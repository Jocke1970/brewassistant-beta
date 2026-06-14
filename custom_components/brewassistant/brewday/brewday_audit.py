"""Brewday audit log for post-test analysis.

The audit log is Python-owned and persisted through Home Assistant storage. It
records compact snapshots of what BrewAssistant believed, what Brewfather exposed
through the normalized runtime, and what BrewZilla actions were considered or
executed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .brewday_runtime import build_brewday_runtime_snapshot

DATA_KEY = "brewday_audit_log"
STORE_DATA_KEY = "brewday_audit_log_store"
STORAGE_KEY = "brewassistant_brewday_audit_log"
STORAGE_VERSION = 1
MAX_EVENTS = 250
INVALID = {None, "unknown", "unavailable", "none", ""}
ACTIVE_STATES = {
    "live",
    "running",
    "paused",
    "prepared",
    "awaiting_snapshot",
    "awaiting_confirm",
}

BREWZILLA_CURRENT_TEMP = "sensor.brewassistant_brewzilla_current_temperature"
BREWZILLA_DEVICE_TARGET = "sensor.brewassistant_brewzilla_target_temperature"
BREWZILLA_POWER = "sensor.brewzilla_power"
BREWZILLA_HEATER = "switch.brewzilla_heater"
BREWZILLA_PUMP = "switch.brewzilla_pump"
BREWZILLA_MAIN = "switch.brewzilla"


@dataclass(slots=True)
class BrewdayAuditLog:
    """Mutable Brewday audit log state."""

    active: bool = False
    started_at: datetime | None = None
    stopped_at: datetime | None = None
    updated_at: datetime | None = None
    events: list[dict[str, Any]] = field(default_factory=list)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return dt_util.as_utc(value)
    if value is None or str(value).lower() in INVALID:
        return None
    parsed = dt_util.parse_datetime(str(value))
    if parsed is not None:
        return dt_util.as_utc(parsed)
    return None


def _as_float(value: Any) -> float | None:
    try:
        if value is None or str(value).lower() in INVALID:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _state(hass: HomeAssistant, entity_id: str) -> str | None:
    state = hass.states.get(entity_id)
    if state is None or state.state.lower() in INVALID:
        return None
    return state.state


def _float_state(hass: HomeAssistant, entity_id: str) -> float | None:
    return _as_float(_state(hass, entity_id))


def _store(hass: HomeAssistant) -> Store:
    data = hass.data.setdefault("brewassistant", {})
    store = data.get(STORE_DATA_KEY)
    if not isinstance(store, Store):
        store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        data[STORE_DATA_KEY] = store
    return store


def _to_store(log: BrewdayAuditLog) -> dict[str, Any]:
    return {
        "active": log.active,
        "started_at": log.started_at.isoformat() if log.started_at else None,
        "stopped_at": log.stopped_at.isoformat() if log.stopped_at else None,
        "updated_at": log.updated_at.isoformat() if log.updated_at else None,
        "events": list(log.events[-MAX_EVENTS:]),
    }


def _from_store(payload: Any) -> BrewdayAuditLog:
    if not isinstance(payload, dict):
        return BrewdayAuditLog()
    events = payload.get("events") if isinstance(payload.get("events"), list) else []
    return BrewdayAuditLog(
        active=bool(payload.get("active", False)),
        started_at=_as_datetime(payload.get("started_at")),
        stopped_at=_as_datetime(payload.get("stopped_at")),
        updated_at=_as_datetime(payload.get("updated_at")),
        events=[event for event in events if isinstance(event, dict)][-MAX_EVENTS:],
    )


async def async_load_brewday_audit_log(hass: HomeAssistant) -> BrewdayAuditLog:
    """Load persisted audit log into hass.data."""
    payload = await _store(hass).async_load()
    log = _from_store(payload)
    hass.data.setdefault("brewassistant", {})[DATA_KEY] = log
    return log


async def async_save_brewday_audit_log(hass: HomeAssistant) -> None:
    """Persist the current audit log."""
    await _store(hass).async_save(_to_store(get_brewday_audit_log(hass)))


def get_brewday_audit_log(hass: HomeAssistant) -> BrewdayAuditLog:
    """Return the Python-owned audit log."""
    data = hass.data.setdefault("brewassistant", {})
    log = data.get(DATA_KEY)
    if not isinstance(log, BrewdayAuditLog):
        log = BrewdayAuditLog()
        data[DATA_KEY] = log
    return log


def _runtime_active(snapshot: dict[str, Any]) -> bool:
    return str(snapshot.get("runtime_state") or "").lower() in ACTIVE_STATES


def _target_value(event: dict[str, Any] | None) -> float | None:
    """Return best available target from an event."""
    if not event:
        return None
    for key in ("tracker_target", "requested_target", "applied_target", "brewzilla_device_target"):
        value = _as_float(event.get(key))
        if value is not None:
            return value
    return None


def _event_base(
    hass: HomeAssistant,
    event_type: str,
    *,
    brewzilla_result: dict[str, Any] | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    runtime = build_brewday_runtime_snapshot(hass)
    result = brewzilla_result or {}
    event = {
        "timestamp": _now().isoformat(),
        "event_type": event_type,
        "note": note,
        "runtime_state": runtime.get("runtime_state"),
        "status": runtime.get("status"),
        "source": runtime.get("source"),
        "stage": runtime.get("stage"),
        "step": runtime.get("step"),
        "next_step": runtime.get("next_step"),
        "raw_step_index": runtime.get("raw_step_index"),
        "resolved_step_index": runtime.get("resolved_step_index"),
        "raw_step_name": runtime.get("raw_step_name"),
        "tracker_target": runtime.get("target_temperature"),
        "time_remaining_seconds": runtime.get("time_remaining_seconds"),
        "stage_remaining_seconds": runtime.get("stage_remaining_seconds"),
        "progress": runtime.get("progress"),
        "snapshot_age_seconds": runtime.get("snapshot_age_seconds"),
        "awaiting_snapshot": runtime.get("awaiting_snapshot"),
        "brewzilla_current_temp": _float_state(hass, BREWZILLA_CURRENT_TEMP),
        "brewzilla_device_target": _float_state(hass, BREWZILLA_DEVICE_TARGET),
        "power_w": _float_state(hass, BREWZILLA_POWER),
        "main_power": _state(hass, BREWZILLA_MAIN),
        "heater_state": _state(hass, BREWZILLA_HEATER),
        "pump_state": _state(hass, BREWZILLA_PUMP),
        "requested_target": result.get("requested_target"),
        "applied_target": result.get("applied_target"),
        "target_delta": result.get("target_delta"),
        "target_sync_needed": result.get("target_sync_needed"),
        "paused_target_rewind_blocked": result.get("paused_target_rewind_blocked"),
        "heating_needed": result.get("heating_needed"),
        "heater_action_needed": result.get("heater_action_needed"),
        "pump_recommended": result.get("pump_recommended"),
        "pump_action_needed": result.get("pump_action_needed"),
        "orchestration_mode": result.get("orchestration_mode"),
        "control_reason": result.get("control_reason"),
        "apply_result": result.get("apply_result"),
        "applied": result.get("applied"),
        "target_changed": result.get("target_changed"),
        "heater_started": result.get("heater_started"),
        "pump_started": result.get("pump_started"),
        "actions": result.get("actions"),
        "rapt_brewzilla_poll_age_seconds": result.get("rapt_brewzilla_poll_age_seconds"),
        "rapt_brewzilla_poll_age_minutes": result.get("rapt_brewzilla_poll_age_minutes"),
        "rapt_brewzilla_newest_entity": result.get("rapt_brewzilla_newest_entity"),
        "rapt_brewzilla_newest_age_seconds": result.get("rapt_brewzilla_newest_age_seconds"),
        "rapt_brewzilla_oldest_entity": result.get("rapt_brewzilla_oldest_entity"),
        "rapt_brewzilla_oldest_age_seconds": result.get("rapt_brewzilla_oldest_age_seconds"),
        "rapt_brewzilla_dynamic_age_seconds": result.get("rapt_brewzilla_dynamic_age_seconds"),
        "rapt_brewzilla_dynamic_age_minutes": result.get("rapt_brewzilla_dynamic_age_minutes"),
        "rapt_brewzilla_dynamic_newest_entity": result.get("rapt_brewzilla_dynamic_newest_entity"),
        "rapt_brewzilla_dynamic_newest_age_seconds": result.get("rapt_brewzilla_dynamic_newest_age_seconds"),
        "rapt_brewzilla_dynamic_oldest_entity": result.get("rapt_brewzilla_dynamic_oldest_entity"),
        "rapt_brewzilla_dynamic_oldest_age_seconds": result.get("rapt_brewzilla_dynamic_oldest_age_seconds"),
        "rapt_brewzilla_static_oldest_entity": result.get("rapt_brewzilla_static_oldest_entity"),
        "rapt_brewzilla_static_oldest_age_seconds": result.get("rapt_brewzilla_static_oldest_age_seconds"),
        "rapt_brewzilla_temperature_age_seconds": result.get("rapt_brewzilla_temperature_age_seconds"),
        "rapt_brewzilla_power_age_seconds": result.get("rapt_brewzilla_power_age_seconds"),
        "rapt_brewzilla_target_age_seconds": result.get("rapt_brewzilla_target_age_seconds"),
        "rapt_brewzilla_heat_util_age_seconds": result.get("rapt_brewzilla_heat_util_age_seconds"),
        "rapt_brewzilla_pump_util_age_seconds": result.get("rapt_brewzilla_pump_util_age_seconds"),
        "rapt_brewzilla_poll_warning": result.get("rapt_brewzilla_poll_warning"),
        "rapt_critical_refresh_recommended": result.get("rapt_critical_refresh_recommended"),
    }
    return {key: value for key, value in event.items() if value is not None}


async def async_start_brewday_audit_log(hass: HomeAssistant, *, note: str | None = None) -> dict[str, Any]:
    """Start collecting audit events."""
    log = get_brewday_audit_log(hass)
    now = _now()
    log.active = True
    log.started_at = now
    log.stopped_at = None
    log.updated_at = now
    log.events.clear()
    log.events.append(_event_base(hass, "audit_started", note=note))
    await async_save_brewday_audit_log(hass)
    return build_brewday_audit_snapshot(hass)


async def async_stop_brewday_audit_log(hass: HomeAssistant, *, note: str | None = None) -> dict[str, Any]:
    """Stop collecting audit events without clearing them."""
    log = get_brewday_audit_log(hass)
    log.active = False
    log.stopped_at = _now()
    log.updated_at = log.stopped_at
    log.events.append(_event_base(hass, "audit_stopped", note=note))
    log.events = log.events[-MAX_EVENTS:]
    await async_save_brewday_audit_log(hass)
    return build_brewday_audit_snapshot(hass)


async def async_clear_brewday_audit_log(hass: HomeAssistant) -> dict[str, Any]:
    """Clear audit events and stop logging."""
    hass.data.setdefault("brewassistant", {})[DATA_KEY] = BrewdayAuditLog(active=False, updated_at=_now())
    await async_save_brewday_audit_log(hass)
    return build_brewday_audit_snapshot(hass)


async def async_record_brewday_audit_event(
    hass: HomeAssistant,
    event_type: str,
    *,
    brewzilla_result: dict[str, Any] | None = None,
    note: str | None = None,
    always_record: bool = False,
) -> dict[str, Any] | None:
    """Record one audit event if logging is active or always_record is true."""
    log = get_brewday_audit_log(hass)
    if not log.active and not always_record:
        return None
    event = _event_base(hass, event_type, brewzilla_result=brewzilla_result, note=note)
    log.events.append(event)
    log.events = log.events[-MAX_EVENTS:]
    log.updated_at = _now()
    await async_save_brewday_audit_log(hass)
    return event


async def async_record_brewday_audit_tick(
    hass: HomeAssistant,
    *,
    brewzilla_result: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Record a coordinator/orchestration tick while audit logging is active."""
    log = get_brewday_audit_log(hass)
    if not log.active:
        return None

    runtime = build_brewday_runtime_snapshot(hass)
    result = brewzilla_result or {}
    if result.get("applied"):
        event_type = "brewzilla_action"
    elif result.get("apply_result") == "not_needed_or_blocked":
        event_type = "action_skipped"
    elif _runtime_active(runtime):
        event_type = "runtime_tick"
    else:
        event_type = "idle_tick"

    return await async_record_brewday_audit_event(
        hass,
        event_type,
        brewzilla_result=brewzilla_result,
        always_record=True,
    )


