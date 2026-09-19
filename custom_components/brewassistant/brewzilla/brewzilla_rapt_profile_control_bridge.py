"""Bridge RAPT profile intent into BrewAssistant's existing hot-side controller.

A RAPT BrewZilla profile is a process/target source, analogous to Brewfather
Brew Tracker. The profile runner advances process steps locally, while
BrewAssistant owns target transport and heat/pump regulation. RAPT profile
heat/pump values are therefore metadata only and are not required for BA control.

The bridge also translates two RAPT-specific process conventions:

* a manual ``Mash In`` step may already advertise the lower mash target after
  Heatstrike has completed. BA keeps the previous strike target latched until
  the operator presses Mash-In Started, then releases to the RAPT mash target;
* a ``ChillOut``/cooling step may use 0 C only as a profile marker. BA must not
  transport that marker as a BrewZilla hot-side target. It requests heater
  safe-down and releases pump ownership to the cooling/operator flow instead.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.core import HomeAssistant, State

from ..brewday import rapt_profile_runtime as rapt_runtime
from ..brewday.rapt_profile_runtime import RAPT_PROFILE_SOURCE
from . import brewzilla_orchestration as orchestration
from . import brewzilla_phase_authority as phase_authority
from . import brewzilla_supervised_runtime_guard as supervised

_INSTALLED = False
_ORIGINAL_ACTIVE_SNAPSHOT: Callable[[HomeAssistant, State, dict[str, Any]], dict[str, Any]] | None = None
_ORIGINAL_PHASE_AUTHORITY_ACTIVE: Callable[[HomeAssistant, dict[str, Any]], bool] | None = None
_ORIGINAL_PRE_MASH_IN: Callable[[HomeAssistant], bool] | None = None
_ORIGINAL_AUTHORITY_DIAGNOSTICS: Callable[[dict[str, Any]], dict[str, Any]] | None = None
_ORIGINAL_REQUEST_SOURCE: Callable[[dict[str, Any]], str] | None = None
_ORIGINAL_ORCHESTRATION_BUILD: Callable[[HomeAssistant], dict[str, Any]] | None = None

_BOIL_WORDS = ("boil", "boiling", "kok", "kokning", "heating to boil", "värm till kok")
_COOL_WORDS = ("cool", "cooling", "chill", "chilling", "chillout", "kyl", "kylning")
_WHIRLPOOL_WORDS = ("whirlpool", "hopstand", "hop stand", "hop-stånd", "humlestånd")
_HEATSTRIKE_WORDS = ("heatstrike", "heat strike", "strike water")
_MASH_IN_WORDS = ("mash in", "mash-in", "inmäsk", "inmask")
_RAMP_WORDS = ("ramp", "heat", "heating", "värm", "uppvärm", "strike", "mash in", "mash-in")
_HOLD_WORDS = ("hold", "rest", "rast", "mash", "mäsk", "saccharification", "beta", "alpha")
_ACTIVE_RUNTIME_STATES = {"live", "running", "paused", "awaiting_snapshot"}
_MASH_IN_STARTED_STATES = {"mash_in_started", "mash_in_complete"}
_TARGET_REACHED_TOLERANCE_C = 0.3


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _contains(text: str, words: tuple[str, ...]) -> bool:
    return any(word in text for word in words)


def _semantic_stage_step(snapshot: dict[str, Any]) -> tuple[str, str]:
    """Map RAPT step metadata to semantic text existing BA logic consumes.

    Explicit process names win. For generic RAPT names (``Step 1`` etc.) the
    profile end/control type provides a conservative fallback: temperature-ended
    steps are ramps, duration-ended steps are holds. A >=95 C generic target is
    treated as boil heat/hold rather than mash.

    RAPT can combine a ramp and a timed Mash Out hold in one step. When the step
    is named Mash Out, BA treats it as a ramp until target is physically reached
    and as a hold afterwards.
    """
    raw_name = str(snapshot.get("raw_step_name") or snapshot.get("step") or "Profile step")
    text = raw_name.lower()
    target = _num(snapshot.get("target_temperature"))
    current = _num(snapshot.get("actual_temperature"))
    control_type = str(snapshot.get("profile_step_control_type") or "").strip().lower()
    end_type = str(snapshot.get("profile_step_end_type") or "").strip().lower()

    if _contains(text, _COOL_WORDS):
        return "Cooling", raw_name
    if _contains(text, _WHIRLPOOL_WORDS):
        return "Whirlpool", raw_name
    if _contains(text, _BOIL_WORDS):
        return "Boil", raw_name
    if _contains(text, _HEATSTRIKE_WORDS):
        # Normalize the compact RAPT spelling "Heatstrike" into the phrase the
        # existing BA Heat Strike controller already recognizes.
        return "Mash", "Heat Strike"
    if _contains(text, _MASH_IN_WORDS):
        return "Mash", "Mash In"

    generic_boil = bool(target is not None and target >= 95.0)
    if generic_boil and (end_type in {"temperature", "duration"} or control_type in {"target", "ramp"}):
        prefix = "Heat to Boil" if end_type == "temperature" or control_type == "ramp" else "Boil Hold"
        return "Boil", f"{prefix} · {raw_name}"

    if "mash out" in text or "mäsk ut" in text or "mäskout" in text:
        if target is not None and current is not None and current < target - _TARGET_REACHED_TOLERANCE_C:
            return "Mash", f"Ramp · {raw_name}"
        return "Mash", f"Mash Hold · {raw_name}"

    if _contains(text, _RAMP_WORDS) or control_type == "ramp" or end_type == "temperature":
        step = raw_name if _contains(text, _RAMP_WORDS) else f"Ramp · {raw_name}"
        return "Mash", step

    if _contains(text, _HOLD_WORDS) or end_type == "duration":
        step = raw_name if _contains(text, _HOLD_WORDS) else f"Mash Hold · {raw_name}"
        return "Mash", step

    return "RAPT Profile", raw_name


def _manual_mash_in(snapshot: dict[str, Any]) -> bool:
    text = str(snapshot.get("raw_step_name") or snapshot.get("step") or "").lower()
    end_type = str(snapshot.get("profile_step_end_type") or "").strip().lower()
    return bool(_contains(text, _MASH_IN_WORDS) and (end_type == "manual" or not end_type))


def _previous_profile_target(known: dict[str, Any]) -> float | None:
    """Return the previous RAPT step target, used as the strike latch fallback."""
    steps = known.get("profile_steps")
    if not isinstance(steps, list):
        return None

    current_number = _num(known.get("step_number"))
    current_id = known.get("step_id")
    current_index: int | None = None

    for index, raw_step in enumerate(steps):
        if not isinstance(raw_step, dict):
            continue
        if current_id and raw_step.get("id") == current_id:
            current_index = index
            break
        step_number = _num(raw_step.get("step_number"))
        if current_number is not None and step_number == current_number:
            current_index = index
            break

    if current_index is None or current_index <= 0:
        return None
    previous = steps[current_index - 1]
    if not isinstance(previous, dict):
        return None
    return _num(previous.get("target_temperature"))


def _active_snapshot(hass: HomeAssistant, state: State, known: dict[str, Any]) -> dict[str, Any]:
    """Decorate active RAPT runtime as BA-controlled process intent."""
    assert _ORIGINAL_ACTIVE_SNAPSHOT is not None
    out = _ORIGINAL_ACTIVE_SNAPSHOT(hass, state, known)
    raw_target = _num(out.get("target_temperature"))
    stage, step = _semantic_stage_step(out)
    profile_name = str(out.get("profile_name") or "RAPT BrewZilla profile")
    gate_state = str(phase_authority._gate_store(hass).get("state") or "idle").lower()

    strike_hold_target: float | None = None
    strike_hold_active = False
    if _manual_mash_in(out) and gate_state not in _MASH_IN_STARTED_STATES:
        strike_hold_target = _previous_profile_target(known)
        if strike_hold_target is not None:
            # RAPT has advanced from Heatstrike to its manual Mash In marker and
            # now advertises the lower mash target. Keep the physical strike
            # target until the brewer explicitly starts adding grain.
            out["target_temperature"] = strike_hold_target
            out["target_temperature_source"] = "rapt_previous_heatstrike_until_mash_in_started"
            strike_hold_active = True

    cooling_marker = stage == "Cooling"
    if cooling_marker:
        # ChillOut commonly uses target 0 only to mark the cooling phase. It is
        # not a hot-side target for BrewAssistant to write back to BrewZilla.
        out["target_temperature"] = None
        out["target_temperature_source"] = "rapt_cooling_marker_ignored"

    out.update(
        {
            "runtime_state": "running",
            "stage": stage,
            "step": step,
            "process_executor": "rapt_profile_step_runner",
            "process_source": "rapt_cloud_link",
            "directive_source": "rapt_profile",
            "control_owner": "brewassistant",
            "transport": "rapt_cloud_link",
            "hardware_executor": "brewzilla",
            "brewassistant_role": "hot_side_controller",
            "direct_brewzilla_control_allowed": not cooling_marker,
            "rapt_profile_role": "process_and_target_source",
            "target_intent_owner": "rapt_profile",
            "heat_pump_owner": "brewassistant" if not cooling_marker else "cooling_handoff",
            "rapt_directive_target_temperature": raw_target,
            "rapt_effective_ba_target_temperature": _num(out.get("target_temperature")),
            "rapt_mash_in_strike_hold_active": strike_hold_active,
            "rapt_mash_in_strike_hold_target": strike_hold_target,
            "rapt_target_control_suppressed": cooling_marker,
            "cooling_handoff_requested": cooling_marker,
            "summary": (
                f"BA cooling handoff · RAPT profile · {profile_name} · {step}"
                if cooling_marker
                else f"BA control · RAPT profile · {profile_name} · {step}"
            ),
        }
    )
    return out


def _rapt_cooling_handoff(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Convert an active RAPT cooling marker into hot-side heater safe-down.

    Cooling Runtime owns the next physical phase. BrewAssistant therefore stops
    hot-side heating and ignores the profile's marker target, while leaving the
    BrewZilla wort-pump state/operator ownership alone for CFC/coil operation.
    """
    source = str(snapshot.get("runtime_source") or "")
    stage = str(snapshot.get("runtime_stage") or "").lower()
    if source != RAPT_PROFILE_SOURCE or not _contains(stage, _COOL_WORDS):
        snapshot.setdefault("rapt_cooling_handoff_active", False)
        return snapshot

    out = dict(snapshot)
    heater_on = bool(out.get("heater_on"))
    heat_util = _num(out.get("heat_utilization"))
    heat_zero_needed = bool(
        heat_util is not None
        and abs(float(heat_util)) > orchestration.UTILIZATION_TOLERANCE
    )
    action_needed = bool(heater_on or heat_zero_needed)
    connected = bool(out.get("connected"))
    can_apply = bool(connected and action_needed and not out.get("abort_lockout_active"))

    out.update(
        {
            "requested_target": None,
            "requested_target_source": "rapt_cooling_marker_ignored",
            "target_sync_needed": False,
            "heating_needed": False,
            "desired_heat_utilization": 0.0,
            "desired_heater_on": False,
            "heater_action_needed": False,
            "heater_stop_needed": heater_on,
            "heat_utilization_action_needed": heat_zero_needed,
            # Pump belongs to Cooling Runtime/operator from this boundary. Do not
            # force it OFF merely because hot-side control has ended.
            "pump_recommended": False,
            "desired_pump_on": None,
            "desired_pump_utilization": None,
            "pump_action_needed": False,
            "pump_stop_needed": False,
            "pump_utilization_action_needed": False,
            "completion_stop_needed": False,
            "completion_pump_stop_needed": False,
            "ba_owned_reassert_action_needed": False,
            "can_apply_target": can_apply,
            "orchestration_mode": "direct-control" if can_apply else "monitor",
            "rapt_cooling_handoff_active": True,
            "rapt_cooling_target_ignored": True,
            "rapt_cooling_heat_safe_down_needed": action_needed,
            "brewzilla_pump_owner": "cooling_runtime_or_operator",
            "control_reason": (
                "RAPT cooling/ChillOut step active. Profile target is a process marker, not a hot-side target; "
                "BA requests heater OFF and heat utilization 0%, then releases BrewZilla pump ownership to Cooling Runtime/operator."
            ),
        }
    )
    return out


