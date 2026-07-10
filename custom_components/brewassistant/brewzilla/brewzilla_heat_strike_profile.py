"""Heat-strike/pre-mash-in profile adjustments for BrewZilla.

"Real mash" means a real brewday, not that grain has already been added.
Before mash-in there is still no grain bed, so BrewAssistant should treat early
mash ramps as strike-water heating: use the kettle/wort temperature, allow a
more aggressive heat profile, and keep mash/wort thermal-mix protection disabled
until mash-in has started.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.core import HomeAssistant

from . import brewzilla_advice_control as advice_control
from . import brewzilla_learning as learning
from . import brewzilla_mash_in_gate as mash_in_gate

_INSTALLED = False
_ORIGINAL_WITH_ADVICE: Callable[[HomeAssistant, dict[str, Any]], dict[str, Any]] | None = None
_ORIGINAL_THERMAL_MIX_MODIFIER: Callable[[dict[str, Any], float | None, str], dict[str, Any]] | None = None
_ORIGINAL_TEMPERATURE_SOURCE_SNAPSHOT: Callable[[HomeAssistant, str], dict[str, Any]] | None = None
_ORIGINAL_BATCH_CONTEXT_SNAPSHOT: Callable[[HomeAssistant, dict[str, Any], str], dict[str, Any]] | None = None
_ORIGINAL_MASH_IN_GATE_TARGET_FOR_GATE: Callable[[dict[str, Any]], float | None] | None = None

_DATA_KEY = "brewzilla_heat_strike_latch"
_MASH_IN_STARTED_STATES = {"mash_in_started", "mash_in_complete"}
_PRE_MASH_IN_STATES = {"", "idle", "ready_for_mash_in", "pending", "waiting", "awaiting_mash_in"}
_ACTIVE_OR_PAUSED_STATES = {"live", "running", "paused", "awaiting_snapshot", "prepared", "awaiting_confirm"}
_TERMINAL_STATES = {"", "idle", "inactive", "completed", "complete", "done", "unknown", "unavailable", "none"}
_BAD_VALUE_STRINGS = {"", "none", "unknown", "unavailable"}

_STRIKE_BOOST_FAR_C = 5.0
_STRIKE_BOOST_APPROACH_C = 3.0
_STRIKE_FAR_DELTA_C = 8.0
_STRIKE_APPROACH_DELTA_C = 2.0
_STRIKE_CAPTURE_DELTA_C = 0.5
_STRIKE_OVERSHOOT_MARGIN_C = 0.3
_STRIKE_FAST_FINAL_RATE_C_PER_MIN = 0.8
_STRIKE_PUMP_UTILIZATION = 50.0
_STRIKE_CAPTURE_HEAT_UTILIZATION = 75.0
_STRIKE_READY_HOLD_HEAT_UTILIZATION = 40.0
_STRIKE_READY_FAST_COAST_HEAT_UTILIZATION = 20.0
_STRIKE_OVERSHOOT_COAST_HEAT_UTILIZATION = 0.0
_RCL_DEGRADED_REQUIRED_FIELDS = {
    "current_temperature": "temperature",
    "applied_target": "target",
    "heat_utilization": "heat_utilization",
    "pump_utilization": "pump_utilization",
    "heater_on": "heater_state",
    "pump_on": "pump_state",
}


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str) and value.strip().lower() in _BAD_VALUE_STRINGS:
        return False
    return True


def _mash_in_gate_state(hass: HomeAssistant) -> str:
    store = hass.data.setdefault("brewassistant", {}).get("brewzilla_mash_in_gate")
    if not isinstance(store, dict):
        return ""
    return str(store.get("state") or "").strip().lower()


def _pre_mash_in(hass: HomeAssistant) -> bool:
    """Return true until the operator has marked mash-in as started/complete."""
    state = _mash_in_gate_state(hass)
    if state in _MASH_IN_STARTED_STATES:
        return False
    if state in _PRE_MASH_IN_STATES:
        return True
    # Unknown future gate states should fail safe as pre-mash-in unless they
    # explicitly say mash-in has started or completed.
    return "started" not in state and "complete" not in state


def _latch_store(hass: HomeAssistant) -> dict[str, Any]:
    return hass.data.setdefault("brewassistant", {}).setdefault(
        _DATA_KEY,
        {
            "active": False,
            "strike_target": None,
            "control_target": None,
            "source_step": None,
            "source_state": None,
            "released_reason": None,
        },
    )


def _runtime_state(out: dict[str, Any]) -> str:
    return str(out.get("brewday_state") or "idle").strip().lower()


def _mash_scope(out: dict[str, Any]) -> bool:
    text = " ".join(
        str(out.get(key) or "")
        for key in ("runtime_stage", "runtime_step", "runtime_raw_step_name", "runtime_next_step")
    ).lower()
    if not text:
        return True
    if any(word in text for word in ("boil", "kok", "cool", "chill", "kyl")):
        return False
    return "mash" in text or "mäsk" in text


def _clear_latch(hass: HomeAssistant, reason: str) -> None:
    store = _latch_store(hass)
    store.update(
        {
            "active": False,
            "control_target": None,
            "released_reason": reason,
        }
    )


def _latch_active(hass: HomeAssistant) -> bool:
    store = _latch_store(hass)
    return bool(store.get("active") and _num(store.get("strike_target")) is not None)


def _record_latch(hass: HomeAssistant, out: dict[str, Any], strike_target: float) -> dict[str, Any]:
    store = _latch_store(hass)
    store.update(
        {
            "active": True,
            "strike_target": float(strike_target),
            "source_step": out.get("runtime_step"),
            "source_state": _runtime_state(out),
            "released_reason": None,
        }
    )
    return store


def _latched_strike_target(hass: HomeAssistant) -> float | None:
    if not _latch_active(hass):
        return None
    return _num(_latch_store(hass).get("strike_target"))


def _sync_heat_strike_latch(hass: HomeAssistant, out: dict[str, Any]) -> float | None:
    """Return the active strike target, latching only real pre-mash-in ramps.

    Brewfather can advance from the strike-water ramp to a paused mash-additions
    / hold step before the kettle has physically reached strike temperature.  In
    that paused window BrewAssistant must keep the last strike-water target as
    the active control target and keep the upcoming mash target separate.
    """
    state = _runtime_state(out)
    stage_kind = str(out.get("advice_stage_kind") or "unknown")

    if (
        state in _TERMINAL_STATES
        or out.get("completed_runtime")
        or out.get("abort_lockout_active")
        or not _pre_mash_in(hass)
        or not _mash_scope(out)
    ):
        _clear_latch(hass, "out_of_scope")
        return None

    if stage_kind == "ramp" and state in _ACTIVE_OR_PAUSED_STATES:
        target = _num(out.get("requested_target"))
        if target is not None:
            _record_latch(hass, out, target)
            return target

    latched = _latched_strike_target(hass)
    if latched is None:
        return None

    # While Brewfather is paused on the post-strike mash-additions / first hold
    # step, keep the strike-water target latched. Once the brewer presses
    # Continue and Brewfather runs the actual hold, release the latch and let
    # normal mash-hold logic take over.
    if state in {"paused", "awaiting_confirm", "prepared", "awaiting_snapshot"}:
        return latched

    if state in {"live", "running"} and stage_kind != "ramp":
        _clear_latch(hass, "mash_hold_running")
        return None

    return latched


def _strike_current_temperature(out: dict[str, Any]) -> float | None:
    for key in (
        "current_temperature",
        "advice_learning_temperature",
        "wort_temperature",
        "mash_temperature",
    ):
        value = _num(out.get(key))
        if value is not None:
            return value
    return None


def _heat_strike_control_profile(
    strike_target: float,
    current_temperature: float | None,
    temp_rate: float | None,
) -> tuple[float, float, bool, str, float | None]:
    """Return device target, heat utilization, heater state, phase and strike delta."""
    if current_temperature is None:
        return round(strike_target + _STRIKE_BOOST_APPROACH_C, 1), 100.0, True, "strike_unknown_temperature_boost", None

    delta = round(strike_target - current_temperature, 2)
    if delta > _STRIKE_FAR_DELTA_C:
        return round(strike_target + _STRIKE_BOOST_FAR_C, 1), 100.0, True, "strike_far_boost", delta
    if delta > _STRIKE_APPROACH_DELTA_C:
        return round(strike_target + _STRIKE_BOOST_APPROACH_C, 1), 100.0, True, "strike_approach_boost", delta
    if delta > _STRIKE_CAPTURE_DELTA_C:
        return round(strike_target, 1), _STRIKE_CAPTURE_HEAT_UTILIZATION, True, "strike_capture", delta
    if delta >= -_STRIKE_OVERSHOOT_MARGIN_C:
        if temp_rate is not None and temp_rate > _STRIKE_FAST_FINAL_RATE_C_PER_MIN:
            return (
                round(strike_target, 1),
                _STRIKE_READY_FAST_COAST_HEAT_UTILIZATION,
                True,
                "strike_ready_fast_rise_min_hold",
                delta,
            )
        return round(strike_target, 1), _STRIKE_READY_HOLD_HEAT_UTILIZATION, True, "strike_ready_hold", delta
    return round(strike_target, 1), _STRIKE_OVERSHOOT_COAST_HEAT_UTILIZATION, False, "strike_overshoot_coast", delta


def _rcl_degraded(out: dict[str, Any]) -> tuple[bool, list[str]]:
    """Return true when the BrewZilla command/observation surface is partial.

    A partial RAPT Cloud Link snapshot is more dangerous than a clean disconnect:
    power may still be visible while temperature, target, utilization or switch
    states are missing. In that state BA should not start new positive actions.
    """
    if not out.get("connected"):
        return True, ["connection"]

    missing = [label for key, label in _RCL_DEGRADED_REQUIRED_FIELDS.items() if not _present(out.get(key))]
    return bool(missing), missing


def _apply_rcl_degraded_guard(
    out: dict[str, Any],
    *,
    missing: list[str],
    physical_phase: str,
    strike_target: float,
) -> dict[str, Any]:
    reason = str(out.get("control_reason") or "BrewZilla control surface degraded.")
    out.update(
        {
            "rcl_degraded": True,
            "rcl_degraded_missing": missing,
            "heat_strike_rcl_degraded": True,
            "heat_strike_latch_active": True,
            "heat_strike_target": round(float(strike_target), 1),
            "heat_strike_gate_target": round(float(strike_target), 1),
            "advice_physical_phase": physical_phase,
            "target_sync_needed": False,
            "heating_needed": False,
            "heater_action_needed": False,
            "pump_action_needed": False,
            "heat_utilization_action_needed": False,
            "pump_utilization_action_needed": False,
            "can_apply_target": False,
            "orchestration_mode": "blocked",
            "control_reason": (
                f"RCL degraded during {physical_phase}; missing {', '.join(missing)}. "
                "BA blocks new positive BrewZilla control until a complete fresh snapshot is available. "
                f"Latched strike target remains {round(float(strike_target), 1)}°C. {reason}"
            ),
        }
    )
    return out


def _heat_strike_thermal_mix_modifier(
    advice: dict[str, Any],
    target: float | None,
    stage_kind: str,
) -> dict[str, Any]:
    """Disable mash/wort thermal-mix protection before mash-in."""
    role = str(advice.get("learning_temperature_role") or "")
    if role.startswith("pre_mash_in"):
        return {
            "active": False,
            "reason": "pre_mash_in_strike_water_no_mash_bed",
            "separate_inputs": False,
        }
    assert _ORIGINAL_THERMAL_MIX_MODIFIER is not None
    return _ORIGINAL_THERMAL_MIX_MODIFIER(advice, target, stage_kind)


def _pre_mash_in_temperature_source_snapshot(hass: HomeAssistant, stage_kind: str) -> dict[str, Any]:
    """Use BrewZilla/kettle temperature as learning temperature before mash-in."""
    if not _pre_mash_in(hass) or (stage_kind != "ramp" and not _latch_active(hass)):
        assert _ORIGINAL_TEMPERATURE_SOURCE_SNAPSHOT is not None
        return _ORIGINAL_TEMPERATURE_SOURCE_SNAPSHOT(hass, stage_kind)

    snapshot = learning.brewzilla_temperature_snapshot(hass)
    learning_temperature = snapshot.get("wort_temperature")
    learning_entity = snapshot.get("wort_temperature_entity")
    learning_source = snapshot.get("wort_temperature_source")

    if learning_temperature is None:
        learning_temperature = snapshot.get("mash_temperature")
        learning_entity = snapshot.get("mash_temperature_entity")
        learning_source = snapshot.get("mash_temperature_source")

    return {
        "mash_temperature": snapshot.get("mash_temperature"),
        "mash_temperature_entity": snapshot.get("mash_temperature_entity"),
        "mash_temperature_source": snapshot.get("mash_temperature_source"),
        "wort_temperature": snapshot.get("wort_temperature"),
        "wort_temperature_entity": snapshot.get("wort_temperature_entity"),
        "wort_temperature_source": snapshot.get("wort_temperature_source"),
        "temperature_delta_mash_wort": snapshot.get("temperature_delta_mash_wort"),
        "learning_temperature": learning_temperature,
        "learning_temperature_entity": learning_entity,
        "learning_temperature_source": learning_source,
        "learning_temperature_role": "pre_mash_in_wort_or_kettle_temperature",
        "use_internal_sensor": None,
        "control_device_type": None,
        "control_device_mac_address": None,
    }


def _pre_mash_in_batch_context_snapshot(
    hass: HomeAssistant,
    runtime: dict[str, Any],
    stage_kind: str,
) -> dict[str, Any]:
    """Do not require grain context while the physical phase is still strike water."""
    assert _ORIGINAL_BATCH_CONTEXT_SNAPSHOT is not None
    snapshot = _ORIGINAL_BATCH_CONTEXT_SNAPSHOT(hass, runtime, stage_kind)
    if _pre_mash_in(hass) and (stage_kind == "ramp" or _latch_active(hass)) and snapshot.get("needs_batch_context"):
        snapshot = dict(snapshot)
        snapshot.update(
            {
                "needs_batch_context": False,
                "batch_context_missing": [],
                "batch_context_reason": "Pre-mash-in strike-water ramp: grain/mash context is not required until mash-in starts.",
            }
        )
    return snapshot


def _apply_pre_mash_in_heat_strike_profile(hass: HomeAssistant, out: dict[str, Any]) -> dict[str, Any]:
    """Override advice output with strike-water control only before mash-in."""
    strike_target = _sync_heat_strike_latch(hass, out)
    if strike_target is None:
        out.setdefault("advice_physical_phase", "not_pre_mash_in_strike")
        return out

    state = _runtime_state(out)
    stage_kind = str(out.get("advice_stage_kind") or "unknown")
    paused_wait = bool(state in {"paused", "awaiting_confirm", "prepared", "awaiting_snapshot"} and stage_kind != "ramp")
    physical_phase = "pre_mash_in_paused_wait" if paused_wait else "pre_mash_in"

    degraded, missing = _rcl_degraded(out)
    if degraded:
        return _apply_rcl_degraded_guard(out, missing=missing, physical_phase=physical_phase, strike_target=float(strike_target))

    current_temperature = _strike_current_temperature(out)
    temp_rate = advice_control._num(out.get("advice_temp_rate_c_per_min"))
    control_target, profile_heat, desired_heater_on, profile_phase, strike_delta = _heat_strike_control_profile(
        float(strike_target),
        current_temperature,
        temp_rate,
    )

    applied_target = advice_control._num(out.get("applied_target"))
    target_delta = None if applied_target is None else round(control_target - applied_target, 2)
    target_sync_needed = bool(target_delta is not None and abs(target_delta) > advice_control.base.TARGET_SYNC_TOLERANCE)

    heat_util = advice_control._num(out.get("heat_utilization"))
    pump_util = advice_control._num(out.get("pump_utilization"))
    heater_on = bool(out.get("heater_on"))
    pump_on = bool(out.get("pump_on"))

    heat_utilization_action_needed = advice_control.base._utilization_action_needed(heat_util, profile_heat)
    pump_utilization_action_needed = advice_control.base._utilization_action_needed(pump_util, _STRIKE_PUMP_UTILIZATION)
    heater_action_needed = bool(desired_heater_on and not heater_on)
    heater_stop_needed = bool(desired_heater_on is False and heater_on)
    pump_action_needed = bool(not pump_on)
    pump_stop_needed = False
    action_needed = bool(
        target_sync_needed
        or heat_utilization_action_needed
        or pump_utilization_action_needed
        or heater_action_needed
        or heater_stop_needed
        or pump_action_needed
        or pump_stop_needed
    )
    can_apply = bool(
        out.get("connected")
        and action_needed
        and not out.get("abort_lockout_active")
        and state in _ACTIVE_OR_PAUSED_STATES
        and not out.get("completed_runtime")
    )

    store = _latch_store(hass)
    store["control_target"] = control_target
    store["last_phase"] = profile_phase
    store["last_delta_to_strike"] = strike_delta

    next_mash_target = out.get("requested_target") if paused_wait else None
    reason = str(out.get("control_reason") or "Brewday Advice profile is active.")
    out.update(
        {
            "rcl_degraded": False,
            "rcl_degraded_missing": [],
            "heat_strike_rcl_degraded": False,
            "requested_target": control_target,
            "requested_target_source": "pre_mash_in_strike_control_boost" if control_target != round(float(strike_target), 1) else "pre_mash_in_strike_control",
            "target_delta": target_delta,
            "target_sync_needed": target_sync_needed,
            "paused_target_rewind_blocked": False,
            "heating_needed": bool(strike_delta is None or strike_delta > _STRIKE_CAPTURE_DELTA_C or desired_heater_on),
            "desired_heat_utilization": profile_heat,
            "desired_heater_on": desired_heater_on,
            "heat_utilization_action_needed": heat_utilization_action_needed,
            "heater_action_needed": heater_action_needed,
            "heater_stop_needed": heater_stop_needed,
            "pump_recommended": True,
            "desired_pump_on": True,
            "desired_pump_utilization": _STRIKE_PUMP_UTILIZATION,
            "pump_action_needed": pump_action_needed,
            "pump_stop_needed": pump_stop_needed,
            "pump_utilization_action_needed": pump_utilization_action_needed,
            "can_apply_target": can_apply,
            "orchestration_mode": "direct-control" if can_apply else "monitor",
            "advice_stage_kind": "ramp",
            "advice_physical_phase": physical_phase,
            "advice_capped_heat_utilization": profile_heat,
            "advice_heat_cap": profile_heat,
            "advice_heat_profile_phase": profile_phase,
            "advice_local_profile_heat_utilization": profile_heat,
            "advice_thermal_mix_active": False,
            "advice_thermal_mix_separate_inputs": False,
            "advice_thermal_mix_severity": None,
            "advice_thermal_mix_heat_cap": None,
            "advice_thermal_mix_reason": "pre_mash_in_strike_water_no_mash_bed",
            "advice_delta_to_target": strike_delta,
            "advice_learning_temperature": current_temperature,
            "advice_learning_temperature_role": "pre_mash_in_wort_or_kettle_temperature",
            "mash_in_heat_strategy_active": True,
            "mash_in_heat_strategy_phase": profile_phase,
            "mash_in_heat_strategy_delta_to_target": strike_delta,
            "mash_hold_strategy_active": False,
            "mash_hold_strategy_phase": None,
            "heat_strike_latch_active": True,
            "heat_strike_target": round(float(strike_target), 1),
            "heat_strike_gate_target": round(float(strike_target), 1),
            "heat_strike_control_target": control_target,
            "heat_strike_next_mash_target": next_mash_target,
            "heat_strike_phase": profile_phase,
            "heat_strike_delta_to_target": strike_delta,
            "paused_heat_strike_maintenance_allowed": paused_wait,
            "control_reason": (
                f"{reason} Physical phase {physical_phase}: holding latched strike-water target "
                f"{round(float(strike_target), 1)}°C while next mash target remains {next_mash_target}°C. "
                f"Device/control target {control_target}°C, heat {profile_heat}% ({profile_phase}); "
                "mash/wort thermal-mix protection is disabled until mash-in starts."
            ),
        }
    )
    return out


def _with_heat_strike_phase_control(hass: HomeAssistant, snapshot: dict[str, Any]) -> dict[str, Any]:
    assert _ORIGINAL_WITH_ADVICE is not None
    out = _ORIGINAL_WITH_ADVICE(hass, snapshot)
    return _apply_pre_mash_in_heat_strike_profile(hass, out)


def _mash_in_gate_target_for_gate(snapshot: dict[str, Any]) -> float | None:
    strike_gate_target = _num(snapshot.get("heat_strike_gate_target"))
    if snapshot.get("heat_strike_latch_active") and strike_gate_target is not None:
        return strike_gate_target
    assert _ORIGINAL_MASH_IN_GATE_TARGET_FOR_GATE is not None
    return _ORIGINAL_MASH_IN_GATE_TARGET_FOR_GATE(snapshot)


def install_heat_strike_profile() -> None:
    """Install heat-strike profile and pre-mash-in physical-phase guards."""
    global _INSTALLED
    global _ORIGINAL_WITH_ADVICE
    global _ORIGINAL_THERMAL_MIX_MODIFIER
    global _ORIGINAL_TEMPERATURE_SOURCE_SNAPSHOT
    global _ORIGINAL_BATCH_CONTEXT_SNAPSHOT
    global _ORIGINAL_MASH_IN_GATE_TARGET_FOR_GATE

    if _INSTALLED:
        return

    profile = advice_control.BREWZILLA_BASE_PROFILE
    profile["description"] = "Built-in BrewZilla 35L small-batch profile with explicit pre-mash-in strike-water ramp."
    profile.setdefault("heat", {}).update(
        {
            "ramp_very_far": 100.0,
            "ramp_far": 100.0,
            "ramp_mid": 100.0,
            "ramp_approach": 75.0,
            "ramp_near": 40.0,
            "ramp_final": 40.0,
            "ramp_feather": 0.0,
        }
    )
    profile.setdefault("delta", {}).update(
        {
            "ramp_very_far": 20.0,
            "ramp_far": 10.0,
            "ramp_mid": 5.0,
            "ramp_approach": 2.0,
            "ramp_near": 0.5,
            "ramp_final": 0.2,
            "ramp_feather": 0.0,
        }
    )
    profile.setdefault("rate", {}).update(
        {
            "fast_c_per_min": 0.30,
            "moderate_c_per_min": 0.10,
            "near_target_heat_cap": 40.0,
        }
    )

    _ORIGINAL_WITH_ADVICE = advice_control._with_advice
    _ORIGINAL_THERMAL_MIX_MODIFIER = advice_control._thermal_mix_modifier
    _ORIGINAL_TEMPERATURE_SOURCE_SNAPSHOT = learning._temperature_source_snapshot
    _ORIGINAL_BATCH_CONTEXT_SNAPSHOT = learning._batch_context_snapshot
    _ORIGINAL_MASH_IN_GATE_TARGET_FOR_GATE = mash_in_gate._target_for_gate

    advice_control._with_advice = _with_heat_strike_phase_control
    advice_control._thermal_mix_modifier = _heat_strike_thermal_mix_modifier
    learning._temperature_source_snapshot = _pre_mash_in_temperature_source_snapshot
    learning._batch_context_snapshot = _pre_mash_in_batch_context_snapshot
    mash_in_gate._target_for_gate = _mash_in_gate_target_for_gate

    _INSTALLED = True
