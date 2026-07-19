"""Heat-strike pump mixing wrapper for BrewZilla."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.core import HomeAssistant

from . import brewzilla_advice_control as advice_control

_INSTALLED = False
_ORIGINAL_WITH_ADVICE: Callable[[HomeAssistant, dict[str, Any]], dict[str, Any]] | None = None

_HEAT_STRIKE_PHASES = {
    "strike_far_boost",
    "strike_approach_boost",
    "strike_capture",
    "strike_ready_hold",
    "strike_ready_fast_rise_min_hold",
    "strike_overshoot_coast",
    "strike_unknown_temperature_boost",
}

_STRIKE_RAMP_PUMP = 70.0
_STRIKE_READY_PUMP = 80.0
_STRIKE_OVERSHOOT_PUMP = 100.0


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _heat_strike_active(out: dict[str, Any]) -> bool:
    phase = str(out.get("heat_strike_phase") or "")
    physical_phase = str(out.get("advice_physical_phase") or "")
    return bool(
        out.get("mash_in_heat_strategy_active")
        and out.get("heat_strike_latch_active")
        and physical_phase.startswith("pre_mash_in")
        and phase in _HEAT_STRIKE_PHASES
    )


def _pump_for_phase(out: dict[str, Any]) -> tuple[float, str]:
    phase = str(out.get("heat_strike_phase") or "")
    delta = _num(out.get("heat_strike_delta_to_target"))
    if phase == "strike_overshoot_coast" or (delta is not None and delta < -0.3):
        return _STRIKE_OVERSHOOT_PUMP, "strike_overshoot_equalize"
    if phase in {"strike_ready_hold", "strike_ready_fast_rise_min_hold"} or (delta is not None and abs(delta) <= 0.5):
        return _STRIKE_READY_PUMP, "strike_ready_equalize"
    return _STRIKE_RAMP_PUMP, "strike_ramp_mix"


def _with_heat_strike_pump_mix(hass: HomeAssistant, snapshot: dict[str, Any]) -> dict[str, Any]:
    assert _ORIGINAL_WITH_ADVICE is not None
    out = _ORIGINAL_WITH_ADVICE(hass, snapshot)
    if not _heat_strike_active(out):
        out.setdefault("heat_strike_pump_mix_active", False)
        return out

    pump_floor, reason = _pump_for_phase(out)
    desired = _num(out.get("desired_pump_utilization"))
    desired_pump = pump_floor if desired is None else max(float(desired), pump_floor)
    pump_util = _num(out.get("pump_utilization"))
    pump_on = bool(out.get("pump_on"))

    out.update(
        {
            "pump_recommended": True,
            "desired_pump_on": True,
            "desired_pump_utilization": desired_pump,
            "pump_action_needed": bool(not pump_on),
            "pump_stop_needed": False,
            "pump_utilization_action_needed": advice_control.base._utilization_action_needed(pump_util, desired_pump),
            "heat_strike_pump_mix_active": True,
            "heat_strike_pump_mix_reason": reason,
            "heat_strike_pump_mix_utilization": desired_pump,
        }
    )

    control_reason = str(out.get("control_reason") or "BrewZilla heat-strike control active.")
    out["control_reason"] = (
        f"{control_reason} Heat-strike pump mix active: {reason}; pump floor {desired_pump}% before mash-in."
    )
    return out


def install_heat_strike_pump_mix_guard() -> None:
    """Install heat-strike pump mixing wrapper."""
    global _INSTALLED, _ORIGINAL_WITH_ADVICE
    if _INSTALLED:
        return
    _ORIGINAL_WITH_ADVICE = advice_control._with_advice
    advice_control._with_advice = _with_heat_strike_pump_mix
    _INSTALLED = True
