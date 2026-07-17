"""Mash-priority thermal-mix tuning for BrewZilla ramp control.

The base advice profile correctly uses mash/BLE temperature as the primary
learning temperature for mash ramps and holds.  The thermal-mix modifier is a
safety layer for stratification: it should increase circulation and limit heat
when the internal/wort sensor is hot, but it should not treat a warm internal
sensor as the mash target while the measured mash still lags several degrees.
"""

from __future__ import annotations

from typing import Any

from . import brewzilla_advice_control as advice_control

_INSTALLED = False
_ORIGINAL_THERMAL_MIX_MODIFIER = None

# Only extreme internal/wort heat should keep the very low original 5-10% cap
# while the mash is still far below target.  Smaller wort overshoots during a
# real mash ramp are usually stratification/malt-pipe lag and should mainly
# request more mixing.
EXTREME_WORT_OVER_TARGET_C = 5.0

# Dynamic real-mash ramp floor.  Heat can be high early in a ramp while the mash
# is far from target, then taper as the mash approaches target.  BrewZilla still
# regulates locally at the target temperature; this only prevents BA's
# thermal-mix safety layer from collapsing heat too early.
MASH_PRIORITY_RAMP_FAR_GAP_C = 5.0
MASH_PRIORITY_RAMP_MID_GAP_C = 3.0
MASH_PRIORITY_RAMP_NEAR_GAP_C = 2.0
MASH_PRIORITY_RAMP_FAR_HEAT_CAP = 75.0
MASH_PRIORITY_RAMP_MID_HEAT_CAP = 60.0
MASH_PRIORITY_RAMP_NEAR_HEAT_CAP = 45.0

# Rate-aware ramp correction.  This uses the learning temperature rate, which is
# the mash/BLE probe during ramp and mash-hold stages.  Larger volumes or weaker
# heat transfer usually show a slower C/min rate and need a higher cap; smaller
# volumes and fast-rising ramps should taper earlier.
MASH_PRIORITY_RAMP_VERY_SLOW_RATE_C_PER_MIN = 0.10
MASH_PRIORITY_RAMP_SLOW_RATE_C_PER_MIN = 0.20
MASH_PRIORITY_RAMP_FAST_RATE_C_PER_MIN = 0.60
MASH_PRIORITY_RAMP_VERY_FAST_RATE_C_PER_MIN = 1.00
MASH_PRIORITY_RAMP_SLOW_BOOST = 10.0
MASH_PRIORITY_RAMP_VERY_SLOW_BOOST = 15.0
MASH_PRIORITY_RAMP_SLOW_MAX_CAP = 85.0
MASH_PRIORITY_RAMP_VERY_SLOW_MAX_CAP = 90.0
MASH_PRIORITY_RAMP_FAST_CAP = 45.0
MASH_PRIORITY_RAMP_VERY_FAST_CAP = 25.0

# Thermal-mix should also increase circulation when the internal/wort side is
# hot.  During a hot-wort / mash-lag condition, more pump usually helps collapse
# stratification and lets the mash probe tell us whether the target is really
# reached.  This is still only used when the base thermal-mix modifier is active.
MASH_PRIORITY_THERMAL_MIX_PUMP_UTILIZATION = 85.0
MASH_PRIORITY_HOT_WORT_MIX_PUMP_UTILIZATION = 100.0
MASH_PRIORITY_NEAR_TARGET_FAST_MIX_PUMP_UTILIZATION = 90.0
MASH_PRIORITY_HOT_WORT_OVER_TARGET_C = 1.0
MASH_PRIORITY_NEAR_TARGET_MASH_GAP_C = 2.0

# Holds should recover more gently than ramps, but still not collapse to a 5-10%
# cap while the measured mash remains several degrees below target.
MASH_PRIORITY_HOLD_FAR_GAP_C = 5.0
MASH_PRIORITY_HOLD_MID_GAP_C = 3.0
MASH_PRIORITY_HOLD_NEAR_GAP_C = 2.0
MASH_PRIORITY_HOLD_FAR_HEAT_CAP = 50.0
MASH_PRIORITY_HOLD_MID_HEAT_CAP = 40.0
MASH_PRIORITY_HOLD_NEAR_HEAT_CAP = 30.0


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _ramp_cap_for_gap(mash_gap: float) -> tuple[float | None, str | None]:
    if mash_gap >= MASH_PRIORITY_RAMP_FAR_GAP_C:
        return MASH_PRIORITY_RAMP_FAR_HEAT_CAP, "ramp_far_mash_gap"
    if mash_gap >= MASH_PRIORITY_RAMP_MID_GAP_C:
        return MASH_PRIORITY_RAMP_MID_HEAT_CAP, "ramp_mid_mash_gap"
    if mash_gap >= MASH_PRIORITY_RAMP_NEAR_GAP_C:
        return MASH_PRIORITY_RAMP_NEAR_HEAT_CAP, "ramp_near_mash_gap"
    return None, None


