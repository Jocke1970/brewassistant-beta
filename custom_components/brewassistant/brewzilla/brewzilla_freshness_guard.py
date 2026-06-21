"""BrewZilla RCL freshness guard."""

from __future__ import annotations

from typing import Any

from . import brewzilla_orchestration as _base

RAPT_ACTIVE_CONTROL_WARN_AGE_SECONDS = 60
RAPT_ACTIVE_CONTROL_BLOCK_AGE_SECONDS = 90

_BASE_BUILD_ORCHESTRATION_SNAPSHOT = _base.build_orchestration_snapshot
_INSTALLED = False


def _runtime_active(state: Any) -> bool:
    return _base._runtime_active(str(state or "idle"))


def _as_number(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _utilization_action_needed(current: Any, desired: float | None) -> bool:
    if desired is None:
        return False
    current_value = _as_number(current)
    if current_value is None:
        return True
    return abs(float(desired) - current_value) > _base.UTILIZATION_TOLERANCE


def _active_control_context(snapshot: dict[str, Any]) -> bool:
    if not _runtime_active(snapshot.get("brewday_state")):
        return False
    if bool(snapshot.get("completed_runtime")):
        return False
    return bool(
        snapshot.get("mash_in_heat_strategy_active")
        or snapshot.get("mash_hold_strategy_active")
        or snapshot.get("boil_stage")
    )


def _freshness_source(snapshot: dict[str, Any]) -> str | None:
    if _as_number(snapshot.get("rapt_brewzilla_temperature_age_seconds")) is not None:
        return "rapt_brewzilla_temperature_age_seconds"
    if _as_number(snapshot.get("brewzilla_rapt_control_age_seconds")) is not None:
        return "brewzilla_rapt_control_age_seconds"
    return None


def _freshness_age(snapshot: dict[str, Any]) -> float | None:
    temperature_age = _as_number(snapshot.get("rapt_brewzilla_temperature_age_seconds"))
    if temperature_age is not None:
        return temperature_age
    return _as_number(snapshot.get("brewzilla_rapt_control_age_seconds"))


def _apply_freshness_guard(snapshot: dict[str, Any]) -> dict[str, Any]:
    guarded = dict(snapshot)
    active_context = _active_control_context(guarded)
    age = _freshness_age(guarded)
    source = _freshness_source(guarded)

    warning = bool(
        active_context
        and age is not None
        and age > RAPT_ACTIVE_CONTROL_WARN_AGE_SECONDS
    )
    blocking = bool(
        active_context
        and age is not None
        and age > RAPT_ACTIVE_CONTROL_BLOCK_AGE_SECONDS
    )
    reason = None
    if blocking:
        reason = f"BrewZilla/RCL temperature data stale ({int(age)}s); control blocked."
    elif warning:
        reason = f"BrewZilla/RCL temperature data getting stale ({int(age)}s); refresh recommended."

    guarded.update(
        {
            "rcl_freshness_guard_active": warning,
            "rcl_freshness_guard_blocking": blocking,
            "rcl_freshness_guard_reason": reason,
            "rcl_freshness_age_seconds": int(age) if age is not None else None,
            "rcl_freshness_source": source,
            "rcl_freshness_warn_age_seconds": RAPT_ACTIVE_CONTROL_WARN_AGE_SECONDS,
            "rcl_freshness_block_age_seconds": RAPT_ACTIVE_CONTROL_BLOCK_AGE_SECONDS,
        }
    )

    if not blocking:
        if warning:
            guarded["rapt_critical_refresh_recommended"] = True
        return guarded

    heater_on = bool(guarded.get("heater_on"))
    pump_on = bool(guarded.get("pump_on"))
    desired_heat = 0.0
    desired_pump = 0.0
    heat_utilization_action_needed = _utilization_action_needed(
        guarded.get("heat_utilization"),
        desired_heat,
    )
    pump_utilization_action_needed = _utilization_action_needed(
        guarded.get("pump_utilization"),
        desired_pump,
    )
    safe_action_needed = bool(
        heater_on
        or pump_on
        or heat_utilization_action_needed
        or pump_utilization_action_needed
    )
    connected = bool(guarded.get("connected"))

    guarded.update(
        {
            "target_sync_needed": False,
            "heating_needed": False,
            "pump_recommended": False,
            "desired_heat_utilization": desired_heat,
            "desired_pump_utilization": desired_pump,
            "desired_heater_on": False,
            "desired_pump_on": False,
            "heater_action_needed": False,
            "pump_action_needed": False,
            "heater_stop_needed": heater_on,
            "pump_stop_needed": pump_on,
            "heat_utilization_action_needed": heat_utilization_action_needed,
            "pump_utilization_action_needed": pump_utilization_action_needed,
            "ba_owned_reassert_action_needed": False,
            "rapt_critical_refresh_recommended": True,
            "can_apply_target": connected and safe_action_needed,
            "orchestration_mode": "direct-control" if connected and safe_action_needed else "blocked",
            "control_reason": reason,
        }
    )
    return guarded


def build_orchestration_snapshot(hass) -> dict[str, Any]:
    return _apply_freshness_guard(_BASE_BUILD_ORCHESTRATION_SNAPSHOT(hass))


def install_freshness_guard() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _base.build_orchestration_snapshot = build_orchestration_snapshot
    _INSTALLED = True
