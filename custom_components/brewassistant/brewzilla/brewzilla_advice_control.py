"""Brewday Advice heat recommendation bridge for BrewZilla.

The goal is to restore Brewday Advice as the heat decision source while keeping
Direct action conservative enough for small-volume BrewZilla tests. Orchestration
still owns target sync and pump actions, but heat utilization and heater on/off
come from Advice with an extra conservative cap.
"""

from __future__ import annotations

from typing import Any

from . import brewzilla_orchestration as base
from .brewzilla_learning import build_brewzilla_learning_snapshot

_BASE_BUILD = base.build_orchestration_snapshot
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


def _heat_cap(stage_kind: str, delta: float | None) -> float:
    """Return conservative max heat for Advice-backed Direct action.

    Brewday Advice may suggest relatively high values for generic ramping. In a
    small water-only BrewZilla test with slow RCL feedback, Direct action needs a
    lower cap so it brakes before the following hold is consumed/overshot.
    """
    if delta is None:
        return 40.0
    if delta <= 0.1:
        return 0.0

    if stage_kind == "mash_hold":
        if delta > 2.0:
            return 35.0
        if delta > 0.7:
            return 25.0
        return 15.0

    if stage_kind == "ramp":
        if delta > 5.0:
            return 75.0
        if delta > 3.0:
            return 55.0
        if delta > 1.5:
            return 35.0
        if delta > 0.7:
            return 20.0
        return 10.0

    return 40.0


def _heater_desired(heat: float | None, delta: float | None) -> bool | None:
    if heat is None:
        return None
    if heat <= base.UTILIZATION_TOLERANCE:
        return False
    if delta is not None and delta <= 0.1:
        return False
    return True


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
        and suggested_heat is not None
    )

    cap = _heat_cap(stage_kind, delta)
    capped_heat = None
    if suggested_heat is not None:
        capped_heat = max(0.0, min(float(suggested_heat), cap))

    out.update(
        {
            "advice_heat_available": suggested_heat is not None,
            "advice_heat_active": active,
            "advice_stage_kind": stage_kind,
            "advice_phase": advice.get("phase"),
            "advice_confidence": advice.get("confidence"),
            "advice_overshoot_risk": advice.get("overshoot_risk"),
            "advice_suggested_heat_utilization": suggested_heat,
            "advice_capped_heat_utilization": capped_heat,
            "advice_heat_cap": cap,
            "advice_delta_to_target": delta,
            "advice_temp_rate_c_per_min": advice.get("temp_rate_c_per_min"),
            "advice_learning_temperature": advice.get("learning_temperature"),
            "advice_learning_temperature_source": advice.get("learning_temperature_source"),
            "advice_heat_reason": advice.get("strategy_reason"),
        }
    )

    if not active or capped_heat is None:
        return out

    desired_heat = max(0.0, min(100.0, float(capped_heat)))
    desired_heater = _heater_desired(desired_heat, delta)
    heat_util = _num(out.get("heat_utilization"))
    heater_on = bool(out.get("heater_on"))

    out["desired_heat_utilization"] = desired_heat
    out["desired_heater_on"] = desired_heater
    out["heating_needed"] = bool(desired_heater)
    out["heat_utilization_action_needed"] = base._utilization_action_needed(heat_util, desired_heat)

    if desired_heater is True:
        out["heater_action_needed"] = not heater_on
        out["heater_stop_needed"] = False
    elif desired_heater is False:
        out["heater_action_needed"] = False
        out["heater_stop_needed"] = heater_on

    action_needed = bool(
        out.get("target_sync_needed")
        or out.get("heater_action_needed")
        or out.get("heater_stop_needed")
        or out.get("pump_action_needed")
        or out.get("pump_stop_needed")
        or out.get("heat_utilization_action_needed")
        or out.get("pump_utilization_action_needed")
        or out.get("completion_stop_needed")
    )
    blocked = out.get("orchestration_mode") == "blocked"
    can_act = bool(
        out.get("connected")
        and not blocked
        and not out.get("abort_lockout_active")
        and _active(runtime_state)
        and base._target_valid(_num(out.get("requested_target")))
    )

    if not blocked:
        out["orchestration_mode"] = "direct-control" if can_act and action_needed else "monitor"
        out["can_apply_target"] = bool(can_act and action_needed)

    reason = advice.get("strategy_reason") or "Brewday Advice heat recommendation is active."
    out["control_reason"] = (
        f"Brewday Advice heat: {reason} "
        f"Suggested {suggested_heat}%, capped to {desired_heat}% for Direct action."
    )
    return out


def build_orchestration_snapshot(hass) -> dict[str, Any]:
    return _with_advice(hass, _BASE_BUILD(hass))


def install_advice_control() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    base.build_orchestration_snapshot = build_orchestration_snapshot
    _INSTALLED = True
