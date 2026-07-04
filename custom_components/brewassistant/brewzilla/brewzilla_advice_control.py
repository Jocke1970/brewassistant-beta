"""Brewday Advice profile bridge for BrewZilla."""

from __future__ import annotations

from typing import Any

from . import brewzilla_orchestration as base
from .brewzilla_learning import build_brewzilla_learning_snapshot

_BASE_BUILD = None
_INSTALLED = False
_APPLICABLE_STAGES = {"ramp", "mash_hold"}

BREWZILLA_BASE_PROFILE = {
    "name": "brewzilla_35l_small_batch_default",
    "description": "Built-in BrewZilla 35L small-batch profile.",
    "heat": {
        "off": 0.0,
        "ramp_far": 45.0,
        "ramp_mid": 30.0,
        "ramp_approach": 22.0,
        "ramp_near": 15.0,
        "ramp_final": 8.0,
        "ramp_feather": 5.0,
        "hold_recovery": 15.0,
        "hold_gentle": 10.0,
        "hold_feather": 5.0,
    },
    "delta": {
        "ramp_far": 5.0,
        "ramp_mid": 3.0,
        "ramp_approach": 2.0,
        "ramp_near": 1.0,
        "ramp_final": 0.5,
        "ramp_feather": 0.2,
        "hold_recovery": 2.0,
        "hold_gentle": 0.7,
        "hold_feather": 0.2,
    },
    "pump": {
        "ramp": 70.0,
        "hold": 50.0,
        "overshoot": 50.0,
        "thermal_mix": 80.0,
    },
    "rate": {
        "fast_c_per_min": 0.20,
        "moderate_c_per_min": 0.10,
        "near_target_heat_cap": 5.0,
    },
    "thermal_mix": {
        "enabled": True,
        "min_mash_wort_delta_c": 0.3,
        "wort_over_target_c": 0.2,
        "mash_below_target_c": 0.7,
        "high_wort_over_target_c": 1.0,
        "large_mash_gap_c": 2.0,
        "heat_cap": 5.0,
        "high_heat_cap": 0.0,
        "pump": 80.0,
    },
    "mash_circulation": {
        "enabled": True,
        "floor_after_mash_in": 50.0,
    },
}


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _profile() -> dict[str, Any]:
    return BREWZILLA_BASE_PROFILE


def _p(path: str, fallback: float) -> float:
    value: Any = _profile()
    for part in path.split("."):
        if not isinstance(value, dict):
            return fallback
        value = value.get(part)
    parsed = _num(value)
    return fallback if parsed is None else parsed


def _active(state: Any) -> bool:
    return base._runtime_active(str(state or "idle"))


def _rate_adjusted_heat(profile_heat: float, *, delta: float | None, temp_rate: float | None) -> tuple[float, str | None]:
    if delta is None or temp_rate is None:
        return profile_heat, None
    cap = _p("rate.near_target_heat_cap", 5.0)
    if delta <= 2.0 and temp_rate >= _p("rate.fast_c_per_min", 0.20):
        return min(profile_heat, cap), "fast_rise_near_target"
    if delta <= 1.0 and temp_rate >= _p("rate.moderate_c_per_min", 0.10):
        return min(profile_heat, cap), "moderate_rise_final_approach"
    return profile_heat, None


