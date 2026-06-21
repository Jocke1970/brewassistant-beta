"""BrewZilla RCL freshness guard."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from . import brewzilla_batch_context_guard as _batch_context_guard
from . import brewzilla_orchestration as _base

RAPT_ACTIVE_CONTROL_WARN_AGE_SECONDS = 60
RAPT_ACTIVE_CONTROL_BLOCK_AGE_SECONDS = 90
RCL_REFRESH_THROTTLE_SECONDS = 45

RCL_REFRESH_ENTITY_IDS = [
    "sensor.brewzilla_temperature",
    "sensor.brewzilla_power",
    "sensor.brewzilla_connection",
    "number.brewzilla_target_temperature",
    "number.brewzilla_heat_utilization",
    "number.brewzilla_pump_utilization",
    "switch.brewzilla_heater",
    "switch.brewzilla_pump",
    "sensor.brewzilla_ble_thermometer_temperature",
    "sensor.brewzilla_control_device_temperature",
]

_BASE_BUILD_ORCHESTRATION_SNAPSHOT = _base.build_orchestration_snapshot
_INSTALLED = False
_REFRESH_LAST_REQUESTED_AT: datetime | None = None
_REFRESH_LAST_AGE_SECONDS: int | None = None
_REFRESH_LAST_SOURCE: str | None = None
_REFRESH_LAST_ENTITY_IDS: list[str] = []


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


def _known_refresh_entity_ids(hass) -> list[str]:
    return [entity_id for entity_id in RCL_REFRESH_ENTITY_IDS if hass.states.get(entity_id) is not None]


def _refresh_state_attrs(requested_now: bool = False) -> dict[str, Any]:
    return {
        "rcl_refresh_requested": requested_now,
        "rcl_refresh_last_requested_at": _REFRESH_LAST_REQUESTED_AT.isoformat() if _REFRESH_LAST_REQUESTED_AT else None,
        "rcl_refresh_last_age_seconds": _REFRESH_LAST_AGE_SECONDS,
        "rcl_refresh_last_source": _REFRESH_LAST_SOURCE,
        "rcl_refresh_entity_ids": list(_REFRESH_LAST_ENTITY_IDS),
        "rcl_refresh_throttle_seconds": RCL_REFRESH_THROTTLE_SECONDS,
    }


def _request_rcl_refresh(hass, age: float | None, source: str | None) -> dict[str, Any]:
    """Ask Home Assistant to refresh known BrewZilla/RCL entities.

    Freshness guard is still the safety net, but active runtime should first try
    to make the RCL/BrewZilla snapshot fresh enough for supervised execution.
    """
    global _REFRESH_LAST_REQUESTED_AT, _REFRESH_LAST_AGE_SECONDS, _REFRESH_LAST_SOURCE, _REFRESH_LAST_ENTITY_IDS

    now = datetime.now(UTC)
    if _REFRESH_LAST_REQUESTED_AT and now - _REFRESH_LAST_REQUESTED_AT < timedelta(seconds=RCL_REFRESH_THROTTLE_SECONDS):
        return _refresh_state_attrs(False)

    entity_ids = _known_refresh_entity_ids(hass)
    if not entity_ids:
        return _refresh_state_attrs(False)

    _REFRESH_LAST_REQUESTED_AT = now
    _REFRESH_LAST_AGE_SECONDS = int(age) if age is not None else None
    _REFRESH_LAST_SOURCE = source
    _REFRESH_LAST_ENTITY_IDS = entity_ids

    async def _async_refresh() -> None:
        await hass.services.async_call(
            "homeassistant",
            "update_entity",
            {"entity_id": entity_ids},
            blocking=False,
        )

    hass.async_create_task(_async_refresh())
    return _refresh_state_attrs(True)


def _apply_freshness_guard(hass, snapshot: dict[str, Any]) -> dict[str, Any]:
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
        reason = f"BrewZilla/RCL temperature data stale ({int(age)}s); refresh requested and control blocked."
    elif warning:
        reason = f"BrewZilla/RCL temperature data getting stale ({int(age)}s); refresh requested."

    refresh_attrs = _request_rcl_refresh(hass, age, source) if warning or blocking else _refresh_state_attrs(False)

    guarded.update(
        {
            "rcl_freshness_guard_active": warning,
            "rcl_freshness_guard_blocking": blocking,
            "rcl_freshness_guard_reason": reason,
            "rcl_freshness_age_seconds": int(age) if age is not None else None,
            "rcl_freshness_source": source,
            "rcl_freshness_warn_age_seconds": RAPT_ACTIVE_CONTROL_WARN_AGE_SECONDS,
            "rcl_freshness_block_age_seconds": RAPT_ACTIVE_CONTROL_BLOCK_AGE_SECONDS,
            **refresh_attrs,
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
    return _apply_freshness_guard(hass, _BASE_BUILD_ORCHESTRATION_SNAPSHOT(hass))


def install_freshness_guard() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _batch_context_guard.install_batch_context_guard()
    _base.build_orchestration_snapshot = build_orchestration_snapshot
    _INSTALLED = True
