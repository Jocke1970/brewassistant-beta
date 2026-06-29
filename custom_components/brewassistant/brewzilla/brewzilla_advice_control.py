"""Brewday Advice profile bridge for BrewZilla."""

from __future__ import annotations

from typing import Any

from . import brewzilla_orchestration as base
from .brewzilla_learning import build_brewzilla_learning_snapshot

_BASE_BUILD = None
_INSTALLED = False
_APPLICABLE_STAGES = {"ramp", "mash_hold"}


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _active(state: Any) -> bool:
    return base._runtime_active(str(state or "idle"))


def _heat_profile(stage_kind: str, delta: float | None) -> float | None:
    """Return a conservative local BrewZilla heat profile.

    The returned value is a profile/max-power setting, not a thermostat output.
    If the current temperature is already at/above target, return None so BA
    does not send a new positive heat profile and BrewZilla can settle locally.
    """
    if delta is not None and delta <= 0.0:
        return None
    if stage_kind == "mash_hold":
        if delta is not None and delta > 2.0:
            return 20.0
        return 12.0
    if stage_kind == "ramp":
        if delta is None:
            return 25.0
        if delta > 5.0:
            return 45.0
        if delta > 3.0:
            return 35.0
        if delta > 1.5:
            return 25.0
        if delta > 0.5:
            return 15.0
        return 10.0
    return 12.0


def _pump_profile(stage_kind: str, delta: float | None) -> tuple[bool | None, float | None, str | None]:
    if stage_kind not in _APPLICABLE_STAGES:
        return None, None, None
    if delta is not None and delta <= -0.3:
        return True, 50.0, "overshoot_mix"
    if stage_kind == "ramp":
        return True, 70.0, "ramp_mix"
    return True, 50.0, "mash_mix"


def _arm_heat(delta: float | None) -> bool:
    return bool(delta is None or delta > 0.5)


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

    active = bool(
        _active(runtime_state)
        and not out.get("completed_runtime")
        and stage_kind in _APPLICABLE_STAGES
    )

    profile_heat = _heat_profile(stage_kind, delta) if active else None
    pump_on_profile, pump_util_profile, pump_phase = _pump_profile(stage_kind, delta)
    profile_suppressed = bool(active and profile_heat is None)

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
        "advice_temp_rate_c_per_min": advice.get("temp_rate_c_per_min"),
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
        "advice_local_profile_suppressed_reason": "at_or_above_target" if profile_suppressed else None,
    })

    if not active:
        return out

    if profile_suppressed:
        _clear_normal_heat_actions(out)
    else:
        heat_util = _num(out.get("heat_utilization"))
        arm_heat = _arm_heat(delta)
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
        profile_text = "profile suppressed at/above target"
    else:
        profile_text = f"profile {profile_heat}%"
    out["control_reason"] = (
        f"Brewday Advice local profile: {reason} "
        f"Suggested {suggested_heat}%, {profile_text}; "
        f"pump {pump_on_profile}/{pump_util_profile}%. "
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
