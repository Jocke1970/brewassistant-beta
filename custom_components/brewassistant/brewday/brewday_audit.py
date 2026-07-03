"""Brewday event/audit log backend.

The event log is Python-owned and persisted through Home Assistant storage.  It is
used as a compact "flight recorder" for Brewday/BrewZilla diagnostics: manual
snapshots, service actions, orchestration ticks, target decisions and RAPT/BLE
health signals.

Public function names are intentionally kept compatible with the older
``brewday_audit`` backend so existing services, sensors and dashboards keep
working.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .brewday_runtime import build_brewday_runtime_snapshot

DATA_KEY = "brewday_audit_log"
STORE_DATA_KEY = "brewday_audit_log_store"
STORAGE_KEY = "brewassistant_brewday_audit_log"
STORAGE_VERSION = 1
EVENT_SCHEMA_VERSION = 2

MAX_EVENTS = 250
RECENT_EVENTS = 20
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

# These result keys are expected to become more important as BA-owned BrewZilla
# control/reassert grows.  Keeping them central prevents _event_base from turning
# into another hand-maintained wall of assignments.
BREWZILLA_RESULT_FIELDS = (
    "requested_target",
    "applied_target",
    "target_delta",
    "target_sync_needed",
    "paused_target_rewind_blocked",
    "heating_needed",
    "heater_action_needed",
    "pump_recommended",
    "pump_action_needed",
    "orchestration_mode",
    "control_reason",
    "apply_result",
    "applied",
    "target_changed",
    "heater_started",
    "pump_started",
    "pump_utilization_changed",
    "actions",
    # Mash-in confirmation gate diagnostics.
    "mash_in_gate_state",
    "mash_in_gate_pending",
    "mash_in_gate_latched",
    "mash_in_gate_active_key",
    "mash_in_gate_trigger",
    "mash_in_gate_notification_id",
    "mash_in_gate_notified_at",
    "mash_in_gate_confirmed",
    "mash_in_gate_confirmed_at",
    "mash_in_gate_last_target",
    "mash_in_gate_last_stage",
    "mash_in_gate_last_step",
    "mash_in_gate_current_target",
    "mash_in_gate_current_temperature",
    "mash_in_resume_allowed",
    "mash_in_resume_result",
    "desired_pump_on",
    "desired_pump_utilization",
    "pump_stop_needed",
    "rapt_brewzilla_poll_age_seconds",
    "rapt_brewzilla_poll_age_minutes",
    "rapt_brewzilla_newest_entity",
    "rapt_brewzilla_newest_age_seconds",
    "rapt_brewzilla_oldest_entity",
    "rapt_brewzilla_oldest_age_seconds",
    "rapt_brewzilla_dynamic_age_seconds",
    "rapt_brewzilla_dynamic_age_minutes",
    "rapt_brewzilla_dynamic_newest_entity",
    "rapt_brewzilla_dynamic_newest_age_seconds",
    "rapt_brewzilla_dynamic_oldest_entity",
    "rapt_brewzilla_dynamic_oldest_age_seconds",
    "rapt_brewzilla_static_oldest_entity",
    "rapt_brewzilla_static_oldest_age_seconds",
    "rapt_brewzilla_temperature_age_seconds",
    "rapt_brewzilla_power_age_seconds",
    "rapt_brewzilla_target_age_seconds",
    "rapt_brewzilla_heat_util_age_seconds",
    "rapt_brewzilla_pump_util_age_seconds",
    "rapt_brewzilla_poll_warning",
    "rapt_critical_refresh_recommended",
    # BA-owned control / reassert diagnostics.
    "ba_owned_control_active",
    "ba_owned_desired_heat_utilization",
    "ba_owned_desired_pump_utilization",
    "ba_owned_current_heat_utilization",
    "ba_owned_current_pump_utilization",
    "ba_owned_heat_utilization_delta",
    "ba_owned_pump_utilization_delta",
    "ba_owned_reassert_heat_utilization",
    "ba_owned_reassert_pump_utilization",
    "heat_utilization_action_needed",
    "pump_utilization_action_needed",
    "heat_utilization_reassert_needed",
    "pump_utilization_reassert_needed",
)

RUNTIME_FIELDS = (
    "runtime_state",
    "status",
    "source",
    "stage",
    "step",
    "next_step",
    "raw_step_index",
    "resolved_step_index",
    "raw_step_name",
    "target_temperature",
    "time_remaining_seconds",
    "stage_remaining_seconds",
    "progress",
    "snapshot_age_seconds",
    "awaiting_snapshot",
)

ALWAYS_RECORD_EVENT_TYPES = {
    "audit_started",
    "audit_stopped",
    "manual_snapshot",
    "manual_brewfather_refresh",
    "brewzilla_action",
    "ba_owned_reassert",
    "mash_in_confirmed",
    "mash_circulation_started",
    "abort",
    "warning",
    "error",
}

ACTION_EVENT_TYPES = {
    "brewzilla_action",
    "ba_owned_reassert",
    "mash_in_confirmed",
    "mash_circulation_started",
    "abort",
}


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
        return float(str(value).replace(",", "."))
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
    normalized_events = [_normalize_event(event) for event in events if isinstance(event, dict)]
    return BrewdayAuditLog(
        active=bool(payload.get("active", False)),
        started_at=_as_datetime(payload.get("started_at")),
        stopped_at=_as_datetime(payload.get("stopped_at")),
        updated_at=_as_datetime(payload.get("updated_at")),
        events=normalized_events[-MAX_EVENTS:],
    )


def _normalize_event(event: dict[str, Any]) -> dict[str, Any]:
    """Make old persisted events compatible with the v2 event shape."""

    normalized = dict(event)
    normalized.setdefault("schema_version", 1)
    normalized.setdefault("severity", _severity_for_event(str(normalized.get("event_type") or ""), normalized))
    normalized.setdefault("occurrences", 1)
    timestamp = normalized.get("timestamp")
    if timestamp:
        normalized.setdefault("first_seen", timestamp)
        normalized.setdefault("last_seen", timestamp)
    normalized.setdefault("signature", _event_signature(normalized))
    return normalized


async def async_load_brewday_audit_log(hass: HomeAssistant) -> BrewdayAuditLog:
    """Load persisted audit log into hass.data."""

    payload = await _store(hass).async_load()
    log = _from_store(payload)
    hass.data.setdefault("brewassistant", {})[DATA_KEY] = log
    return log


async def async_save_brewday_audit_log(hass: HomeAssistant) -> None:
    """Persist the current audit log."""

    await _store(hass,).async_save(_to_store(get_brewday_audit_log(hass)))


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


def _actions(result: dict[str, Any]) -> list[str]:
    actions = result.get("actions")
    if isinstance(actions, list):
        return [str(action) for action in actions if action is not None]
    if isinstance(actions, tuple):
        return [str(action) for action in actions if action is not None]
    if isinstance(actions, str) and actions:
        return [actions]
    return []


def _has_ba_owned_reassert(result: dict[str, Any]) -> bool:
    if result.get("ba_owned_reassert_heat_utilization") is not None:
        return True
    if result.get("ba_owned_reassert_pump_utilization") is not None:
        return True
    action_text = " ".join(_actions(result)).lower()
    return "ba_owned_reassert" in action_text or "reassert" in action_text


def _tick_event_type(runtime: dict[str, Any], result: dict[str, Any]) -> str:
    if _has_ba_owned_reassert(result):
        return "ba_owned_reassert"
    if result.get("applied"):
        return "brewzilla_action"
    if result.get("apply_result") == "not_needed_or_blocked":
        return "action_skipped"
    if result.get("rapt_brewzilla_poll_warning") or result.get("rapt_critical_refresh_recommended"):
        return "warning"
    if _runtime_active(runtime):
        return "runtime_tick"
    return "idle_tick"


def _severity_for_event(event_type: str, event: dict[str, Any]) -> str:
    if event_type in ACTION_EVENT_TYPES:
        return "action"
    if event_type in {"warning", "action_skipped"}:
        return "warning"
    if event_type in {"audit_started", "audit_stopped", "manual_snapshot", "manual_brewfather_refresh"}:
        return "info"
    if event.get("rapt_brewzilla_poll_warning") or event.get("rapt_critical_refresh_recommended"):
        return "warning"
    return "debug"


def _event_signature(event: dict[str, Any]) -> str:
    """Signature used to coalesce noisy tick events without losing changes."""

    signature_payload = {
        "event_type": event.get("event_type"),
        "runtime_state": event.get("runtime_state"),
        "source": event.get("source"),
        "stage": event.get("stage"),
        "step": event.get("step"),
        "target": event.get("tracker_target"),
        "requested_target": event.get("requested_target"),
        "applied_target": event.get("applied_target"),
        "apply_result": event.get("apply_result"),
        "control_reason": event.get("control_reason"),
        "target_sync_needed": event.get("target_sync_needed"),
        "actions": event.get("actions"),
        "mash_in_gate_state": event.get("mash_in_gate_state"),
        "mash_in_gate_pending": event.get("mash_in_gate_pending"),
        "mash_in_gate_latched": event.get("mash_in_gate_latched"),
        "mash_in_gate_active_key": event.get("mash_in_gate_active_key"),
        "ba_owned_reassert_heat_utilization": event.get("ba_owned_reassert_heat_utilization"),
        "ba_owned_reassert_pump_utilization": event.get("ba_owned_reassert_pump_utilization"),
        "warning": event.get("rapt_brewzilla_poll_warning") or event.get("rapt_critical_refresh_recommended"),
    }
    return json.dumps(signature_payload, sort_keys=True, default=str)


def _compact_event(event: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in event.items() if value is not None}


def _runtime_context(hass: HomeAssistant) -> dict[str, Any]:
    runtime = build_brewday_runtime_snapshot(hass)
    return {key: runtime.get(key) for key in RUNTIME_FIELDS}


def _brewzilla_context(hass: HomeAssistant) -> dict[str, Any]:
    return {
        "brewzilla_current_temp": _float_state(hass, BREWZILLA_CURRENT_TEMP),
        "brewzilla_device_target": _float_state(hass, BREWZILLA_DEVICE_TARGET),
        "power_w": _float_state(hass, BREWZILLA_POWER),
        "main_power": _state(hass, BREWZILLA_MAIN),
        "heater_state": _state(hass, BREWZILLA_HEATER),
        "pump_state": _state(hass, BREWZILLA_PUMP),
    }


def _result_context(result: dict[str, Any]) -> dict[str, Any]:
    return {key: result.get(key) for key in BREWZILLA_RESULT_FIELDS}


def _event_base(
    hass: HomeAssistant,
    event_type: str,
    *,
    brewzilla_result: dict[str, Any] | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    runtime = _runtime_context(hass)
    result = brewzilla_result or {}
    now = _now().isoformat()

    event = {
        "schema_version": EVENT_SCHEMA_VERSION,
        "timestamp": now,
        "first_seen": now,
        "last_seen": now,
        "occurrences": 1,
        "event_type": event_type,
        "note": note,
        **runtime,
        "tracker_target": runtime.get("target_temperature"),
        **_brewzilla_context(hass),
        **_result_context(result),
    }
    event["severity"] = _severity_for_event(event_type, event)
    event["signature"] = _event_signature(event)
    return _compact_event(event)


def _should_coalesce(event: dict[str, Any]) -> bool:
    """Only coalesce non-action tick-style events.

    Actions, warnings, manual snapshots and audit start/stop events are kept as
    individual rows because they are high-signal timeline markers.
    """

    event_type = str(event.get("event_type") or "")
    if event_type in ALWAYS_RECORD_EVENT_TYPES:
        return False
    return event_type in {"runtime_tick", "idle_tick", "action_skipped"}


def _merge_repeated_event(existing: dict[str, Any], event: dict[str, Any]) -> None:
    existing["last_seen"] = event.get("timestamp")
    existing["timestamp"] = event.get("timestamp")
    existing["occurrences"] = int(existing.get("occurrences") or 1) + 1

    # Keep the freshest volatile diagnostics on the coalesced row.
    for key in (
        "snapshot_age_seconds",
        "time_remaining_seconds",
        "stage_remaining_seconds",
        "progress",
        "brewzilla_current_temp",
        "brewzilla_device_target",
        "power_w",
        "heater_state",
        "pump_state",
        "mash_in_gate_state",
        "mash_in_gate_pending",
        "mash_in_gate_latched",
        "mash_in_gate_current_target",
        "mash_in_gate_current_temperature",
        "rapt_brewzilla_poll_age_seconds",
        "rapt_brewzilla_poll_age_minutes",
        "rapt_brewzilla_dynamic_age_seconds",
        "rapt_brewzilla_dynamic_age_minutes",
        "rapt_brewzilla_temperature_age_seconds",
        "rapt_brewzilla_power_age_seconds",
        "rapt_brewzilla_target_age_seconds",
        "rapt_brewzilla_heat_util_age_seconds",
        "rapt_brewzilla_pump_util_age_seconds",
    ):
        if key in event:
            existing[key] = event[key]


def _append_event(log: BrewdayAuditLog, event: dict[str, Any]) -> dict[str, Any]:
    if _should_coalesce(event) and log.events:
        previous = log.events[-1]
        if previous.get("signature") == event.get("signature"):
            _merge_repeated_event(previous, event)
            log.updated_at = _now()
            return previous

    log.events.append(event)
    log.events = log.events[-MAX_EVENTS:]
    log.updated_at = _now()
    return event


async def async_start_brewday_audit_log(hass: HomeAssistant, *, note: str | None = None) -> dict[str, Any]:
    """Start collecting audit events."""

    log = get_brewday_audit_log(hass)
    now = _now()
    log.active = True
    log.started_at = now
    log.stopped_at = None
    log.updated_at = now
    log.events.clear()
    _append_event(log, _event_base(hass, "audit_started", note=note))
    await async_save_brewday_audit_log(hass)
    return build_brewday_audit_snapshot(hass)


async def async_stop_brewday_audit_log(hass: HomeAssistant, *, note: str | None = None) -> dict[str, Any]:
    """Stop collecting audit events without clearing them."""

    log = get_brewday_audit_log(hass)
    log.active = False
    log.stopped_at = _now()
    log.updated_at = log.stopped_at
    _append_event(log, _event_base(hass, "audit_stopped", note=note))
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
    recorded = _append_event(log, event)
    await async_save_brewday_audit_log(hass)
    return recorded


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
    event_type = _tick_event_type(runtime, result)

    return await async_record_brewday_audit_event(
        hass,
        event_type,
        brewzilla_result=brewzilla_result,
        always_record=True,
    )


async def async_record_brewday_audit_snapshot(hass: HomeAssistant, *, note: str | None = None) -> dict[str, Any] | None:
    """Record a manual diagnostic snapshot."""

    return await async_record_brewday_audit_event(hass, "manual_snapshot", note=note, always_record=True)


def _last_action_event(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    return next(
        (
            event
            for event in reversed(events)
            if event.get("applied")
            or event.get("event_type") in ACTION_EVENT_TYPES
            or event.get("ba_owned_reassert_heat_utilization") is not None
            or event.get("ba_owned_reassert_pump_utilization") is not None
        ),
        None,
    )


def build_brewday_audit_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    """Return dashboard-friendly audit summary."""

    log = get_brewday_audit_log(hass)
    last_event = log.events[-1] if log.events else None
    last_action = _last_action_event(log.events)

    return {
        "active": log.active,
        "status": "recording" if log.active else "stopped" if log.events else "empty",
        "event_count": len(log.events),
        "max_events": MAX_EVENTS,
        "schema_version": EVENT_SCHEMA_VERSION,
        "started_at": log.started_at.isoformat() if log.started_at else None,
        "stopped_at": log.stopped_at.isoformat() if log.stopped_at else None,
        "updated_at": log.updated_at.isoformat() if log.updated_at else None,
        "last_event_type": last_event.get("event_type") if last_event else None,
        "last_event_severity": last_event.get("severity") if last_event else None,
        "last_event_at": last_event.get("timestamp") if last_event else None,
        "last_event_occurrences": last_event.get("occurrences") if last_event else None,
        "last_step": last_event.get("step") if last_event else None,
        "last_stage": last_event.get("stage") if last_event else None,
        "last_target": _target_value(last_event),
        "last_action_type": last_action.get("event_type") if last_action else None,
        "last_apply_result": last_action.get("apply_result") if last_action else None,
        "last_control_reason": last_event.get("control_reason") if last_event else None,
        "last_paused_target_rewind_blocked": last_event.get("paused_target_rewind_blocked") if last_event else None,
        "last_mash_in_gate_state": last_event.get("mash_in_gate_state") if last_event else None,
        "last_mash_in_gate_pending": last_event.get("mash_in_gate_pending") if last_event else None,
        "last_mash_in_gate_latched": last_event.get("mash_in_gate_latched") if last_event else None,
        "last_mash_in_gate_active_key": last_event.get("mash_in_gate_active_key") if last_event else None,
        "last_mash_in_gate_trigger": last_event.get("mash_in_gate_trigger") if last_event else None,
        "last_ba_owned_reassert_heat_utilization": (
            last_action.get("ba_owned_reassert_heat_utilization") if last_action else None
        ),
        "last_ba_owned_reassert_pump_utilization": (
            last_action.get("ba_owned_reassert_pump_utilization") if last_action else None
        ),
        "last_rapt_brewzilla_poll_age_seconds": last_event.get("rapt_brewzilla_poll_age_seconds") if last_event else None,
        "last_rapt_brewzilla_poll_age_minutes": last_event.get("rapt_brewzilla_poll_age_minutes") if last_event else None,
        "last_rapt_brewzilla_dynamic_age_seconds": (
            last_event.get("rapt_brewzilla_dynamic_age_seconds") if last_event else None
        ),
        "last_rapt_brewzilla_dynamic_age_minutes": (
            last_event.get("rapt_brewzilla_dynamic_age_minutes") if last_event else None
        ),
        "last_rapt_brewzilla_temperature_age_seconds": (
            last_event.get("rapt_brewzilla_temperature_age_seconds") if last_event else None
        ),
        "last_rapt_brewzilla_power_age_seconds": (
            last_event.get("rapt_brewzilla_power_age_seconds") if last_event else None
        ),
        "last_rapt_critical_refresh_recommended": (
            last_event.get("rapt_critical_refresh_recommended") if last_event else None
        ),
        "events": list(log.events[-MAX_EVENTS:]),
        "recent_events": list(log.events[-RECENT_EVENTS:]),
    }
