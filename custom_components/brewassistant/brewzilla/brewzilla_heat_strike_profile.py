"""Heat-strike/water-only profile adjustments for BrewZilla.

Before mash-in there is no grain bed, so BrewAssistant should treat the ramp as
strike water heating: use the kettle/wort temperature, allow a more aggressive
heat profile, and do not apply mash/wort thermal-mix protection until there is a
real mash context.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.core import HomeAssistant

from . import brewzilla_advice_control as advice_control
from . import brewzilla_learning as learning

_INSTALLED = False
_ORIGINAL_BASE_HEAT_PROFILE: Callable[[str, float | None, float | None], tuple[float | None, str | None]] | None = None
_ORIGINAL_THERMAL_MIX_MODIFIER: Callable[[dict[str, Any], float | None, str], dict[str, Any]] | None = None
_ORIGINAL_TEMPERATURE_SOURCE_SNAPSHOT: Callable[[HomeAssistant, str], dict[str, Any]] | None = None
_ORIGINAL_BATCH_CONTEXT_SNAPSHOT: Callable[[HomeAssistant, dict[str, Any], str], dict[str, Any]] | None = None


def _heat_strike_rate_adjusted_heat(
    profile_heat: float,
    *,
    delta: float | None,
    temp_rate: float | None,
) -> tuple[float, str | None]:
    """Taper strike-water heat only in the final degree."""
    if delta is None or temp_rate is None:
        return profile_heat, None
    cap = advice_control._p("rate.near_target_heat_cap", 5.0)
    if delta <= 1.0 and temp_rate >= advice_control._p("rate.fast_c_per_min", 0.30):
        return min(profile_heat, cap), "fast_rise_final_degree"
    if delta <= 0.5 and temp_rate >= advice_control._p("rate.moderate_c_per_min", 0.10):
        return min(profile_heat, cap), "moderate_rise_final_approach"
    return profile_heat, None


def _heat_strike_base_heat_profile(
    stage_kind: str,
    delta: float | None,
    temp_rate: float | None = None,
) -> tuple[float | None, str | None]:
    """Return a tiered heat profile for strike-water ramps."""
    if stage_kind != "ramp":
        assert _ORIGINAL_BASE_HEAT_PROFILE is not None
        return _ORIGINAL_BASE_HEAT_PROFILE(stage_kind, delta, temp_rate)

    if delta is not None and delta <= 0.0:
        return advice_control._p("heat.off", 0.0), "at_or_above_target"

    if delta is None:
        profile_heat, phase = advice_control._p("heat.ramp_near", 30.0), "ramp_unknown_delta"
    elif delta > advice_control._p("delta.ramp_very_far", 20.0):
        profile_heat, phase = advice_control._p("heat.ramp_very_far", 100.0), "ramp_very_far"
    elif delta > advice_control._p("delta.ramp_far", 10.0):
        profile_heat, phase = advice_control._p("heat.ramp_far", 85.0), "ramp_far"
    elif delta > advice_control._p("delta.ramp_mid", 5.0):
        profile_heat, phase = advice_control._p("heat.ramp_mid", 65.0), "ramp_mid"
    elif delta > advice_control._p("delta.ramp_approach", 3.0):
        profile_heat, phase = advice_control._p("heat.ramp_approach", 45.0), "ramp_approach"
    elif delta > advice_control._p("delta.ramp_near", 1.0):
        profile_heat, phase = advice_control._p("heat.ramp_near", 30.0), "ramp_near"
    elif delta > advice_control._p("delta.ramp_final", 0.5):
        profile_heat, phase = advice_control._p("heat.ramp_final", 15.0), "ramp_final"
    elif delta > advice_control._p("delta.ramp_feather", 0.2):
        profile_heat, phase = advice_control._p("heat.ramp_feather", 5.0), "ramp_feather"
    else:
        profile_heat, phase = advice_control._p("heat.off", 0.0), "ramp_at_target"

    adjusted, modifier = _heat_strike_rate_adjusted_heat(profile_heat, delta=delta, temp_rate=temp_rate)
    return adjusted, modifier or phase


def _heat_strike_thermal_mix_modifier(
    advice: dict[str, Any],
    target: float | None,
    stage_kind: str,
) -> dict[str, Any]:
    """Disable mash/wort thermal-mix protection for explicit water-only runs."""
    if str(advice.get("learning_context") or "") == "Water only" and stage_kind == "ramp":
        return {
            "active": False,
            "reason": "water_only_heat_strike_no_mash_bed",
            "separate_inputs": False,
        }
    assert _ORIGINAL_THERMAL_MIX_MODIFIER is not None
    return _ORIGINAL_THERMAL_MIX_MODIFIER(advice, target, stage_kind)


def _water_only_temperature_source_snapshot(hass: HomeAssistant, stage_kind: str) -> dict[str, Any]:
    """Use BrewZilla/kettle temperature as learning temperature for water-only ramps."""
    if learning.learning_context(hass) != "Water only" or stage_kind != "ramp":
        assert _ORIGINAL_TEMPERATURE_SOURCE_SNAPSHOT is not None
        return _ORIGINAL_TEMPERATURE_SOURCE_SNAPSHOT(hass, stage_kind)

    snapshot = learning.brewzilla_temperature_snapshot(hass)
    learning_temperature = snapshot.get("wort_temperature")
    learning_entity = snapshot.get("wort_temperature_entity")
    learning_source = snapshot.get("wort_temperature_source")

    if learning_temperature is None:
        learning_temperature = snapshot.get("mash_temperature")
        learning_entity = snapshot.get("mash_temperature_entity")
        learning_source = snapshot.get("mash_temperature_source")

    return {
        "mash_temperature": snapshot.get("mash_temperature"),
        "mash_temperature_entity": snapshot.get("mash_temperature_entity"),
        "mash_temperature_source": snapshot.get("mash_temperature_source"),
        "wort_temperature": snapshot.get("wort_temperature"),
        "wort_temperature_entity": snapshot.get("wort_temperature_entity"),
        "wort_temperature_source": snapshot.get("wort_temperature_source"),
        "temperature_delta_mash_wort": snapshot.get("temperature_delta_mash_wort"),
        "learning_temperature": learning_temperature,
        "learning_temperature_entity": learning_entity,
        "learning_temperature_source": learning_source,
        "learning_temperature_role": "water_only_wort_or_kettle_temperature",
        "use_internal_sensor": None,
        "control_device_type": None,
        "control_device_mac_address": None,
    }


def _water_only_batch_context_snapshot(
    hass: HomeAssistant,
    runtime: dict[str, Any],
    stage_kind: str,
) -> dict[str, Any]:
    """Do not require grain context while the selected context is water-only."""
    assert _ORIGINAL_BATCH_CONTEXT_SNAPSHOT is not None
    snapshot = _ORIGINAL_BATCH_CONTEXT_SNAPSHOT(hass, runtime, stage_kind)
    if learning.learning_context(hass) == "Water only" and stage_kind == "ramp" and snapshot.get("needs_batch_context"):
        snapshot = dict(snapshot)
        snapshot.update(
            {
                "needs_batch_context": False,
                "batch_context_missing": [],
                "batch_context_reason": "Water-only heat-strike ramp: grain/mash context is not required before mash-in.",
            }
        )
    return snapshot


def install_heat_strike_profile() -> None:
    """Install heat-strike profile and water-only guards."""
    global _INSTALLED
    global _ORIGINAL_BASE_HEAT_PROFILE
    global _ORIGINAL_THERMAL_MIX_MODIFIER
    global _ORIGINAL_TEMPERATURE_SOURCE_SNAPSHOT
    global _ORIGINAL_BATCH_CONTEXT_SNAPSHOT

    if _INSTALLED:
        return

    profile = advice_control.BREWZILLA_BASE_PROFILE
    profile["description"] = "Built-in BrewZilla 35L small-batch profile with explicit heat-strike water ramp."
    profile.setdefault("heat", {}).update(
        {
            "ramp_very_far": 100.0,
            "ramp_far": 85.0,
            "ramp_mid": 65.0,
            "ramp_approach": 45.0,
            "ramp_near": 30.0,
            "ramp_final": 15.0,
            "ramp_feather": 5.0,
        }
    )
    profile.setdefault("delta", {}).update(
        {
            "ramp_very_far": 20.0,
            "ramp_far": 10.0,
            "ramp_mid": 5.0,
            "ramp_approach": 3.0,
            "ramp_near": 1.0,
            "ramp_final": 0.5,
            "ramp_feather": 0.2,
        }
    )
    profile.setdefault("rate", {}).update(
        {
            "fast_c_per_min": 0.30,
            "moderate_c_per_min": 0.10,
            "near_target_heat_cap": 5.0,
        }
    )

    _ORIGINAL_BASE_HEAT_PROFILE = advice_control._base_heat_profile
    _ORIGINAL_THERMAL_MIX_MODIFIER = advice_control._thermal_mix_modifier
    _ORIGINAL_TEMPERATURE_SOURCE_SNAPSHOT = learning._temperature_source_snapshot
    _ORIGINAL_BATCH_CONTEXT_SNAPSHOT = learning._batch_context_snapshot

    advice_control._base_heat_profile = _heat_strike_base_heat_profile
    advice_control._thermal_mix_modifier = _heat_strike_thermal_mix_modifier
    learning._temperature_source_snapshot = _water_only_temperature_source_snapshot
    learning._batch_context_snapshot = _water_only_batch_context_snapshot

    _INSTALLED = True
