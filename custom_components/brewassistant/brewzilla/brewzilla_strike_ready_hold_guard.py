"""Ready-wait hold guard for BrewZilla pre-mash-in heat-strike.

Once the strike target has been reached, the brewer may still need time to mash
in.  During that supervised wait BA should not forget the strike target or drop
straight to 0% heat unless there is a real overshoot/safety reason.  This module
keeps a small hysteresis/hold profile around the latched strike target until
mash-in starts.
"""

from __future__ import annotations

from typing import Any

from . import brewzilla_heat_strike_profile as heat_strike

_INSTALLED = False
_ORIGINAL_HEAT_STRIKE_CONTROL_PROFILE = None

_READY_WAIT_HOLD_HEAT_UTILIZATION = 25.0
_READY_WAIT_LOW_HOLD_HEAT_UTILIZATION = 15.0
_READY_WAIT_COAST_OVERSHOOT_C = 1.0
_READY_WAIT_HOLD_BAND_BELOW_C = 0.5
_READY_WAIT_HOLD_BAND_ABOVE_C = 0.3
_FAST_RISE_MIN_HOLD_HEAT_UTILIZATION = 20.0


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _strike_ready_hold_profile(
    strike_target: float,
    current_temperature: float | None,
    temp_rate: float | None,
) -> tuple[float, float, bool, str, float | None]:
    """Keep a modest hold profile while waiting for mash-in.

    The base heat-strike profile is intentionally aggressive on the way up, but
    once the target is reached it can enter a coast/off branch.  That is fine for
    true overshoot, not for a supervised mash-in wait where the operator expects
    the strike temperature to be held.
    """
    assert _ORIGINAL_HEAT_STRIKE_CONTROL_PROFILE is not None
    if current_temperature is None:
        return _ORIGINAL_HEAT_STRIKE_CONTROL_PROFILE(strike_target, current_temperature, temp_rate)

    delta = round(float(strike_target) - float(current_temperature), 2)

    # True overshoot: let the system coast until it falls back toward the band.
    if delta < -_READY_WAIT_COAST_OVERSHOOT_C:
        return (
            round(float(strike_target), 1),
            0.0,
            False,
            "strike_ready_wait_true_overshoot_coast",
            delta,
        )

    # Slight overshoot around target is still a wait/hold state, not a forgotten
    # heat-strike state.  Keep a very low utilization so BA can re-arm instead of
    # staying at hard 0% through the mash-in pause.
    if delta < -_READY_WAIT_HOLD_BAND_ABOVE_C:
        return (
            round(float(strike_target), 1),
            _READY_WAIT_LOW_HOLD_HEAT_UTILIZATION,
            True,
            "strike_ready_wait_low_hold",
            delta,
        )

    # Inside the ready band: hold gently.  If the selected strike sensor is still
    # rising quickly, use the existing low minimum hold instead of the normal hold.
    if delta <= _READY_WAIT_HOLD_BAND_BELOW_C:
        if temp_rate is not None and temp_rate > heat_strike._STRIKE_FAST_FINAL_RATE_C_PER_MIN:
            return (
                round(float(strike_target), 1),
                _FAST_RISE_MIN_HOLD_HEAT_UTILIZATION,
                True,
                "strike_ready_wait_fast_rise_min_hold",
                delta,
            )
        return (
            round(float(strike_target), 1),
            _READY_WAIT_HOLD_HEAT_UTILIZATION,
            True,
            "strike_ready_wait_hold",
            delta,
        )

    return _ORIGINAL_HEAT_STRIKE_CONTROL_PROFILE(strike_target, current_temperature, temp_rate)


def install_strike_ready_hold_guard() -> None:
    """Install ready-wait hold behavior after heat-strike profile setup."""
    global _INSTALLED, _ORIGINAL_HEAT_STRIKE_CONTROL_PROFILE
    if _INSTALLED:
        return

    _ORIGINAL_HEAT_STRIKE_CONTROL_PROFILE = heat_strike._heat_strike_control_profile
    heat_strike._heat_strike_control_profile = _strike_ready_hold_profile
    _INSTALLED = True
