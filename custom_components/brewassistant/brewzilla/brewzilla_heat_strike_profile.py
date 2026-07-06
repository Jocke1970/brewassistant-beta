"""Heat-strike/pre-mash-in profile adjustments for BrewZilla.

"Real mash" means a real brewday, not that grain has already been added.
Before mash-in there is still no grain bed, so BrewAssistant should treat early
mash ramps as strike-water heating: use the kettle/wort temperature, allow a
more aggressive heat profile, and keep mash/wort thermal-mix protection disabled
until mash-in has started.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.core import HomeAssistant

from . import brewzilla_advice_control as advice_control
from . import brewzilla_learning as learning

_INSTALLED = False
_ORIGINAL_WITH_ADVICE: Callable[[HomeAssistant, dict[str, Any]], dict[str, Any]] | None = None
_ORIGINAL_THERMAL_MIX_MODIFIER: Callable[[dict[str, Any], float | None, str], dict[str, Any]] | None = None
_ORIGINAL_TEMPERATURE_SOURCE_SNAPSHOT: Callable[[HomeAssistant, str], dict[str, Any]] | None = None
_ORIGINAL_BATCH_CONTEXT_SNAPSHOT: Callable[[HomeAssistant, dict[str, Any], str], dict[str, Any]] | None = None

_MASH_IN_STARTED_STATES = {"mash_in_started", "mash_in_complete"}
_PRE_MASH_IN_STATES = {"", "idle", "ready_for_mash_in", "pending", "waiting", "awaiting_mash_in"}


def _mash_in_gate_state(hass: HomeAssistant) -> str:
    store = hass.data.setdefault("brewassistant", {}).get("brewzilla_mash_in_gate")
    if not isinstance(store, dict):
        return ""
    return str(store.get("state") or "").strip().lower()


def _pre_mash_in(hass: HomeAssistant) -> bool:
    """Return true until the operator has marked mash-in as started/complete."""
    state = _mash_in_gate_state(hass)
    if state in _MASH_IN_STARTED_STATES:
        return False
    if state in _PRE_MASH_IN_STATES:
        return True
    # Unknown future gate states should fail safe as pre-mash-in unless they
    # explicitly say mash-in has started or completed.
    return "started" not in state and "complete" not in state


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
    delta: float | None,
    temp_rate: float | None = None,
) -> tuple[float | None, str | None]:
    """Return a tiered heat profile for pre-mash-in strike-water ramps."""
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
    """Disable mash/wort thermal-mix protection before mash-in."""
    role = str(advice.get("learning_temperature_role") or "")
    if stage_kind == "ramp" and role.startswith("pre_mash_in"):
        return {
            "active": False,
            "reason": "pre_mash_in_strike_water_no_mash_bed",
            "separate_inputs": False,
        }
    assert _ORIGINAL_THERMAL_MIX_MODIFIER is not None
    return _ORIGINAL_THERMAL_MIX_MODIFIER(advice, target, stage_kind)


def _pre_mash_in_temperature_source_snapshot(hass: HomeAssistant, stage_kind: str) -> dict[str, Any]:
    """Use BrewZilla/kettle temperature as learning temperature before mash-in."""
    if stage_kind != "ramp" or not _pre_mash_in(hass):
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
        "learning_temperature_role": "pre_mash_in_wort_or_kettle_temperature",
        "use_internal_sensor": None,
        "control_device_type": None,
        "control_device_mac_address": None,
    }


def _pre_mash_in_batch_context_snapshot(
    hass: HomeAssistant,
    runtime: dict[str, Any],
    stage_kind: str,
) -> dict[str, Any]:
    """Do not require grain context while the physical phase is still strike water."""
    assert _ORIGINAL_BATCH_CONTEXT_SNAPSHOT is not None
    snapshot = _ORIGINAL_BATCH_CONTEXT_SNAPSHOT(hass, runtime, stage_kind)
    if stage_kind == "ramp" and _pre_mash_in(hass) and snapshot.get("needs_batch_context"):
        snapshot = dict(snapshot)
        snapshot.update(
            {
                "needs_batch_context": False,
                "batch_context_missing": [],
                "batch_context_reason": "Pre-mash-in strike-water ramp: grain/mash context is not required until mash-in starts.",
            }
        )
    return snapshot


def _apply_pre_mash_in_heat_strike_profile(hass: HomeAssistant, out: dict[str, Any]) -> dict[str, Any]:
    """Override advice output with strike-water heat only before mash-in."""
    stage_kind = str(out.get("advice_stage_kind") or "unknown")
    if stage_kind != "ramp":
        out["advice_physical_phase"] = "not_ramp"
        return out

    if not _pre_mash_in(hass):
        out["advice_physical_phase"] = "mash_in_started_or_complete"
        return out

    out["advice_physical_phase"] = "pre_mash_in"
    if not out.get("advice_local_profile_active"):
        return out

    delta = advice_control._num(out.get("advice_delta_to_target"))
    temp_rate = advice_control._num(out.get("advice_temp_rate_c_per_min"))
    profile_heat, profile_phase = _heat_strike_base_heat_profile(delta, temp_rate)
    heat_util = advice_control._num(out.get("heat_utilization"))
    arm_heat = advice_control._arm_heat(delta, profile_heat)

    out.update(
        {
            "advice_capped_heat_utilization": profile_heat,
            "advice_heat_cap": profile_heat,
            "advice_heat_profile_phase": profile_phase,
            "advice_local_profile_heat_utilization": profile_heat,
            "advice_thermal_mix_active": False,
            "advice_thermal_mix_separate_inputs": False,
            "advice_thermal_mix_severity": None,
            "advice_thermal_mix_heat_cap": None,
            "advice_thermal_mix_reason": "pre_mash_in_strike_water_no_mash_bed",
            "desired_heat_utilization": profile_heat,
            "desired_heater_on": True if arm_heat else None,
            "heating_needed": arm_heat,
            "heat_utilization_action_needed": advice_control.base._utilization_action_needed(heat_util, profile_heat),
            "heater_stop_needed": False,
            "heater_action_needed": bool(arm_heat and not bool(out.get("heater_on"))),
        }
    )

    runtime_state = str(out.get("brewday_state") or "idle")
    advice_control._refresh_mode(out, runtime_state)

    reason = str(out.get("control_reason") or "Brewday Advice profile is active.")
    out["control_reason"] = (
        f"{reason} Physical phase pre-mash-in: treating Real mash as real brewday strike water; "
        "using kettle/wort temperature and disabling mash/wort thermal-mix until mash-in starts."
    )
    return out


def _with_heat_strike_phase_control(hass: HomeAssistant, snapshot: dict[str, Any]) -> dict[str, Any]:
    assert _ORIGINAL_WITH_ADVICE is not None
    out = _ORIGINAL_WITH_ADVICE(hass, snapshot)
    return _apply_pre_mash_in_heat_strike_profile(hass, out)


def install_heat_strike_profile() -> None:
    """Install heat-strike profile and pre-mash-in physical-phase guards."""
    global _INSTALLED
    global _ORIGINAL_WITH_ADVICE
    global _ORIGINAL_THERMAL_MIX_MODIFIER
    global _ORIGINAL_TEMPERATURE_SOURCE_SNAPSHOT
    global _ORIGINAL_BATCH_CONTEXT_SNAPSHOT

    if _INSTALLED:
        return

    profile = advice_control.BREWZILLA_BASE_PROFILE
    profile["description"] = "Built-in BrewZilla 35L small-batch profile with explicit pre-mash-in strike-water ramp."
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

    _ORIGINAL_WITH_ADVICE = advice_control._with_advice
    _ORIGINAL_THERMAL_MIX_MODIFIER = advice_control._thermal_mix_modifier
    _ORIGINAL_TEMPERATURE_SOURCE_SNAPSHOT = learning._temperature_source_snapshot
    _ORIGINAL_BATCH_CONTEXT_SNAPSHOT = learning._batch_context_snapshot

    advice_control._with_advice = _with_heat_strike_phase_control
    advice_control._thermal_mix_modifier = _heat_strike_thermal_mix_modifier
    learning._temperature_source_snapshot = _pre_mash_in_temperature_source_snapshot
    learning._batch_context_snapshot = _pre_mash_in_batch_context_snapshot

    _INSTALLED = True
