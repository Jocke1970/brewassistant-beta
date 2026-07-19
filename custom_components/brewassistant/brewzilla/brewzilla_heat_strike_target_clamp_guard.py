"""Clamp pre-mash-in heat-strike device targets to the real strike target.

Heat-strike control can use heat-utilization to ramp aggressively, but it should
not write a BrewZilla device target above the actual strike temperature. If a
later brake/safe-down write is blocked, delayed, or lost while Brewfather is
paused for mash-in additions, BrewZilla's own local regulation must still stop
at the real strike target rather than at a temporary boosted target.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from . import brewzilla_heat_strike_profile as heat_strike_profile

_INSTALLED = False
_ORIGINAL_HEAT_STRIKE_CONTROL_PROFILE: Callable[[float, float | None, float | None], tuple[float, float, bool, str, float | None]] | None = None


def _clamped_heat_strike_control_profile(
    strike_target: float,
    current_temperature: float | None,
    temp_rate: float | None,
) -> tuple[float, float, bool, str, float | None]:
    assert _ORIGINAL_HEAT_STRIKE_CONTROL_PROFILE is not None
    _control_target, heat_utilization, heater_on, phase, delta = _ORIGINAL_HEAT_STRIKE_CONTROL_PROFILE(
        strike_target,
        current_temperature,
        temp_rate,
    )

    # The heat profile may still be aggressive, but the local BrewZilla target
    # must remain the true strike target so the device can self-regulate safely
    # if HA/RCL/Brewfather state changes are delayed or blocked.
    return round(float(strike_target), 1), heat_utilization, heater_on, phase, delta


def install_heat_strike_target_clamp_guard() -> None:
    """Install pre-mash-in strike target clamp."""
    global _INSTALLED, _ORIGINAL_HEAT_STRIKE_CONTROL_PROFILE
    if _INSTALLED:
        return

    _ORIGINAL_HEAT_STRIKE_CONTROL_PROFILE = heat_strike_profile._heat_strike_control_profile
    heat_strike_profile._heat_strike_control_profile = _clamped_heat_strike_control_profile
    _INSTALLED = True