async def async_record_brewday_audit_snapshot(hass: HomeAssistant, *, note: str | None = None) -> dict[str, Any] | None:
    """Record a manual diagnostic snapshot."""
    return await async_record_brewday_audit_event(hass, "manual_snapshot", note=note, always_record=True)


def build_brewday_audit_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    """Return dashboard-friendly audit summary."""
    log = get_brewday_audit_log(hass)
    last_event = log.events[-1] if log.events else None
    last_action = next(
        (event for event in reversed(log.events) if event.get("applied") or event.get("event_type") == "brewzilla_action"),
        None,
    )
    return {
        "active": log.active,
        "status": "recording" if log.active else "stopped" if log.events else "empty",
        "event_count": len(log.events),
        "max_events": MAX_EVENTS,
        "started_at": log.started_at.isoformat() if log.started_at else None,
        "stopped_at": log.stopped_at.isoformat() if log.stopped_at else None,
        "updated_at": log.updated_at.isoformat() if log.updated_at else None,
        "last_event_type": last_event.get("event_type") if last_event else None,
        "last_event_at": last_event.get("timestamp") if last_event else None,
        "last_step": last_event.get("step") if last_event else None,
        "last_stage": last_event.get("stage") if last_event else None,
        "last_target": _target_value(last_event),
        "last_action_type": last_action.get("event_type") if last_action else None,
        "last_apply_result": last_action.get("apply_result") if last_action else None,
        "last_control_reason": last_event.get("control_reason") if last_event else None,
        "last_paused_target_rewind_blocked": last_event.get("paused_target_rewind_blocked") if last_event else None,
        "last_rapt_brewzilla_poll_age_seconds": last_event.get("rapt_brewzilla_poll_age_seconds") if last_event else None,
        "last_rapt_brewzilla_poll_age_minutes": last_event.get("rapt_brewzilla_poll_age_minutes") if last_event else None,
        "last_rapt_brewzilla_dynamic_age_seconds": last_event.get("rapt_brewzilla_dynamic_age_seconds") if last_event else None,
        "last_rapt_brewzilla_dynamic_age_minutes": last_event.get("rapt_brewzilla_dynamic_age_minutes") if last_event else None,
        "last_rapt_brewzilla_temperature_age_seconds": last_event.get("rapt_brewzilla_temperature_age_seconds") if last_event else None,
        "last_rapt_brewzilla_power_age_seconds": last_event.get("rapt_brewzilla_power_age_seconds") if last_event else None,
        "last_rapt_critical_refresh_recommended": last_event.get("rapt_critical_refresh_recommended") if last_event else None,
        "events": list(log.events[-MAX_EVENTS:]),
        "recent_events": list(log.events[-20:]),
    }