def _rate_adjusted_ramp_cap(
    floor: float,
    *,
    mash_gap: float,
    temp_rate: float | None,
) -> tuple[float, str | None]:
    if temp_rate is None:
        return floor, None

    # If mash is still far below target and rising slowly, do not let the
    # thermal-mix cap become the limiting factor.  The local BrewZilla target and
    # the extreme-wort guard remain the hard safety boundaries.
    if mash_gap >= MASH_PRIORITY_RAMP_MID_GAP_C:
        if temp_rate <= MASH_PRIORITY_RAMP_VERY_SLOW_RATE_C_PER_MIN:
            return min(MASH_PRIORITY_RAMP_VERY_SLOW_MAX_CAP, floor + MASH_PRIORITY_RAMP_VERY_SLOW_BOOST), "very_slow_rate"
        if temp_rate <= MASH_PRIORITY_RAMP_SLOW_RATE_C_PER_MIN:
            return min(MASH_PRIORITY_RAMP_SLOW_MAX_CAP, floor + MASH_PRIORITY_RAMP_SLOW_BOOST), "slow_rate"

    # If the measured mash itself is already rising quickly near target, taper
    # earlier.  This is mostly for small-volume batches or unusually efficient
    # circulation where the mash probe catches up quickly.
    if mash_gap <= MASH_PRIORITY_RAMP_MID_GAP_C:
        if temp_rate >= MASH_PRIORITY_RAMP_VERY_FAST_RATE_C_PER_MIN:
            return min(floor, MASH_PRIORITY_RAMP_VERY_FAST_CAP), "very_fast_rate_taper"
        if temp_rate >= MASH_PRIORITY_RAMP_FAST_RATE_C_PER_MIN:
            return min(floor, MASH_PRIORITY_RAMP_FAST_CAP), "fast_rate_taper"

    return floor, None


def _thermal_mix_pump_for_conditions(
    *,
    stage_kind: str,
    mash_gap: float,
    wort_over: float,
    temp_rate: float | None,
) -> tuple[float, str]:
    if wort_over >= MASH_PRIORITY_HOT_WORT_OVER_TARGET_C:
        return MASH_PRIORITY_HOT_WORT_MIX_PUMP_UTILIZATION, "hot_wort_mix"
    if (
        stage_kind == "ramp"
        and mash_gap <= MASH_PRIORITY_NEAR_TARGET_MASH_GAP_C
        and temp_rate is not None
        and temp_rate >= MASH_PRIORITY_RAMP_FAST_RATE_C_PER_MIN
    ):
        return MASH_PRIORITY_NEAR_TARGET_FAST_MIX_PUMP_UTILIZATION, "near_target_fast_mix"
    return MASH_PRIORITY_THERMAL_MIX_PUMP_UTILIZATION, "thermal_mix"


def _hold_cap_for_gap(mash_gap: float) -> tuple[float | None, str | None]:
    if mash_gap >= MASH_PRIORITY_HOLD_FAR_GAP_C:
        return MASH_PRIORITY_HOLD_FAR_HEAT_CAP, "hold_far_mash_gap"
    if mash_gap >= MASH_PRIORITY_HOLD_MID_GAP_C:
        return MASH_PRIORITY_HOLD_MID_HEAT_CAP, "hold_mid_mash_gap"
    if mash_gap >= MASH_PRIORITY_HOLD_NEAR_GAP_C:
        return MASH_PRIORITY_HOLD_NEAR_HEAT_CAP, "hold_near_mash_gap"
    return None, None


