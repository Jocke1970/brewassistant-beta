"""Dynamic mash/wort delta pump mixing for BrewZilla.

The base BrewZilla profile keeps real-mash pump utilization conservative to avoid
malt-bed compaction. During observed stratification, however, a large gap
between the mash/BLE probe and the internal/wort probe usually means the system
needs stronger circulation until the two readings converge.

This patch raises the requested pump utilization as a floor based on wort-mash
delta. It never lowers the normal profile, and it leaves heat decisions to the
existing advice/thermal-mix guards.
"""

from __future__ import annotations

from typing import Any

from . import brewzilla_advice_control as advice_control

_INSTALLED = False
_ORIGINAL_BASE_PUMP_PROFILE = None

_APPLICABLE_STAGES = {"ramp", "mash_hold"}

# Pump floors for real-mash stratification. The base profile can still return
# 50% when the mash and wort readings converge again.
LARGE_DELTA_C = 5.0
MID_DELTA_C = 3.0
SMALL_DELTA_C = 1.5
LARGE_DELTA_PUMP = 100.0
MID_DELTA_PUMP = 90.0
SMALL_DELTA_PUMP = 80.0


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _context(advice: dict[str, Any]) -> str:
    context = str(advice.get("learning_context") or "Unknown")
    return context if context in {"Water only", "Real mash"} else "Unknown"


def _mash_wort_delta_pump_floor(advice: dict[str, Any]) -> tuple[float | None, str | None, float | None]:
    if _context(advice) != "Real mash":
        return None, None, None

    mash = _num(advice.get("mash_temperature"))
    wort = _num(advice.get("wort_temperature"))
    if mash is None or wort is None:
        return None, None, None

    # Positive value means wort/internal is hotter than mash/BLE.
    mash_wort_delta = round(wort - mash, 2)
    if mash_wort_delta >= LARGE_DELTA_C:
        return LARGE_DELTA_PUMP, "mash_wort_delta_large_mix", mash_wort_delta
    if mash_wort_delta >= MID_DELTA_C:
        return MID_DELTA_PUMP, "mash_wort_delta_mid_mix", mash_wort_delta
    if mash_wort_delta >= SMALL_DELTA_C:
        return SMALL_DELTA_PUMP, "mash_wort_delta_small_mix", mash_wort_delta
    return None, None, mash_wort_delta


def _base_pump_profile(advice: dict[str, Any], stage_kind: str, delta: float | None) -> tuple[bool | None, float | None, str | None]:
    assert _ORIGINAL_BASE_PUMP_PROFILE is not None
    pump_on, pump_utilization, pump_phase = _ORIGINAL_BASE_PUMP_PROFILE(advice, stage_kind, delta)

    if stage_kind not in _APPLICABLE_STAGES:
        return pump_on, pump_utilization, pump_phase

    floor, reason, _mash_wort_delta = _mash_wort_delta_pump_floor(advice)
    if floor is None or reason is None:
        return pump_on, pump_utilization, pump_phase

    current = _num(pump_utilization)
    if current is not None and current >= floor:
        return pump_on, pump_utilization, pump_phase

    return True, floor, reason


def install_mash_wort_delta_pump_guard() -> None:
    """Install delta-driven real-mash pump mixing."""
    global _INSTALLED, _ORIGINAL_BASE_PUMP_PROFILE
    if _INSTALLED:
        return

    _ORIGINAL_BASE_PUMP_PROFILE = advice_control._base_pump_profile
    advice_control._base_pump_profile = _base_pump_profile
    _INSTALLED = True