def _base_heat_profile(stage_kind: str, delta: float | None, temp_rate: float | None = None) -> tuple[float | None, str | None]:
    if stage_kind not in _APPLICABLE_STAGES:
        return None, None
    if delta is not None and delta <= 0.0:
        return _p("heat.off", 0.0), "at_or_above_target"

    if stage_kind == "mash_hold":
        if delta is None:
            profile_heat, phase = _p("heat.hold_gentle", 10.0), "hold_unknown_delta"
        elif delta > _p("delta.hold_recovery", 2.0):
            profile_heat, phase = _p("heat.hold_recovery", 15.0), "hold_recovery"
        elif delta > _p("delta.hold_gentle", 0.7):
            profile_heat, phase = _p("heat.hold_gentle", 10.0), "hold_gentle"
        elif delta > _p("delta.hold_feather", 0.2):
            profile_heat, phase = _p("heat.hold_feather", 5.0), "hold_feather"
        else:
            profile_heat, phase = _p("heat.off", 0.0), "hold_at_target"
        adjusted, modifier = _rate_adjusted_heat(profile_heat, delta=delta, temp_rate=temp_rate)
        return adjusted, modifier or phase

    if stage_kind == "ramp":
        if delta is None:
            profile_heat, phase = _p("heat.ramp_near", 15.0), "ramp_unknown_delta"
        elif delta > _p("delta.ramp_far", 5.0):
            profile_heat, phase = _p("heat.ramp_far", 45.0), "ramp_far"
        elif delta > _p("delta.ramp_mid", 3.0):
            profile_heat, phase = _p("heat.ramp_mid", 30.0), "ramp_mid"
        elif delta > _p("delta.ramp_approach", 2.0):
            profile_heat, phase = _p("heat.ramp_approach", 22.0), "ramp_approach"
        elif delta > _p("delta.ramp_near", 1.0):
            profile_heat, phase = _p("heat.ramp_near", 15.0), "ramp_near"
        elif delta > _p("delta.ramp_final", 0.5):
            profile_heat, phase = _p("heat.ramp_final", 8.0), "ramp_final"
        elif delta > _p("delta.ramp_feather", 0.2):
            profile_heat, phase = _p("heat.ramp_feather", 5.0), "ramp_feather"
        else:
            profile_heat, phase = _p("heat.off", 0.0), "ramp_at_target"
        adjusted, modifier = _rate_adjusted_heat(profile_heat, delta=delta, temp_rate=temp_rate)
        return adjusted, modifier or phase

    return None, None


def _base_pump_profile(stage_kind: str, delta: float | None) -> tuple[bool | None, float | None, str | None]:
    if stage_kind not in _APPLICABLE_STAGES:
        return None, None, None
    if delta is not None and delta <= -0.3:
        return True, _p("pump.overshoot", 50.0), "overshoot_mix"
    if stage_kind == "ramp":
        return True, _p("pump.ramp", 70.0), "ramp_mix"
    return True, _p("pump.hold", 50.0), "mash_mix"


def _thermal_mix_modifier(advice: dict[str, Any], target: float | None, stage_kind: str) -> dict[str, Any]:
    cfg = _profile().get("thermal_mix", {})
    if not isinstance(cfg, dict) or not bool(cfg.get("enabled", True)):
        return {"active": False}

    mash = _num(advice.get("mash_temperature"))
    wort = _num(advice.get("wort_temperature"))
    if stage_kind not in _APPLICABLE_STAGES or mash is None or wort is None or target is None:
        return {"active": False}

    mash_wort_delta = round(mash - wort, 2)
    mash_gap = round(target - mash, 2)
    wort_over = round(wort - target, 2)
    separate_inputs = abs(mash_wort_delta) >= _p("thermal_mix.min_mash_wort_delta_c", 0.3)
    active = bool(
        separate_inputs
        and wort_over > _p("thermal_mix.wort_over_target_c", 0.2)
        and mash_gap > _p("thermal_mix.mash_below_target_c", 0.7)
    )
    high = bool(
        active
        and (
            wort_over >= _p("thermal_mix.high_wort_over_target_c", 1.0)
            or mash_gap >= _p("thermal_mix.large_mash_gap_c", 2.0)
        )
    )
    return {
        "active": active,
        "separate_inputs": separate_inputs,
        "mash_temperature": mash,
        "wort_temperature": wort,
        "mash_wort_delta": mash_wort_delta,
        "mash_gap_to_target": mash_gap,
        "wort_over_target": wort_over,
        "heat_cap": (_p("thermal_mix.high_heat_cap", 0.0) if high else _p("thermal_mix.heat_cap", 5.0)) if active else None,
        "pump_utilization": _p("thermal_mix.pump", 80.0) if active else None,
        "severity": "high" if high else "active" if active else None,
        "reason": "wort_above_target_mash_lagging" if active else None,
    }


def _mash_circulation_floor(snapshot: dict[str, Any], stage_kind: str) -> float | None:
    cfg = _profile().get("mash_circulation", {})
    if not isinstance(cfg, dict) or not bool(cfg.get("enabled", True)):
        return None
    if stage_kind not in _APPLICABLE_STAGES:
        return None
    if snapshot.get("mash_in_gate_pending") or snapshot.get("mash_in_gate_latched"):
        return None
    gate_state = str(snapshot.get("mash_in_gate_state") or "").lower()
    mash_in_done = bool(
        gate_state == "mash_in_complete"
        or snapshot.get("mash_in_resume_allowed")
        or snapshot.get("mash_in_resume_result")
    )
    if not mash_in_done:
        return None
    return _p("mash_circulation.floor_after_mash_in", 50.0)