def build_orchestration_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    """Apply the RAPT-specific cooling ownership boundary to BA orchestration."""
    assert _ORIGINAL_ORCHESTRATION_BUILD is not None
    return _rapt_cooling_handoff(_ORIGINAL_ORCHESTRATION_BUILD(hass))


def _rapt_pre_mash_in(hass: HomeAssistant) -> bool:
    """Give active RAPT mash intent the same physical pre-mash authority as BT."""
    assert _ORIGINAL_PRE_MASH_IN is not None
    if _ORIGINAL_PRE_MASH_IN(hass):
        return True

    runtime = phase_authority.build_brewday_runtime_snapshot(hass)
    runtime_state = str(runtime.get("runtime_state") or "idle").lower()
    source = str(runtime.get("source") or "")
    stage = str(runtime.get("stage") or "").lower()
    gate = phase_authority._gate_store(hass)
    gate_state = str(gate.get("state") or "idle").lower()

    return bool(
        source == RAPT_PROFILE_SOURCE
        and runtime_state in _ACTIVE_RUNTIME_STATES
        and ("mash" in stage or "mäsk" in stage)
        and not phase_authority._gate_complete(hass)
        and gate_state in phase_authority._PRE_MASH_IN_GATE_STATES
    )


def _phase_authority_active(hass: HomeAssistant, snapshot: dict[str, Any]) -> bool:
    """Extend BT phase authority to RAPT profile-driven BA regulation."""
    assert _ORIGINAL_PHASE_AUTHORITY_ACTIVE is not None
    if _ORIGINAL_PHASE_AUTHORITY_ACTIVE(hass, snapshot):
        return True

    runtime_state = str(snapshot.get("brewday_state") or "idle").lower()
    runtime_source = str(snapshot.get("runtime_source") or "")
    gate_state = str(phase_authority._gate_store(hass).get("state") or "idle").lower()

    if (
        runtime_source != RAPT_PROFILE_SOURCE
        or runtime_state not in _ACTIVE_RUNTIME_STATES
        or snapshot.get("completed_runtime")
        or snapshot.get("abort_lockout_active")
        or phase_authority._gate_complete(hass)
    ):
        return False

    if snapshot.get("clean_heat_strike_active"):
        return True

    return gate_state in {"ready_for_mash_in", "mash_in_started"}