def _raise_cap(
    result: dict[str, Any],
    *,
    floor: float,
    severity: str,
    reason: str,
    temp_rate: float | None,
    pump_utilization: float | None = None,
    pump_reason: str | None = None,
    rate_reason: str | None = None,
) -> dict[str, Any]:
    original_cap = _num(result.get("heat_cap"))
    cap = floor if original_cap is None else max(original_cap, floor)
    original_pump = _num(result.get("pump_utilization"))
    pump = original_pump
    if pump_utilization is not None:
        pump = pump_utilization if original_pump is None else max(original_pump, pump_utilization)
    return {
        **result,
        "heat_cap": cap,
        "pump_utilization": pump,
        "severity": severity,
        "reason": reason,
        "mash_priority_heat_cap_active": True,
        "mash_priority_heat_cap_reason": "mash_temperature_lags_more_than_wort_safety_requires",
        "mash_priority_original_heat_cap": original_cap,
        "mash_priority_dynamic_floor": floor,
        "mash_priority_rate_c_per_min": temp_rate,
        "mash_priority_rate_reason": rate_reason,
        "mash_priority_pump_utilization": pump,
        "mash_priority_original_pump_utilization": original_pump,
        "mash_priority_pump_reason": pump_reason,
    }


def _mash_priority_cap(
    result: dict[str, Any],
    *,
    stage_kind: str,
    temp_rate: float | None,
) -> dict[str, Any]:
    if not result.get("active"):
        return result

    mash_gap = _num(result.get("mash_gap_to_target"))
    wort_over = _num(result.get("wort_over_target"))
    if mash_gap is None or wort_over is None:
        return result

    if wort_over >= EXTREME_WORT_OVER_TARGET_C:
        return {
            **result,
            "mash_priority_heat_cap_active": False,
            "mash_priority_heat_cap_reason": "extreme_wort_over_target_kept_original_cap",
            "mash_priority_rate_c_per_min": temp_rate,
        }

    pump_utilization, pump_reason = _thermal_mix_pump_for_conditions(
        stage_kind=stage_kind,
        mash_gap=mash_gap,
        wort_over=wort_over,
        temp_rate=temp_rate,
    )

    if stage_kind == "ramp":
        floor, band = _ramp_cap_for_gap(mash_gap)
        if floor is not None and band is not None:
            adjusted_floor, rate_reason = _rate_adjusted_ramp_cap(floor, mash_gap=mash_gap, temp_rate=temp_rate)
            severity = f"mash_priority_{band}" if rate_reason is None else f"mash_priority_{band}_{rate_reason}"
            return _raise_cap(
                result,
                floor=adjusted_floor,
                severity=severity,
                reason="mash_priority_ramp_mix",
                temp_rate=temp_rate,
                pump_utilization=pump_utilization,
                pump_reason=pump_reason,
                rate_reason=rate_reason,
            )

    if stage_kind == "mash_hold":
        floor, band = _hold_cap_for_gap(mash_gap)
        if floor is not None and band is not None:
            return _raise_cap(
                result,
                floor=floor,
                severity=f"mash_priority_{band}",
                reason="mash_priority_hold_mix",
                temp_rate=temp_rate,
                pump_utilization=pump_utilization,
                pump_reason=pump_reason,
            )

    return {
        **result,
        "mash_priority_heat_cap_active": False,
        "mash_priority_heat_cap_reason": "mash_near_target_kept_original_cap",
        "mash_priority_rate_c_per_min": temp_rate,
    }


def _thermal_mix_modifier(advice: dict[str, Any], target: float | None, stage_kind: str) -> dict[str, Any]:
    assert _ORIGINAL_THERMAL_MIX_MODIFIER is not None
    result = _ORIGINAL_THERMAL_MIX_MODIFIER(advice, target, stage_kind)
    temp_rate = _num(advice.get("temp_rate_c_per_min"))
    return _mash_priority_cap(result, stage_kind=stage_kind, temp_rate=temp_rate)


def install_mash_priority_thermal_mix_guard() -> None:
    """Install mash-priority tuning for ramp/hold thermal-mix capping."""
    global _INSTALLED, _ORIGINAL_THERMAL_MIX_MODIFIER
    if _INSTALLED:
        return

    _ORIGINAL_THERMAL_MIX_MODIFIER = advice_control._thermal_mix_modifier
    advice_control._thermal_mix_modifier = _thermal_mix_modifier
    _INSTALLED = True