def _arm_heat(delta: float | None, profile_heat: float | None) -> bool:
    return bool(profile_heat is not None and profile_heat > 0.0 and (delta is None or delta > 0.5))


def _action_needed(out: dict[str, Any]) -> bool:
    return bool(
        out.get("target_sync_needed")
        or out.get("heater_action_needed")
        or out.get("pump_action_needed")
        or out.get("pump_stop_needed")
        or out.get("heat_utilization_action_needed")
        or out.get("pump_utilization_action_needed")
        or out.get("completion_stop_needed")
    )


def _refresh_mode(out: dict[str, Any], runtime_state: str) -> None:
    if out.get("orchestration_mode") == "blocked":
        return
    can_act = bool(
        out.get("connected")
        and not out.get("abort_lockout_active")
        and _active(runtime_state)
        and base._target_valid(_num(out.get("requested_target")))
    )
    needed = _action_needed(out)
    out["orchestration_mode"] = "direct-control" if can_act and needed else "monitor"
    out["can_apply_target"] = bool(can_act and needed)


def _clear_normal_heat_actions(out: dict[str, Any]) -> None:
    out["desired_heater_on"] = None
    out["heating_needed"] = False
    out["heater_stop_needed"] = False
    out["heater_action_needed"] = False
    out["heat_utilization_action_needed"] = False


