"""Final clean heat-strike guard for BrewZilla.

This guard makes the physical pre-mash-in heat-strike phase dominant over the
Brewfather paused/hold step.  While mash-in has not started, control decisions
should be based on the strike-water/kettle view, not on a cold mash/BLE gate
probe or the next Brewfather mash hold.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.core import HomeAssistant

from . import brewzilla_advice_control as advice_control

_INSTALLED = False
_ORIGINAL_WITH_ADVICE: Callable[[HomeAssistant, dict[str, Any]], dict[str, Any]] | None = None

_ACTIVE_STATES = {"live", "running", "paused", "awaiting_snapshot", "prepared", "awaiting_confirm"}

# Heat profile for the physical strike-water phase.  Far from strike we keep the
# heat-strike ramp decisive; close to strike we taper from the hottest kettle/wort
# view.  The mash/BLE probe is allowed only as a fallback temperature, never as a
# reason to keep heat alive when the kettle/wort view is already near strike.
_CLEAN_HEAT_PROFILE: tuple[tuple[float, float, bool, str], ...] = (
    (1.0, 0.0, False, "clean_strike_final_coast"),
    (3.0, 10.0, True, "clean_strike_final_low_hold"),
    (5.0, 25.0, True, "clean_strike_capture"),
    (8.0, 50.0, True, "clean_strike_approach"),
    (10.0, 75.0, True, "clean_strike_late_ramp"),
)
_CLEAN_FAR_HEAT = 100.0
_CLEAN_FAR_PHASE = "clean_strike_far_ramp"

# Pump floors during heat-strike.  The pump is used for water/kettle mixing here;
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


def _guard_temperature(out: dict[str, Any]) -> tuple[float | None, str | None]:
    """Return strike-water guard temp.

    Prefer kettle/wort/internal readings.  Use mash/BLE only as a fallback if no
    kettle/wort view exists.  This prevents a cold external probe from forcing a
    low-hold/heat-alive branch while the actual strike water is already close.
    """
    primary_candidates: list[tuple[str, float]] = []
    for key in (
        "current_temperature",
        "brewzilla_current_temp",
        "wort_temperature",
        "heat_strike_transition_brake_temperature",
        "advice_learning_temperature",
    ):
        value = _num(out.get(key))
        if value is not None:
            primary_candidates.append((key, value))
    if primary_candidates:
        source, value = max(primary_candidates, key=lambda item: item[1])
        return value, source

    for key in ("mash_temperature", "mash_in_gate_current_temperature"):
        value = _num(out.get(key))
        if value is not None:
            return value, key
    return None, None


def _heat_for_delta(delta: float | None) -> tuple[float | None, bool | None, str | None]:
    if delta is None:
        return None, None, None
    for threshold, heat, heater_on, phase in _CLEAN_HEAT_PROFILE:
        if delta <= threshold:
            return heat, heater_on, phase
    return _CLEAN_FAR_HEAT, True, _CLEAN_FAR_PHASE


def _mash_wort_delta(out: dict[str, Any]) -> float | None:
    mash = _num(out.get("mash_temperature"))
    wort = _num(out.get("wort_temperature"))
    if mash is None or wort is None:
        return None
    return round(float(wort) - float(mash), 2)


def _pump_for_conditions(out: dict[str, Any], strike_delta: float | None) -> tuple[float, str, float | None]:
    mw_delta = _mash_wort_delta(out)
    if mw_delta is not None:
        if mw_delta >= _DELTA_PUMP_LARGE_C:
            return _PUMP_READY, "clean_strike_mash_wort_large_mix", mw_delta
        if mw_delta >= _DELTA_PUMP_MID_C:
            return _PUMP_NEAR, "clean_strike_mash_wort_mid_mix", mw_delta
        if mw_delta >= _DELTA_PUMP_SMALL_C:
            return 80.0, "clean_strike_mash_wort_small_mix", mw_delta

    if strike_delta is not None and strike_delta <= 3.0:
        return _PUMP_READY, "clean_strike_near_target_equalize", mw_delta
    if strike_delta is not None and strike_delta <= 8.0:
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

    guard_temp, guard_source = _guard_temperature(out)
    strike_delta = None if guard_temp is None else round(float(strike) - float(guard_temp), 2)
    clean_heat, clean_heater_on, clean_phase = _heat_for_delta(strike_delta)
    if clean_heat is None or clean_heater_on is None or clean_phase is None:
        out.setdefault("clean_heat_strike_active", False)
        return out

    pump_floor, pump_reason, mw_delta = _pump_for_conditions(out, strike_delta)
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
            "clean_heat_strike_guard_temperature": guard_temp,
            "clean_heat_strike_guard_temperature_source": guard_source,
            "clean_heat_strike_delta_to_target": strike_delta,
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
            "mash_in_heat_strategy_delta_to_target": strike_delta,
            "heat_strike_phase": clean_phase,
            "heat_strike_delta_to_target": strike_delta,
            "heat_strike_control_target": target,
            "heat_strike_clean_control_target": target,
            "heat_strike_transition_low_hold_floor_active": False,
            "control_reason": (
                f"{original_reason} Clean heat-strike control: physical pre-mash-in phase is dominant; "
                f"guard temp {guard_temp}°C ({guard_source}), strike target {target}°C, "
                f"delta {strike_delta}°C; heat {round(float(clean_heat), 1)}% ({clean_phase}), "
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
