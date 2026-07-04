"""Brewday Advice profile bridge for BrewZilla."""

from __future__ import annotations

from typing import Any

from . import brewzilla_orchestration as base
from .brewzilla_learning import build_brewzilla_learning_snapshot

_BASE_BUILD = None
_INSTALLED = False
_APPLICABLE_STAGES = {"ramp", "mash_hold"}


# BrewZilla has meaningful thermal inertia, especially with small test volumes
# and when the mash/BLE temperature is used as control context.  These profiles
# are deliberately conservative: they are max-power/profile values, not a remote
# thermostat output.  The goal is to taper before target instead of waiting for
# the local regulator to overshoot and then recover.
RAMP_HEAT_FAR = 45.0
RAMP_HEAT_MID = 30.0
RAMP_HEAT_APPROACH = 22.0
RAMP_HEAT_NEAR = 15.0
RAMP_HEAT_FINAL = 8.0
RAMP_HEAT_FEATHER = 5.0
HOLD_HEAT_RECOVERY = 15.0
HOLD_HEAT_GENTLE = 10.0
HOLD_HEAT_FEATHER = 5.0
HEAT_OFF_PROFILE = 0.0
FAST_RISE_RATE_C_PER_MIN = 0.20
MODERATE_RISE_RATE_C_PER_MIN = 0.10


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _active(state: Any) -> bool:
    return base._runtime_active(str(state or "idle"))


def _rate_adjusted_heat(profile: float, *, delta: float | None, temp_rate: float | None) -> float:
    """Cap heat more aggressively when temperature is still rising near target."""
    if delta is None or temp_rate is None:
        return profile
    if delta <= 2.0 and temp_rate >= FAST_RISE_RATE_C_PER_MIN:
        return min(profile, RAMP_HEAT_FEATHER)
    if delta <= 1.0 and temp_rate >= MODERATE_RISE_RATE_C_PER_MIN:
        return min(profile, RAMP_HEAT_FEATHER)
    return profile


def _heat_profile(stage_kind: str, delta: float | None, temp_rate: float | None = None) -> float | None:
    """Return a conservative local BrewZilla heat profile.

    The returned value is a profile/max-power setting, not a thermostat output.
    Returning 0 is intentional at/above target: BA should reduce BrewZilla's heat
    utilization instead of passively observing overshoot. Returning None means
    the current stage is outside this advice bridge.
    """
    if stage_kind not in _APPLICABLE_STAGES:
        return None
    if delta is not None and delta <= 0.0:
        return HEAT_OFF_PROFILE

    if stage_kind == "mash_hold":
        if delta is None:
            profile = HOLD_HEAT_GENTLE
        elif delta > 2.0:
            profile = HOLD_HEAT_RECOVERY
        elif delta > 0.7:
            profile = HOLD_HEAT_GENTLE
        elif delta > 0.2:
            profile = HOLD_HEAT_FEATHER
        else:
            profile = HEAT_OFF_PROFILE
        return _rate_adjusted_heat(profile, delta=delta, temp_rate=temp_rate)

    if stage_kind == "ramp":
        if delta is None:
            profile = RAMP_HEAT_NEAR
        elif delta > 5.0:
            profile = RAMP_HEAT_FAR
        elif delta > 3.0:
            profile = RAMP_HEAT_MID
        elif delta > 2.0:
            profile = RAMP_HEAT_APPROACH
        elif delta > 1.0:
            profile = RAMP_HEAT_NEAR
        elif delta > 0.5:
            profile = RAMP_HEAT_FINAL
        elif delta > 0.2:
            profile = RAMP_HEAT_FEATHER
        else:
            profile = HEAT_OFF_PROFILE
        return _rate_adjusted_heat(profile, delta=delta, temp_rate=temp_rate)

    return None


def _pump_profile(stage_kind: str, delta: float | None) -> tuple[bool | None, float | None, str | None]:
    if stage_kind not in _APPLICABLE_STAGES:
        return None, None, None
    if delta is not None and delta <= -0.3:
        return True, 50.0, "overshoot_mix"
    if stage_kind == "ramp":
        return True, 70.0, "ramp_mix"
    return True, 50.0, "mash_mix"


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
    """Prevent Advice from acting as a remote thermostat."""
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

    active = bool(
        _active(runtime_state)
        and not out.get("completed_runtime")
        and stage_kind in _APPLICABLE_STAGES
    )

    profile_heat = _heat_profile(stage_kind, delta, temp_rate) if active else None
    pump_on_profile, pump_util_profile, pump_phase = _pump_profile(stage_kind, delta)
    profile_suppressed = False

    out.update({
        "advice_heat_available": suggested_heat is not None,
        "advice_heat_active": active,
        "advice_stage_kind": stage_kind,
        "advice_phase": advice.get("phase"),
        "advice_confidence": advice.get("confidence"),
        "advice_overshoot_risk": advice.get("overshoot_risk"),
        "advice_suggested_heat_utilization": suggested_heat,
        "advice_capped_heat_utilization": profile_heat,
        "advice_heat_cap": profile_heat,
        "advice_delta_to_target": delta,
        "advice_temp_rate_c_per_min": temp_rate,
        "advice_learning_temperature": advice.get("learning_temperature"),
        "advice_learning_temperature_source": advice.get("learning_temperature_source"),
        "advice_heat_reason": advice.get("strategy_reason"),
        "advice_pump_active": bool(active and pump_on_profile is not None),
        "advice_desired_pump_on": pump_on_profile,
        "advice_desired_pump_utilization": pump_util_profile,
        "advice_pump_phase": pump_phase,
        "advice_local_profile_active": active,
        "advice_local_profile_heat_utilization": profile_heat,
        "advice_local_profile_suppressed": profile_suppressed,
        "advice_local_profile_suppressed_reason": None,
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
    if profile_suppressed:
        profile_text = "profile suppressed"
    else:
        profile_text = f"profile {profile_heat}%"
    out["control_reason"] = (
        f"Brewday Advice local profile: {reason} "
        f"Suggested {suggested_heat}%, {profile_text}; "
        f"delta {delta}°C, rate {temp_rate}°C/min; "
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