def _authority_diagnostics(snapshot: dict[str, Any]) -> dict[str, Any]:
    assert _ORIGINAL_AUTHORITY_DIAGNOSTICS is not None
    out = _ORIGINAL_AUTHORITY_DIAGNOSTICS(snapshot)
    if snapshot.get("runtime_source") == RAPT_PROFILE_SOURCE:
        out["phase_authority_source"] = "rapt_profile_active"
    return out


def _request_source(snapshot: dict[str, Any]) -> str:
    """Use the same supervised control policy for RAPT intent as Brew Tracker."""
    assert _ORIGINAL_REQUEST_SOURCE is not None
    if snapshot.get("runtime_source") == RAPT_PROFILE_SOURCE:
        return supervised.SOURCE_BREW_TRACKER
    return _ORIGINAL_REQUEST_SOURCE(snapshot)


def install_rapt_profile_control_bridge() -> None:
    """Install the RAPT process-source bridge after generic supervised guards."""
    global _INSTALLED
    global _ORIGINAL_ACTIVE_SNAPSHOT
    global _ORIGINAL_PHASE_AUTHORITY_ACTIVE
    global _ORIGINAL_PRE_MASH_IN
    global _ORIGINAL_AUTHORITY_DIAGNOSTICS
    global _ORIGINAL_REQUEST_SOURCE
    global _ORIGINAL_ORCHESTRATION_BUILD

    if _INSTALLED:
        return

    _ORIGINAL_ACTIVE_SNAPSHOT = rapt_runtime._active_snapshot
    _ORIGINAL_PHASE_AUTHORITY_ACTIVE = phase_authority._phase_authority_active
    _ORIGINAL_PRE_MASH_IN = phase_authority._brewtracker_pre_mash_in
    _ORIGINAL_AUTHORITY_DIAGNOSTICS = phase_authority._authority_diagnostics
    _ORIGINAL_REQUEST_SOURCE = supervised._request_source
    _ORIGINAL_ORCHESTRATION_BUILD = orchestration.build_orchestration_snapshot

    rapt_runtime._active_snapshot = _active_snapshot
    phase_authority._phase_authority_active = _phase_authority_active
    phase_authority._brewtracker_pre_mash_in = _rapt_pre_mash_in
    phase_authority._authority_diagnostics = _authority_diagnostics
    supervised._request_source = _request_source
    orchestration.build_orchestration_snapshot = build_orchestration_snapshot
    _INSTALLED = True
