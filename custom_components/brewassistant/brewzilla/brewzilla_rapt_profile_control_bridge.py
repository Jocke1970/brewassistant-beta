"""Bridge RAPT profile intent into BrewAssistant's existing hot-side controller.

A RAPT BrewZilla profile is a process/target source, analogous to Brewfather
Brew Tracker.  The profile runner may advance steps locally, but BrewAssistant
owns target transport and heat/pump regulation.  RAPT profile heat/pump values
are therefore not required for BrewAssistant control.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.core import HomeAssistant, State

from ..brewday import rapt_profile_runtime as rapt_runtime
from ..brewday.rapt_profile_runtime import RAPT_PROFILE_SOURCE
from . import brewzilla_phase_authority as phase_authority
from . import brewzilla_supervised_runtime_guard as supervised

_INSTALLED = False
_ORIGINAL_ACTIVE_SNAPSHOT: Callable[[HomeAssistant, State, dict[str, Any]], dict[str, Any]] | None = None
_ORIGINAL_PHASE_AUTHORITY_ACTIVE: Callable[[HomeAssistant, dict[str, Any]], bool] | None = None
_ORIGINAL_PRE_MASH_IN: Callable[[HomeAssistant], bool] | None = None
_ORIGINAL_AUTHORITY_DIAGNOSTICS: Callable[[dict[str, Any]], dict[str, Any]] | None = None
_ORIGINAL_REQUEST_SOURCE: Callable[[dict[str, Any]], str] | None = None

_BOIL_WORDS = ("boil", "boiling", "kok", "kokning", "heating to boil", "värm till kok")
_COOL_WORDS = ("cool", "cooling", "chill", "chilling", "kyl", "kylning")
_WHIRLPOOL_WORDS = ("whirlpool", "hopstand", "hop stand", "hop-stånd", "humlestånd")
_RAMP_WORDS = ("ramp", "heat", "heating", "värm", "uppvärm", "strike", "mash in", "mash-in")
_HOLD_WORDS = ("hold", "rest", "rast", "mash", "mäsk", "saccharification", "beta", "alpha")
_ACTIVE_RUNTIME_STATES = {"live", "running", "paused", "awaiting_snapshot"}


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
    """Map RAPT step metadata to the semantic text existing BA logic consumes.

    Explicit step names win.  For generic RAPT names ("Step 1" etc.) the
    profile end/control type provides a conservative fallback: temperature-ended
    steps are ramps, duration-ended steps are holds.  A >=95 C generic target is
    treated as boil heat/hold rather than mash.
    """
    raw_name = str(snapshot.get("raw_step_name") or snapshot.get("step") or "Profile step")
    text = raw_name.lower()
    target = _num(snapshot.get("target_temperature"))
    control_type = str(snapshot.get("profile_step_control_type") or "").strip().lower()
    end_type = str(snapshot.get("profile_step_end_type") or "").strip().lower()

    if _contains(text, _COOL_WORDS):
        return "Cooling", raw_name
    if _contains(text, _WHIRLPOOL_WORDS):
        return "Whirlpool", raw_name
    if _contains(text, _BOIL_WORDS):
        return "Boil", raw_name

    generic_boil = bool(target is not None and target >= 95.0)
    if generic_boil and (end_type in {"temperature", "duration"} or control_type in {"target", "ramp"}):
        prefix = "Heat to Boil" if end_type == "temperature" or control_type == "ramp" else "Boil Hold"
        return "Boil", f"{prefix} · {raw_name}"

    if "mash out" in text or "mäsk ut" in text or "mäskout" in text:
        return "Mash", raw_name if _contains(text, _RAMP_WORDS) else f"Ramp · {raw_name}"

    if _contains(text, _RAMP_WORDS) or control_type == "ramp" or end_type == "temperature":
        step = raw_name if _contains(text, _RAMP_WORDS) else f"Ramp · {raw_name}"
        return "Mash", step

    if _contains(text, _HOLD_WORDS) or end_type == "duration":
        step = raw_name if _contains(text, _HOLD_WORDS) else f"Mash Hold · {raw_name}"
        return "Mash", step

    return "RAPT Profile", raw_name


def _active_snapshot(hass: HomeAssistant, state: State, known: dict[str, Any]) -> dict[str, Any]:
    """Decorate active RAPT runtime as BA-controlled process intent."""
    assert _ORIGINAL_ACTIVE_SNAPSHOT is not None
    out = _ORIGINAL_ACTIVE_SNAPSHOT(hass, state, known)
    stage, step = _semantic_stage_step(out)
    profile_name = str(out.get("profile_name") or "RAPT BrewZilla profile")

    out.update(
        {
            "runtime_state": "running",
            "stage": stage,
            "step": step,
            "process_executor": "rapt_profile_step_runner",
            "control_owner": "brewassistant",
            "brewassistant_role": "hot_side_controller",
            "direct_brewzilla_control_allowed": True,
            "rapt_profile_role": "process_and_target_source",
            "target_intent_owner": "rapt_profile",
            "heat_pump_owner": "brewassistant",
            "summary": f"BA control · RAPT profile · {profile_name} · {step}",
        }
    )
    return out


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

    if _INSTALLED:
        return

    _ORIGINAL_ACTIVE_SNAPSHOT = rapt_runtime._active_snapshot
    _ORIGINAL_PHASE_AUTHORITY_ACTIVE = phase_authority._phase_authority_active
    _ORIGINAL_PRE_MASH_IN = phase_authority._brewtracker_pre_mash_in
    _ORIGINAL_AUTHORITY_DIAGNOSTICS = phase_authority._authority_diagnostics
    _ORIGINAL_REQUEST_SOURCE = supervised._request_source

    rapt_runtime._active_snapshot = _active_snapshot
    phase_authority._phase_authority_active = _phase_authority_active
    phase_authority._brewtracker_pre_mash_in = _rapt_pre_mash_in
    phase_authority._authority_diagnostics = _authority_diagnostics
    supervised._request_source = _request_source
    _INSTALLED = True