def _with_advice(hass, snapshot: dict[str, Any]) -> dict[str, Any]:
    out = dict(snapshot)
    advice = build_brewzilla_learning_snapshot(hass)
    runtime_state = str(out.get("brewday_state") or "idle")
    stage_kind = str(advice.get("stage_kind") or "unknown")
    suggested_heat = _num(advice.get("suggested_heat_utilization"))
    delta = _num(advice.get("delta_to_target"))
    temp_rate = _num(advice.get("temp_rate_c_per_min"))
    target = _num(out.get("requested_target"))

    active = bool(
        _active(runtime_state)
        and not out.get("completed_runtime")
        and stage_kind in _APPLICABLE_STAGES
    )

    profile_heat, profile_phase = _base_heat_profile(stage_kind, delta, temp_rate) if active else (None, None)
    pump_on_profile, pump_util_profile, pump_phase = _base_pump_profile(stage_kind, delta)
    thermal_mix = _thermal_mix_modifier(advice, target, stage_kind) if active else {"active": False}
    if thermal_mix.get("active"):
        heat_cap = _num(thermal_mix.get("heat_cap"))
        if heat_cap is not None:
            profile_heat = heat_cap if profile_heat is None else min(float(profile_heat), heat_cap)
        pump_on_profile = True
        mix_pump = _num(thermal_mix.get("pump_utilization"))
        if mix_pump is not None:
            pump_util_profile = mix_pump if pump_util_profile is None else max(float(pump_util_profile), mix_pump)
        pump_phase = "thermal_mix"
        profile_phase = "thermal_mix_heat_cap"

    mash_circulation_floor = _mash_circulation_floor(out, stage_kind) if active else None
    mash_circulation_floor_active = mash_circulation_floor is not None
    if mash_circulation_floor_active:
        pump_on_profile = True
        if pump_util_profile is None:
            pump_util_profile = mash_circulation_floor
        else:
            pump_util_profile = max(float(pump_util_profile), float(mash_circulation_floor))
        if pump_phase is None:
            pump_phase = "mash_circulation_floor"

    profile_suppressed = False

    out.update({
        "advice_profile_name": _profile().get("name"),
        "advice_profile_source": "built_in",
        "advice_heat_available": suggested_heat is not None,
        "advice_heat_active": active,
        "advice_stage_kind": stage_kind,
        "advice_phase": advice.get("phase"),
        "advice_confidence": advice.get("confidence"),
        "advice_overshoot_risk": advice.get("overshoot_risk"),
        "advice_suggested_heat_utilization": suggested_heat,
        "advice_capped_heat_utilization": profile_heat,
        "advice_heat_cap": profile_heat,
        "advice_heat_profile_phase": profile_phase,
        "advice_delta_to_target": delta,
        "advice_temp_rate_c_per_min": temp_rate,
        "advice_learning_temperature": advice.get("learning_temperature"),
        "advice_learning_temperature_source": advice.get("learning_temperature_source"),
        "advice_heat_reason": advice.get("strategy_reason"),
        "advice_pump_active": bool(active and pump_on_profile is not None),
        "advice_desired_pump_on": pump_on_profile,
        "advice_desired_pump_utilization": pump_util_profile,
        "advice_pump_phase": pump_phase,
        "advice_mash_circulation_floor_active": mash_circulation_floor_active,
        "advice_mash_circulation_floor_utilization": mash_circulation_floor,
        "advice_local_profile_active": active,
        "advice_local_profile_heat_utilization": profile_heat,
        "advice_local_profile_suppressed": profile_suppressed,
        "advice_local_profile_suppressed_reason": None,
        "advice_thermal_mix_active": bool(thermal_mix.get("active")),
        "advice_thermal_mix_separate_inputs": bool(thermal_mix.get("separate_inputs")),
        "advice_thermal_mix_severity": thermal_mix.get("severity"),
        "advice_thermal_mix_mash_temperature": thermal_mix.get("mash_temperature"),
        "advice_thermal_mix_wort_temperature": thermal_mix.get("wort_temperature"),
        "advice_thermal_mix_mash_wort_delta": thermal_mix.get("mash_wort_delta"),
        "advice_thermal_mix_mash_gap_to_target": thermal_mix.get("mash_gap_to_target"),
        "advice_thermal_mix_wort_over_target": thermal_mix.get("wort_over_target"),
        "advice_thermal_mix_heat_cap": thermal_mix.get("heat_cap"),
        "advice_thermal_mix_pump_utilization": thermal_mix.get("pump_utilization"),
        "advice_thermal_mix_reason": thermal_mix.get("reason"),
    })

    if not active:
        return out

    if profile_suppressed:
        _clear_normal_heat_actions(out)
    else:
        heat_util = _num(out.get("heat_utilization"))
        arm_heat = _arm_heat(delta, profile_heat)
        out["desired_heat_utilization"] = profile_heat
        out["desired_heater_on"] = True if arm_heat else None
        out["heating_needed"] = arm_heat
        out["heat_utilization_action_needed"] = base._utilization_action_needed(heat_util, profile_heat)
        out["heater_stop_needed"] = False
        out["heater_action_needed"] = bool(arm_heat and not bool(out.get("heater_on")))

    if pump_on_profile is not None:
        pump_util = _num(out.get("pump_utilization"))
        pump_on = bool(out.get("pump_on"))
        out["desired_pump_on"] = pump_on_profile
        out["desired_pump_utilization"] = pump_util_profile
        out["pump_recommended"] = bool(pump_on_profile)
        out["pump_action_needed"] = bool(pump_on_profile and not pump_on)
        out["pump_stop_needed"] = bool((pump_on_profile is False) and pump_on)
        out["pump_utilization_action_needed"] = base._utilization_action_needed(pump_util, pump_util_profile)

    _refresh_mode(out, runtime_state)

    reason = advice.get("strategy_reason") or "Brewday Advice profile is active."
    if thermal_mix.get("active"):
        reason = f"{reason} Thermal mix modifier active: wort above target while mash lags."
    if mash_circulation_floor_active:
        reason = f"{reason} Mash circulation floor active after mash-in."
    profile_text = "profile suppressed" if profile_suppressed else f"profile {profile_heat}% ({profile_phase})"
    out["control_reason"] = (
        f"Brewday Advice local profile: {reason} "
        f"Base profile {_profile().get('name')}; suggested {suggested_heat}%, {profile_text}; "
        f"delta {delta}°C, rate {temp_rate}°C/min; "
        f"mash {advice.get('mash_temperature')}°C, wort {advice.get('wort_temperature')}°C; "
        f"pump {pump_on_profile}/{pump_util_profile}% ({pump_phase}). "
        "BrewZilla regulates temperature locally."
    )
    return out


def build_orchestration_snapshot(hass) -> dict[str, Any]:
    assert _BASE_BUILD is not None
    return _with_advice(hass, _BASE_BUILD(hass))


def install_advice_control() -> None:
    global _BASE_BUILD, _INSTALLED
    if _INSTALLED:
        return
    _BASE_BUILD = base.build_orchestration_snapshot
    base.build_orchestration_snapshot = build_orchestration_snapshot
    _INSTALLED = True
