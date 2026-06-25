"""Explicit BrewZilla mash-ramp heat strategy.

Brewfather exposes short mash ramp steps as ordinary mash tracker steps. The
base mash-hold strategy therefore treated ramps like gentle recovery/hold and
used 55% heat utilization. That is safe, but too soft for short 2 minute ramps:
BrewZilla may enter the following hold before the target has been reached.

This patch keeps the existing hold behaviour, but gives true ramp steps their
own strategy:

- far from target: 100% heat, pump on for circulation
- approaching target: 75% heat, pump on
- at/above target: heat off, pump on
"""

from __future__ import annotations

from typing import Any

from . import brewzilla_orchestration as _base

_BASE_MASH_HOLD_STRATEGY = None
_INSTALLED = False

MASH_RAMP_FAR_MARGIN_C = 2.0
MASH_RAMP_APPROACH_MARGIN_C = 0.5
MASH_RAMP_FAR_HEAT_UTILIZATION = 100.0
MASH_RAMP_APPROACH_HEAT_UTILIZATION = 75.0
MASH_RAMP_AT_TARGET_HEAT_UTILIZATION = 0.0
MASH_RAMP_PUMP_UTILIZATION = 50.0

_RAMP_WORDS = (
    "ramp",
    "värm upp",
    "värm mäsken",
    "värm mäskvattnet",
    "heat up",
    "heat mash",
)


def _current_stage_text(runtime: dict[str, Any]) -> str:
    return f"{runtime.get('stage') or ''} {runtime.get('step') or ''} {runtime.get('raw_step_name') or ''}".lower()


def _stage_is_mash_ramp(runtime: dict[str, Any]) -> bool:
    text = _current_stage_text(runtime)
    if not text.strip():
        return False
    if _base._stage_is_boil(runtime):
        return False
    if not any(word in text for word in _base._MASH_WORDS):
        return False
    return any(word in text for word in _RAMP_WORDS)


def _mash_ramp_strategy(
    runtime: dict[str, Any],
    *,
    current_temperature: float | None,
    requested_target: float | None,
) -> dict[str, Any]:
    if not _stage_is_mash_ramp(runtime) or current_temperature is None or requested_target is None:
        return _base._inactive_strategy()

    delta_to_target = requested_target - current_temperature
    if delta_to_target > MASH_RAMP_FAR_MARGIN_C:
        phase = "mash_ramp_far"
        desired_heat_utilization = MASH_RAMP_FAR_HEAT_UTILIZATION
        desired_heater_on = True
        reason = "Mash ramp: far from target; heat 100% and circulate to reach next hold."
    elif delta_to_target > MASH_RAMP_APPROACH_MARGIN_C:
        phase = "mash_ramp_approach"
        desired_heat_utilization = MASH_RAMP_APPROACH_HEAT_UTILIZATION
        desired_heater_on = True
        reason = "Mash ramp: approaching target; taper heat to 75% and circulate."
    elif current_temperature > requested_target + _base.MASH_HOLD_UPPER_MARGIN_C:
        phase = "mash_ramp_overshoot"
        desired_heat_utilization = MASH_RAMP_AT_TARGET_HEAT_UTILIZATION
        desired_heater_on = False
        reason = "Mash ramp: above target; heat OFF while temperature settles."
    else:
        phase = "mash_ramp_at_target"
        desired_heat_utilization = MASH_RAMP_AT_TARGET_HEAT_UTILIZATION
        desired_heater_on = False
        reason = "Mash ramp: target reached; heat OFF before hold."

    return {
        "active": True,
        "phase": phase,
        "delta_to_target": round(delta_to_target, 2),
        "desired_heat_utilization": desired_heat_utilization,
        "desired_pump_utilization": MASH_RAMP_PUMP_UTILIZATION,
        "desired_heater_on": desired_heater_on,
        "desired_pump_on": True,
        "mash_in_confirmation_recommended": False,
        "reason": reason,
        "strategy": "mash_ramp",
    }


def _mash_hold_strategy(
    runtime: dict[str, Any],
    *,
    runtime_state: str,
    current_temperature: float | None,
    requested_target: float | None,
) -> dict[str, Any]:
    ramp = _mash_ramp_strategy(
        runtime,
        current_temperature=current_temperature,
        requested_target=requested_target,
    )
    if ramp.get("active"):
        return ramp

    assert _BASE_MASH_HOLD_STRATEGY is not None
    return _BASE_MASH_HOLD_STRATEGY(
        runtime,
        runtime_state=runtime_state,
        current_temperature=current_temperature,
        requested_target=requested_target,
    )


def install_mash_ramp_strategy() -> None:
    global _BASE_MASH_HOLD_STRATEGY, _INSTALLED
    if _INSTALLED:
        return
    _BASE_MASH_HOLD_STRATEGY = _base._mash_hold_strategy
    _base._mash_hold_strategy = _mash_hold_strategy
    _INSTALLED = True
