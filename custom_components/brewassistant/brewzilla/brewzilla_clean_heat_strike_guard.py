"""Final clean heat-strike guard for BrewZilla.

This guard makes the physical pre-mash-in heat-strike phase explicit and
separates two different jobs:

* readiness / operator gate: the mash/BLE/control probe should reach strike
  because that is the temperature the brewer uses for mash-in readiness.
* overshoot safety: the hottest kettle/wort/internal view must cap heat early
  and drive stronger pump mixing when the kettle is running hotter than the
  mash/BLE probe.

While mash-in has not started, Brewfather may already be paused on the first
mash hold.  BA must still control the physical strike-water phase rather than
treating the Brewfather hold as a real mash hold.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.core import HomeAssistant

from . import brewzilla_advice_control as advice_control

_INSTALLED = False
_ORIGINAL_WITH_ADVICE: Callable[[HomeAssistant, dict[str, Any]], dict[str, Any]] | None = None

_ACTIVE_STATES = {"live", "running", "paused", "awaiting_snapshot", "prepared", "awaiting_confirm"}

# Nominal heat profile from the operator-facing strike gate temperature.  This
# answers the question: how far is the mash/BLE/control probe from strike?
_GATE_HEAT_PROFILE: tuple[tuple[float, float, bool, str], ...] = (
    (1.0, 0.0, False, "clean_gate_final_coast"),
    (3.0, 10.0, True, "clean_gate_final_low_hold"),
    (5.0, 25.0, True, "clean_gate_capture"),
    (8.0, 50.0, True, "clean_gate_approach"),
    (10.0, 75.0, True, "clean_gate_late_ramp"),
)
_GATE_FAR_HEAT = 100.0
_GATE_FAR_PHASE = "clean_gate_far_ramp"

# Safety heat cap from the hottest kettle/wort/internal view.  This answers the
# question: is the hot side already too close to strike to keep pushing heat?
_SAFETY_HEAT_CAPS: tuple[tuple[float, float, bool, str], ...] = (
    (0.0, 0.0, False, "clean_safety_at_or_over_strike"),
    (1.0, 0.0, False, "clean_safety_final_coast"),
    (3.0, 10.0, True, "clean_safety_final_low_hold"),
    (5.0, 25.0, True, "clean_safety_capture_cap"),
    (8.0, 50.0, True, "clean_safety_approach_cap"),
    (10.0, 75.0, True, "clean_safety_late_ramp_cap"),
)
_SAFETY_FAR_CAP = 100.0
_SAFETY_FAR_PHASE = "clean_safety_far_no_cap"

# Pump floors during heat-strike.  The pump is used for strike-water mixing here;
# there is no grain bed yet, so compaction is not a concern before mash-in.
_PUMP_FAR = 70.0
_PUMP_NEAR = 90.0
_PUMP_READY = 100.0
_DELTA_PUMP_SMALL_C = 1.5
_DELTA_PUMP_MID_C = 3.0
_DELTA_PUMP_LARGE_C = 5.0


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _runtime_state(out: dict[str, Any]) -> str:
    return str(out.get("brewday_state") or "idle").strip().lower()


def _clean_heatstrike_active(out: dict[str, Any]) -> bool:
    physical_phase = str(out.get("advice_physical_phase") or "").lower()
    return bool(
        out.get("heat_strike_latch_active")
        and physical_phase.startswith("pre_mash_in")
        and _runtime_state(out) in _ACTIVE_STATES
        and not out.get("completed_runtime")
        and not out.get("abort_lockout_active")
        and not out.get("rcl_degraded")
        and not out.get("heat_strike_rcl_degraded")
    )


def _strike_target(out: dict[str, Any]) -> float | None:
    return _num(out.get("heat_strike_target") or out.get("heat_strike_gate_target"))


def _gate_temperature(out: dict[str, Any]) -> tuple[float | None, str | None]:
    """Return the operator-facing heat-strike gate temperature.

    Mash/BLE/control temperature should be the primary readiness signal because
    that is what tells the brewer whether the strike water is ready at the probe
    location used for mash-in.  Kettle/wort/internal readings are fallback only
    for readiness.
    """
    for key in (
        "mash_temperature",
        "mash_in_gate_current_temperature",
        "heat_strike_control_temperature",
    ):
        value = _num(out.get(key))
        if value is not None:
            return value, key

    for key in (
        "advice_learning_temperature",
        "current_temperature",
        "brewzilla_current_temp",
        "wort_temperature",
        "heat_strike_transition_brake_temperature",
    ):
        value = _num(out.get(key))
        if value is not None:
            return value, key

    return None, None


def _safety_temperature(out: dict[str, Any]) -> tuple[float | None, str | None]:
    """Return the hottest strike-water safety temperature.

    This is intentionally different from the readiness/gate temperature.  It is
    used only to cap heat and prevent overshoot when kettle/wort is already hot
    while mash/BLE still lags behind.
    """
    candidates: list[tuple[str, float]] = []
    for key in (
        "current_temperature",
        "brewzilla_current_temp",
        "wort_temperature",
        "heat_strike_transition_brake_temperature",
        "advice_learning_temperature",
        "mash_temperature",
        "mash_in_gate_current_temperature",
    ):
        value = _num(out.get(key))
        if value is not None:
            candidates.append((key, value))

    if not candidates:
        return None, None

    source, value = max(candidates, key=lambda item: item[1])
    return value, source


def _heat_from_gate_delta(delta: float | None) -> tuple[float | None, bool | None, str | None]:
    if delta is None:
        return None, None, None
    for threshold, heat, heater_on, phase in _GATE_HEAT_PROFILE:
        if delta <= threshold:
            return heat, heater_on, phase
    return _GATE_FAR_HEAT, True, _GATE_FAR_PHASE


def _heat_cap_from_safety_delta(delta: float | None) -> tuple[float | None, bool | None, str | None]:
    if delta is None:
        return None, None, None
    for threshold, heat_cap, heater_on, phase in _SAFETY_HEAT_CAPS:
        if delta <= threshold:
            return heat_cap, heater_on, phase
    return _SAFETY_FAR_CAP, True, _SAFETY_FAR_PHASE


def _mash_wort_delta(out: dict[str, Any]) -> float | None:
    mash = _num(out.get("mash_temperature") or out.get("mash_in_gate_current_temperature"))
    wort = _num(out.get("wort_temperature") or out.get("current_temperature") or out.get("brewzilla_current_temp"))
    if mash is None or wort is None:
        return None
    return round(float(wort) - float(mash), 2)


def _pump_for_conditions(out: dict[str, Any], safety_delta: float | None, gate_delta: float | None) -> tuple[float, str, float | None]:
    mw_delta = _mash_wort_delta(out)
    if mw_delta is not None:
        if mw_delta >= _DELTA_PUMP_LARGE_C:
            return _PUMP_READY, "clean_strike_mash_wort_large_mix", mw_delta
        if mw_delta >= _DELTA_PUMP_MID_C:
            return _PUMP_NEAR, "clean_strike_mash_wort_mid_mix", mw_delta
        if mw_delta >= _DELTA_PUMP_SMALL_C:
            return 80.0, "clean_strike_mash_wort_small_mix", mw_delta

    # When either view is close to target, mix more aggressively so the readings
    # converge before the operator mashes in.
    closest_delta = min(
        value for value in (safety_delta, gate_delta) if value is not None
    ) if safety_delta is not None or gate_delta is not None else None

    if closest_delta is not None and closest_delta <= 3.0:
        return _PUMP_READY, "clean_strike_near_target_equalize", mw_delta
    if closest_delta is not None and closest_delta <= 8.0:
        return _PUMP_NEAR, "clean_strike_approach_equalize", mw_delta
    return _PUMP_FAR, "clean_strike_ramp_mix", mw_delta


def _can_apply(out: dict[str, Any], action_needed: bool) -> bool:
    return bool(
        out.get("connected")
        and action_needed
        and _runtime_state(out) in _ACTIVE_STATES
        and not out.get("abort_lockout_active")
        and not out.get("completed_runtime")
    )


def _apply_clean_heatstrike(out: dict[str, Any]) -> dict[str, Any]:
    if not _clean_heatstrike_active(out):
        out.setdefault("clean_heat_strike_active", False)
        return out

    strike = _strike_target(out)
    if strike is None:
        out.setdefault("clean_heat_strike_active", False)
        return out

    gate_temp, gate_source = _gate_temperature(out)
    safety_temp, safety_source = _safety_temperature(out)
    gate_delta = None if gate_temp is None else round(float(strike) - float(gate_temp), 2)
    safety_delta = None if safety_temp is None else round(float(strike) - float(safety_temp), 2)

    gate_heat, gate_heater_on, gate_phase = _heat_from_gate_delta(gate_delta)
    safety_cap, safety_heater_on, safety_phase = _heat_cap_from_safety_delta(safety_delta)
    if gate_heat is None or gate_heater_on is None or gate_phase is None:
        out.setdefault("clean_heat_strike_active", False)
        return out
    if safety_cap is None or safety_heater_on is None or safety_phase is None:
        safety_cap, safety_heater_on, safety_phase = 100.0, True, "clean_safety_unknown_no_cap"

    clean_heat = min(float(gate_heat), float(safety_cap))
    # If the safety view says heater off, it wins over the readiness gate.
    clean_heater_on = bool(gate_heater_on and safety_heater_on and clean_heat > advice_control.base.UTILIZATION_TOLERANCE)
    clean_phase = gate_phase if clean_heat == float(gate_heat) else safety_phase

    pump_floor, pump_reason, mw_delta = _pump_for_conditions(out, safety_delta, gate_delta)
    desired_pump_current = _num(out.get("desired_pump_utilization"))
    clean_pump = pump_floor if desired_pump_current is None else max(float(desired_pump_current), pump_floor)

    heat_util = advice_control._num(out.get("heat_utilization"))
    pump_util = advice_control._num(out.get("pump_utilization"))
    heater_on = bool(out.get("heater_on"))
    pump_on = bool(out.get("pump_on"))
    applied_target = advice_control._num(out.get("applied_target"))
    target = round(float(strike), 1)
    target_delta = None if applied_target is None else round(target - applied_target, 2)
    target_sync_needed = bool(
        target_delta is not None and abs(target_delta) > advice_control.base.TARGET_SYNC_TOLERANCE
    )

    heat_needed = advice_control.base._utilization_action_needed(heat_util, clean_heat)
    pump_needed = advice_control.base._utilization_action_needed(pump_util, clean_pump)
    heater_action_needed = bool(clean_heater_on and not heater_on)
    heater_stop_needed = bool(clean_heater_on is False and heater_on)
    pump_action_needed = bool(not pump_on)
    action_needed = bool(
        target_sync_needed
        or heat_needed
        or pump_needed
        or heater_action_needed
        or heater_stop_needed
        or pump_action_needed
    )

    original_reason = str(out.get("control_reason") or "BrewZilla heat-strike control active.")
    previous_heat = _num(out.get("desired_heat_utilization"))
    previous_pump = _num(out.get("desired_pump_utilization"))

    out.update(
        {
            "clean_heat_strike_active": True,
            "clean_heat_strike_phase": clean_phase,
            "clean_heat_strike_gate_temperature": gate_temp,
            "clean_heat_strike_gate_temperature_source": gate_source,
            "clean_heat_strike_gate_delta_to_target": gate_delta,
            "clean_heat_strike_safety_temperature": safety_temp,
            "clean_heat_strike_safety_temperature_source": safety_source,
            "clean_heat_strike_safety_delta_to_target": safety_delta,
            "clean_heat_strike_gate_heat_utilization": gate_heat,
            "clean_heat_strike_safety_heat_cap": safety_cap,
            "clean_heat_strike_original_heat_utilization": previous_heat,
            "clean_heat_strike_original_pump_utilization": previous_pump,
            "clean_heat_strike_pump_reason": pump_reason,
            "clean_heat_strike_mash_wort_delta": mw_delta,
            "requested_target": target,
            "requested_target_source": "clean_pre_mash_in_strike_control",
            "target_delta": target_delta,
            "target_sync_needed": target_sync_needed,
            "desired_heat_utilization": round(float(clean_heat), 1),
            "desired_heater_on": clean_heater_on,
            "heating_needed": bool(clean_heat > advice_control.base.UTILIZATION_TOLERANCE),
            "heat_utilization_action_needed": heat_needed,
            "heater_action_needed": heater_action_needed,
            "heater_stop_needed": heater_stop_needed,
            "pump_recommended": True,
            "desired_pump_on": True,
            "desired_pump_utilization": round(float(clean_pump), 1),
            "pump_action_needed": pump_action_needed,
            "pump_stop_needed": False,
            "pump_utilization_action_needed": pump_needed,
            "can_apply_target": _can_apply(out, action_needed),
            "orchestration_mode": "direct-control" if action_needed else "monitor",
            "advice_capped_heat_utilization": round(float(clean_heat), 1),
            "advice_heat_cap": round(float(clean_heat), 1),
            "advice_heat_profile_phase": clean_phase,
            "advice_local_profile_heat_utilization": round(float(clean_heat), 1),
            "mash_in_heat_strategy_phase": clean_phase,
            "mash_in_heat_strategy_delta_to_target": gate_delta,
            "heat_strike_phase": clean_phase,
            "heat_strike_delta_to_target": gate_delta,
            "heat_strike_safety_delta_to_target": safety_delta,
            "heat_strike_control_target": target,
            "heat_strike_clean_control_target": target,
            "heat_strike_transition_low_hold_floor_active": False,
            "control_reason": (
                f"{original_reason} Clean heat-strike control: mash/BLE gate remains primary for readiness; "
                f"gate temp {gate_temp}°C ({gate_source}), gate delta {gate_delta}°C; "
                f"safety temp {safety_temp}°C ({safety_source}), safety delta {safety_delta}°C; "
                f"heat {round(float(clean_heat), 1)}% ({clean_phase}; gate {gate_heat}%, cap {safety_cap}%), "
                f"pump {round(float(clean_pump), 1)}% ({pump_reason})."
            ),
        }
    )
    return out


def _with_clean_heatstrike(hass: HomeAssistant, snapshot: dict[str, Any]) -> dict[str, Any]:
    assert _ORIGINAL_WITH_ADVICE is not None
    out = _ORIGINAL_WITH_ADVICE(hass, snapshot)
    return _apply_clean_heatstrike(out)


def install_clean_heat_strike_guard() -> None:
    """Install final clean heat-strike guard."""
    global _INSTALLED, _ORIGINAL_WITH_ADVICE
    if _INSTALLED:
        return
    _ORIGINAL_WITH_ADVICE = advice_control._with_advice
    advice_control._with_advice = _with_clean_heatstrike
    _INSTALLED = True
