"""BrewZilla mash ramp strategy."""

from __future__ import annotations

from typing import Any

from . import brewzilla_orchestration as _base

_BASE_MASH_HOLD_STRATEGY = None
_INSTALLED = False
MASH_RAMP_FAR_MARGIN_C = 2.0
MASH_RAMP_APPROACH_MARGIN_C = 0.5

_RAMP_WORDS = ("ramp", "heat up", "heat mash", "värm upp", "värm mäsken", "värm mäskvattnet")


def _current_stage_text(runtime: dict[str, Any]) -> str:
    return f"{runtime.get('stage') or ''} {runtime.get('step') or ''} {runtime.get('raw_step_name') or ''}".lower()


def _stage_is_mash_ramp(runtime: dict[str, Any]) -> bool:
    text = _current_stage_text(runtime)
    return bool(text.strip() and not _base._stage_is_boil(runtime) and any(w in text for w in _base._MASH_WORDS) and any(w in text for w in _RAMP_WORDS))


def _mash_ramp_strategy(runtime: dict[str, Any], *, current_temperature: float | None, requested_target: float | None) -> dict[str, Any]:
    if not _stage_is_mash_ramp(runtime) or current_temperature is None or requested_target is None:
        return _base._inactive_strategy()
    delta = requested_target - current_temperature
    if delta > MASH_RAMP_FAR_MARGIN_C:
        phase, heat, pump, heater_on, reason = "mash_ramp_far", 100.0, 25.0, True, "Mash ramp: far from target; heat 100% and circulate gently at 25%."
    elif delta > MASH_RAMP_APPROACH_MARGIN_C:
        phase, heat, pump, heater_on, reason = "mash_ramp_approach", 75.0, 50.0, True, "Mash ramp: approaching target; heat 75% and pump 50%."
    elif current_temperature > requested_target + _base.MASH_HOLD_UPPER_MARGIN_C:
        phase, heat, pump, heater_on, reason = "mash_ramp_overshoot", 0.0, 50.0, False, "Mash ramp: above target; heat OFF and pump 50%."
    else:
        phase, heat, pump, heater_on, reason = "mash_ramp_at_target", 0.0, 50.0, False, "Mash ramp: target reached; heat OFF and pump 50%."
    return {
        "active": True,
        "phase": phase,
        "delta_to_target": round(delta, 2),
        "desired_heat_utilization": heat,
        "desired_pump_utilization": pump,
        "desired_heater_on": heater_on,
        "desired_pump_on": True,
        "mash_in_confirmation_recommended": False,
        "reason": reason,
        "strategy": "mash_ramp",
    }


def _mash_hold_strategy(runtime: dict[str, Any], *, runtime_state: str, current_temperature: float | None, requested_target: float | None) -> dict[str, Any]:
    ramp = _mash_ramp_strategy(runtime, current_temperature=current_temperature, requested_target=requested_target)
    if ramp.get("active"):
        return ramp
    assert _BASE_MASH_HOLD_STRATEGY is not None
    return _BASE_MASH_HOLD_STRATEGY(runtime, runtime_state=runtime_state, current_temperature=current_temperature, requested_target=requested_target)


def install_mash_ramp_strategy() -> None:
    global _BASE_MASH_HOLD_STRATEGY, _INSTALLED
    if _INSTALLED:
        return
    _BASE_MASH_HOLD_STRATEGY = _base._mash_hold_strategy
    _base._mash_hold_strategy = _mash_hold_strategy
    _INSTALLED = True
