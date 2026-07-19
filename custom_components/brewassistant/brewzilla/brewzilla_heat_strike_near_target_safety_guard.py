"""Near-target heat-strike safety caps for BrewZilla.

Heat-strike can ramp aggressively while far below strike, but once the kettle or
wort temperature is close to strike the applied heat utilization must taper even
if the mash/BLE probe still lags behind.  This guard is intentionally installed
after the heat-strike and transition guards so it can act as a final safety cap
on the heat command.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.core import HomeAssistant

from . import brewzilla_advice_control as advice_control

_INSTALLED = False
_ORIGINAL_WITH_ADVICE: Callable[[HomeAssistant, dict[str, Any]], dict[str, Any]] | None = None

_ACTIVE_OR_PAUSED_STATES = {"live", "running", "paused", "awaiting_snapshot", "prepared", "awaiting_confirm"}

# Conservative heat caps based on the hottest available kettle/wort view.
# These are intentionally lower than the generic mash-ramp profile because
# BrewZilla already has the real strike target locally and can coast/regulate.
_NEAR_STRIKE_CAPS: tuple[tuple[float, float, bool, str], ...] = (
    (-0.10, 0.0, False, "strike_over_target_coast"),
    (0.70, 0.0, False, "strike_final_coast"),
    (1.50, 10.0, True, "strike_final_low_hold"),
    (3.00, 25.0, True, "strike_capture_low_hold"),
    (5.00, 50.0, True, "strike_approach_cap"),
)
_FAST_RISE_C_PER_MIN = 1.0
_FAST_RISE_CAP_WHEN_WITHIN_C = 8.0
_FAST_RISE_HEAT_CAP = 50.0


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _runtime_state(out: dict[str, Any]) -> str:
    return str(out.get("brewday_state") or "idle").strip().lower()


def _guard_temperature(out: dict[str, Any]) -> tuple[float | None, str | None]:
    """Return the hottest useful near-strike guard temperature.

    Before mash-in, the BLE/mash probe can lag far behind the hot wort/kettle
    sensor.  To avoid overshoot we cap heat from the hottest available control
    view, not from the coldest probe.
    """
    candidates: list[tuple[str, float]] = []
    for key in (
        "current_temperature",
        "wort_temperature",
        "advice_learning_temperature",
        "mash_temperature",
    ):
        value = _num(out.get(key))
        if value is not None:
            candidates.append((key, value))
    if not candidates:
        return None, None
    source, value = max(candidates, key=lambda item: item[1])
    return value, source


def _cap_for_delta(delta: float, rate: float | None) -> tuple[float | None, bool | None, str | None]:
    if rate is not None and rate >= _FAST_RISE_C_PER_MIN and delta <= _FAST_RISE_CAP_WHEN_WITHIN_C:
        return _FAST_RISE_HEAT_CAP, True, "strike_fast_rise_cap"
    for threshold, cap, heater_on, reason in _NEAR_STRIKE_CAPS:
        if delta <= threshold:
            return cap, heater_on, reason
    return None, None, None


def _apply_heat_strike_near_target_safety(out: dict[str, Any]) -> dict[str, Any]:
    if not out.get("heat_strike_latch_active") or out.get("completed_runtime") or out.get("abort_lockout_active"):
        return out

    strike_target = _num(out.get("heat_strike_target") or out.get("heat_strike_gate_target"))
    desired_heat = _num(out.get("desired_heat_utilization"))
    if strike_target is None or desired_heat is None:
        return out

    guard_temp, guard_source = _guard_temperature(out)
    if guard_temp is None:
        return out

    delta = round(float(strike_target) - float(guard_temp), 2)
    rate = _num(out.get("advice_temp_rate_c_per_min"))
    cap, desired_heater_on, reason = _cap_for_delta(delta, rate)
    if cap is None or reason is None:
        return out

    capped_heat = min(float(desired_heat), float(cap))
    if abs(capped_heat - float(desired_heat)) <= advice_control.base.UTILIZATION_TOLERANCE:
        return out

    heat_utilization = _num(out.get("heat_utilization"))
    heater_on = bool(out.get("heater_on"))
    heat_action_needed = advice_control.base._utilization_action_needed(heat_utilization, capped_heat)
    heater_action_needed = bool(desired_heater_on is True and not heater_on)
    heater_stop_needed = bool(desired_heater_on is False and heater_on)

    action_needed = bool(
        out.get("target_sync_needed")
        or heat_action_needed
        or heater_action_needed
        or heater_stop_needed
        or out.get("pump_action_needed")
        or out.get("pump_stop_needed")
        or out.get("pump_utilization_action_needed")
    )
    can_apply = bool(
        out.get("connected")
        and action_needed
        and not out.get("abort_lockout_active")
        and _runtime_state(out) in _ACTIVE_OR_PAUSED_STATES
        and not out.get("completed_runtime")
    )

    previous_reason = str(out.get("control_reason") or "BrewZilla heat-strike control active.")
    out.update(
        {
            "desired_heat_utilization": capped_heat,
            "desired_heater_on": desired_heater_on,
            "heating_needed": bool(capped_heat > advice_control.base.UTILIZATION_TOLERANCE),
            "heat_utilization_action_needed": heat_action_needed,
            "heater_action_needed": heater_action_needed,
            "heater_stop_needed": heater_stop_needed,
            "can_apply_target": can_apply,
            "orchestration_mode": "direct-control" if can_apply else out.get("orchestration_mode"),
            "advice_capped_heat_utilization": capped_heat,
            "advice_heat_cap": capped_heat,
            "advice_local_profile_heat_utilization": capped_heat,
            "heat_strike_near_target_safety_active": True,
            "heat_strike_near_target_safety_reason": reason,
            "heat_strike_near_target_safety_original_heat_utilization": desired_heat,
            "heat_strike_near_target_safety_heat_cap": cap,
            "heat_strike_near_target_safety_guard_temperature": round(float(guard_temp), 2),
            "heat_strike_near_target_safety_guard_source": guard_source,
            "heat_strike_near_target_safety_delta_to_strike": delta,
            "heat_strike_near_target_safety_rate_c_per_min": rate,
            "control_reason": (
                f"{previous_reason} Heat-strike near-target safety cap: hottest guard temp "
                f"{round(float(guard_temp), 2)}°C ({guard_source}) is {delta}°C below strike; "
                f"heat capped from {desired_heat}% to {capped_heat}% ({reason})."
            ),
        }
    )
    return out


def _with_heat_strike_near_target_safety(hass: HomeAssistant, snapshot: dict[str, Any]) -> dict[str, Any]:
    assert _ORIGINAL_WITH_ADVICE is not None
    out = _ORIGINAL_WITH_ADVICE(hass, snapshot)
    return _apply_heat_strike_near_target_safety(out)


def install_heat_strike_near_target_safety_guard() -> None:
    """Install final heat-strike near-target safety cap."""
    global _INSTALLED, _ORIGINAL_WITH_ADVICE
    if _INSTALLED:
        return

    _ORIGINAL_WITH_ADVICE = advice_control._with_advice
    advice_control._with_advice = _with_heat_strike_near_target_safety
    _INSTALLED = True
