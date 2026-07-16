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

# Only extreme internal/wort heat should keep the very low 5% cap while the mash
# is still far below target.  Smaller wort overshoots during a real mash ramp are
# usually stratification/malt-pipe lag and should mainly request more mixing.
EXTREME_WORT_OVER_TARGET_C = 5.0
MASH_PRIORITY_RAMP_GAP_C = 2.0
MASH_PRIORITY_HOLD_GAP_C = 2.0
MASH_PRIORITY_RAMP_HEAT_CAP = 45.0
MASH_PRIORITY_HOLD_HEAT_CAP = 30.0


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _mash_priority_cap(
    result: dict[str, Any],
    *,
    stage_kind: str,
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
        }

    if stage_kind == "ramp" and mash_gap >= MASH_PRIORITY_RAMP_GAP_C:
        original_cap = _num(result.get("heat_cap"))
        cap = MASH_PRIORITY_RAMP_HEAT_CAP if original_cap is None else max(original_cap, MASH_PRIORITY_RAMP_HEAT_CAP)
        return {
            **result,
            "heat_cap": cap,
            "severity": "mash_priority_ramp",
            "reason": "mash_priority_ramp_mix",
            "mash_priority_heat_cap_active": True,
            "mash_priority_heat_cap_reason": "mash_temperature_lags_during_ramp",
            "mash_priority_original_heat_cap": original_cap,
        }

    if stage_kind == "mash_hold" and mash_gap >= MASH_PRIORITY_HOLD_GAP_C:
        original_cap = _num(result.get("heat_cap"))
        cap = MASH_PRIORITY_HOLD_HEAT_CAP if original_cap is None else max(original_cap, MASH_PRIORITY_HOLD_HEAT_CAP)
        return {
            **result,
            "heat_cap": cap,
            "severity": "mash_priority_hold",
            "reason": "mash_priority_hold_mix",
            "mash_priority_heat_cap_active": True,
            "mash_priority_heat_cap_reason": "mash_temperature_lags_during_hold",
            "mash_priority_original_heat_cap": original_cap,
        }

    return {
        **result,
        "mash_priority_heat_cap_active": False,
        "mash_priority_heat_cap_reason": "mash_near_target_kept_original_cap",
    }


def _thermal_mix_modifier(advice: dict[str, Any], target: float | None, stage_kind: str) -> dict[str, Any]:
    assert _ORIGINAL_THERMAL_MIX_MODIFIER is not None
    result = _ORIGINAL_THERMAL_MIX_MODIFIER(advice, target, stage_kind)
    return _mash_priority_cap(result, stage_kind=stage_kind)


def install_mash_priority_thermal_mix_guard() -> None:
    """Install mash-priority tuning for ramp/hold thermal-mix capping."""
    global _INSTALLED, _ORIGINAL_THERMAL_MIX_MODIFIER
    if _INSTALLED:
        return

    _ORIGINAL_THERMAL_MIX_MODIFIER = advice_control._thermal_mix_modifier
    advice_control._thermal_mix_modifier = _thermal_mix_modifier
    _INSTALLED = True
