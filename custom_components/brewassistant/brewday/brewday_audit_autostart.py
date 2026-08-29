"""Automatic Brewday audit start and high-signal flight-recorder transitions.

The normal Brewday audit backend remains the persistent event store.  This hook
makes logging automatic for both Manual Brewday and Brewfather, and adds compact
state-change snapshots for ownership/handoff diagnostics without logging every
temperature or power update.
"""

from __future__ import annotations

from datetime import timedelta
import json
import logging
from typing import Any, Callable

from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers.event import async_call_later, async_track_state_change_event, async_track_time_interval

from .brewday_audit import (
    async_record_brewday_audit_event,
    async_start_brewday_audit_log,
    get_brewday_audit_log,
)
from .brewday_runtime import build_brewday_runtime_snapshot
from .brewday_runtime_core import brewfather_session_active
from .manual_brewday_store import get_manual_brewday_session

_LOGGER = logging.getLogger(__name__)

BREWFATHER_STATUS_ENTITIES = (
    "sensor.brewfather_brew_tracker_status",
    "sensor.brewfather_brewtracker_status",
)
BREWFATHER_RUNTIME_SOURCE = "Brewfather Brew Tracker"
MANUAL_RUNTIME_SOURCE = "Manual Brewday"
MANUAL_STATUS_ENTITY = "sensor.brewassistant_manual_brewday_status"
RUNTIME_SOURCE_ENTITY = "sensor.brewassistant_brewday_runtime_source"
RUNTIME_STATE_ENTITY = "sensor.brewassistant_brewday_runtime_state"
RUNTIME_STAGE_ENTITY = "sensor.brewassistant_brewday_runtime_stage"
RUNTIME_STEP_ENTITY = "sensor.brewassistant_brewday_runtime_step"
PLANNING_STATUS = "planning"
DATA_KEY_LAST_RESULT = "brewday_audit_autostart_last_result"

ACTIVE_RUNTIME_STATES = {
    "live",
    "running",
    "paused",
    "prepared",
    "awaiting_snapshot",
    "awaiting_confirm",
}

BREWFATHER_BATCH_STATUS_ATTRIBUTES = (
    "brew_tracker_batch_status",
    "batch_status",
)

BREWZILLA_BACKEND_ENTITY_CANDIDATES = (
    "number.brewzilla_target_temperature",
    "number.brewzilla_heat_utilization",
    "number.brewzilla_pump_utilization",
    "sensor.brewzilla_temperature",
    "sensor.brewzilla_power",
    "switch.brewzilla_heater",
    "switch.brewzilla_pump",
)

MANUAL_CONTROL_ENTITIES = (
    "switch.brewassistant_brewzilla_manual_target_override",
    "switch.brewassistant_brewzilla_allow_heater_control",
    "switch.brewassistant_brewzilla_allow_pump_control",
    "number.brewassistant_brewzilla_manual_target_temperature",
    "number.brewassistant_brewzilla_manual_heat_utilization",
    "number.brewassistant_brewzilla_manual_pump_utilization",
)

# Only high-signal state changes are event-triggered.  Temperature and power are
# captured as context on those rows, but are deliberately not triggers themselves.
FLIGHT_RECORDER_TRIGGER_ENTITIES = (
    *BREWFATHER_STATUS_ENTITIES,
    MANUAL_STATUS_ENTITY,
    RUNTIME_SOURCE_ENTITY,
    RUNTIME_STATE_ENTITY,
    RUNTIME_STAGE_ENTITY,
    RUNTIME_STEP_ENTITY,
    *MANUAL_CONTROL_ENTITIES,
    "number.brewzilla_target_temperature",
    "number.brewzilla_heat_utilization",
    "number.brewzilla_pump_utilization",
    "switch.brewzilla_heater",
    "switch.brewzilla_pump",
)

INITIAL_CHECK_DELAY_SECONDS = 5
RETRY_CHECK_DELAYS_SECONDS = (15, 30, 60, 120)
WATCHDOG_INTERVAL_SECONDS = 30


def _normalize_status(value: Any) -> str | None:
    status = str(value or "").strip().lower()
    return status or None


def _state_available(hass: HomeAssistant, entity_id: str) -> bool:
    state = hass.states.get(entity_id)
    return bool(state is not None and str(state.state).lower() not in {"unknown", "unavailable"})


def _entity_state(hass: HomeAssistant, entity_id: str) -> State | None:
    """Return exact or HA-suffixed translated entity state."""
    direct = hass.states.get(entity_id)
    if direct is not None:
        return direct
    if "." not in entity_id:
        return None
    domain, object_id = entity_id.split(".", 1)
    suffix = f"_{object_id}"
    for candidate in hass.states.async_all(domain):
        candidate_object_id = candidate.entity_id.split(".", 1)[1]
        if candidate_object_id == object_id or candidate_object_id.endswith(suffix):
            return candidate
    return None


def _value(hass: HomeAssistant, entity_id: str) -> Any:
    state = _entity_state(hass, entity_id)
    if state is None:
        return None
    value = str(state.state)
    return None if value.lower() in {"unknown", "unavailable", "none", ""} else value


def _float_value(hass: HomeAssistant, entity_id: str) -> float | None:
    value = _value(hass, entity_id)
    try:
        return None if value is None else float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _bool_on(hass: HomeAssistant, entity_id: str) -> bool | None:
    value = _value(hass, entity_id)
    if value is None:
        return None
    return str(value).lower() == "on"


def _brewfather_backend_available(hass: HomeAssistant) -> bool:
    return any(_state_available(hass, entity_id) for entity_id in BREWFATHER_STATUS_ENTITIES)


def _brewzilla_backend_available(hass: HomeAssistant) -> bool:
    return any(_state_available(hass, entity_id) for entity_id in BREWZILLA_BACKEND_ENTITY_CANDIDATES)


def _brewfather_status_from_state(state: State | None) -> tuple[str | None, str | None]:
    if state is None:
        return None, None
    raw_state = _normalize_status(getattr(state, "state", None))
    if raw_state == PLANNING_STATUS:
        return PLANNING_STATUS, "state"
    attributes = getattr(state, "attributes", {}) or {}
    for attribute_name in BREWFATHER_BATCH_STATUS_ATTRIBUTES:
        attribute_status = _normalize_status(attributes.get(attribute_name))
        if attribute_status == PLANNING_STATUS:
            return PLANNING_STATUS, attribute_name
    return raw_state, "state" if raw_state is not None else None


def _brewfather_status(hass: HomeAssistant) -> str | None:
    for entity_id in BREWFATHER_STATUS_ENTITIES:
        status, _source = _brewfather_status_from_state(hass.states.get(entity_id))
        if status is not None:
            return status
    return None


def _runtime_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    try:
        snapshot = build_brewday_runtime_snapshot(hass)
    except Exception as exc:  # pragma: no cover - diagnostics must never break HA setup
        return {"runtime_error": f"{type(exc).__name__}: {exc}"}
    return snapshot if isinstance(snapshot, dict) else {"runtime_error": "invalid_snapshot"}


def _runtime_state(runtime: dict[str, Any]) -> str:
    return str(runtime.get("runtime_state") or runtime.get("status") or "idle").strip().lower()


def _manual_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    try:
        return get_manual_brewday_session(hass).to_snapshot()
    except Exception as exc:  # pragma: no cover - diagnostics only
        return {"runtime_error": f"{type(exc).__name__}: {exc}"}


def _autostart_allowed(hass: HomeAssistant) -> tuple[bool, str, dict[str, Any]]:
    runtime = _runtime_snapshot(hass)
    if get_brewday_audit_log(hass).active:
        return False, "audit_already_active", runtime

    manual = _manual_snapshot(hass)
    manual_state = str(manual.get("runtime_state") or manual.get("status") or "idle").lower()
    if manual_state in ACTIVE_RUNTIME_STATES:
        return True, f"manual_runtime_{manual_state}", runtime

    runtime_source = str(runtime.get("source") or "")
    runtime_state = _runtime_state(runtime)
    if runtime_source not in {"", "None"} and runtime_state in ACTIVE_RUNTIME_STATES:
        return True, f"runtime_active:{runtime_source}:{runtime_state}", runtime

    if brewfather_session_active(hass):
        return True, "brewfather_session_active", runtime

    if _brewfather_status(hass) == PLANNING_STATUS:
        return True, "brewfather_planning", runtime

    return False, "brewday_runtime_not_active", runtime


def _store_autostart_result(hass: HomeAssistant, result: dict[str, Any]) -> None:
    hass.data.setdefault("brewassistant", {})[DATA_KEY_LAST_RESULT] = result


def _runtime_result_fields(runtime: dict[str, Any]) -> dict[str, Any]:
    return {
        "runtime_source": runtime.get("source"),
        "runtime_state": runtime.get("runtime_state") or runtime.get("status"),
        "runtime_stage": runtime.get("stage"),
        "runtime_step": runtime.get("step"),
        "runtime_next_step": runtime.get("next_step"),
        "runtime_target_temperature": runtime.get("target_temperature"),
        "runtime_error": runtime.get("runtime_error"),
    }


def _last_apply_context(hass: HomeAssistant) -> dict[str, Any]:
    result = hass.data.setdefault("brewassistant", {}).get("brewzilla_last_apply_result")
    if not isinstance(result, dict):
        return {}
    keys = (
        "orchestration_mode",
        "control_reason",
        "apply_result",
        "actions",
        "requested_target",
        "applied_target",
        "desired_heat_utilization",
        "desired_pump_utilization",
        "desired_heater_on",
        "desired_pump_on",
        "heater_action_needed",
        "heater_stop_needed",
        "pump_action_needed",
        "pump_stop_needed",
        "heat_utilization_action_needed",
        "pump_utilization_action_needed",
        "manual_brew_control_active",
        "manual_target_override_active",
        "manual_heater_auto_allowed",
        "manual_pump_auto_allowed",
        "manual_pause_safe_down_active",
        "abort_lockout_active",
    )
    return {key: result.get(key) for key in keys if result.get(key) is not None}


def _flight_recorder_context(
    hass: HomeAssistant,
    *,
    trigger: str,
    changed_entity: str | None = None,
    old_value: Any = None,
    new_value: Any = None,
) -> dict[str, Any]:
    runtime = _runtime_snapshot(hass)
    manual = _manual_snapshot(hass)
    return {
        "flight_recorder_version": 3,
        "trigger": trigger,
        "changed_entity": changed_entity,
        "old_value": old_value,
        "new_value": new_value,
        "runtime": {
            "source": runtime.get("source"),
            "state": runtime.get("runtime_state") or runtime.get("status"),
            "stage": runtime.get("stage"),
            "step": runtime.get("step"),
            "next_step": runtime.get("next_step"),
            "target": runtime.get("target_temperature"),
        },
        "manual_session": {
            "state": manual.get("runtime_state") or manual.get("status"),
            "stage": manual.get("stage"),
            "step": manual.get("step"),
            "next_step": manual.get("next_step"),
            "target": manual.get("target_temperature"),
        },
        "brewfather": {
            "session_active": brewfather_session_active(hass),
            "status": _brewfather_status(hass),
        },
        "ownership": {
            "target_manual": _bool_on(hass, "switch.brewassistant_brewzilla_manual_target_override"),
            "heat_auto": _bool_on(hass, "switch.brewassistant_brewzilla_allow_heater_control"),
            "pump_auto": _bool_on(hass, "switch.brewassistant_brewzilla_allow_pump_control"),
        },
        "ba_setpoints": {
            "target_c": _float_value(hass, "number.brewassistant_brewzilla_manual_target_temperature"),
            "heat_pct": _float_value(hass, "number.brewassistant_brewzilla_manual_heat_utilization"),
            "pump_pct": _float_value(hass, "number.brewassistant_brewzilla_manual_pump_utilization"),
        },
        "brewzilla_readback": {
            "target_c": _float_value(hass, "number.brewzilla_target_temperature"),
            "heat_pct": _float_value(hass, "number.brewzilla_heat_utilization"),
            "pump_pct": _float_value(hass, "number.brewzilla_pump_utilization"),
            "temperature_c": _float_value(hass, "sensor.brewzilla_temperature"),
            "power_w": _float_value(hass, "sensor.brewzilla_power"),
            "heater": _value(hass, "switch.brewzilla_heater"),
            "pump": _value(hass, "switch.brewzilla_pump"),
        },
        "last_apply": _last_apply_context(hass),
    }


async def async_maybe_autostart_brewday_audit_log(
    hass: HomeAssistant,
    *,
    trigger: str,
) -> dict[str, Any]:
    """Start the persistent audit automatically when any Brewday becomes active."""
    allowed, reason, runtime = _autostart_allowed(hass)
    if not allowed:
        result = {
            "started": False,
            "reason": reason,
            "trigger": trigger,
            "brewfather_status": _brewfather_status(hass),
            "brewfather_backend_available": _brewfather_backend_available(hass),
            "brewzilla_backend_available": _brewzilla_backend_available(hass),
            **_runtime_result_fields(runtime),
        }
        _store_autostart_result(hass, result)
        return result

    note = f"Auto-started Brewday flight recorder ({trigger}; {reason})."
    snapshot = await async_start_brewday_audit_log(hass, note=note)
    _LOGGER.info("Brewday flight recorder auto-started from %s (%s)", reason, trigger)
    result = {
        "started": True,
        "reason": reason,
        "trigger": trigger,
        "brewfather_status": _brewfather_status(hass),
        "brewfather_backend_available": _brewfather_backend_available(hass),
        "brewzilla_backend_available": _brewzilla_backend_available(hass),
        **_runtime_result_fields(runtime),
        "snapshot": snapshot,
    }
    _store_autostart_result(hass, result)
    return result


async def _record_transition(
    hass: HomeAssistant,
    *,
    trigger: str,
    changed_entity: str | None = None,
    old_value: Any = None,
    new_value: Any = None,
) -> None:
    if not get_brewday_audit_log(hass).active:
        return
    context = _flight_recorder_context(
        hass,
        trigger=trigger,
        changed_entity=changed_entity,
        old_value=old_value,
        new_value=new_value,
    )
    await async_record_brewday_audit_event(
        hass,
        "flight_recorder_transition",
        note=json.dumps(context, sort_keys=True, default=str, separators=(",", ":")),
        always_record=True,
    )


def async_setup_brewday_audit_autostart(hass: HomeAssistant) -> Callable[[], None]:
    """Register automatic Brewday logging and high-signal black-box transitions."""

    async def _check(trigger: str) -> None:
        result = await async_maybe_autostart_brewday_audit_log(hass, trigger=trigger)
        if result.get("started"):
            await _record_transition(hass, trigger=f"autostart:{trigger}")
        elif result.get("reason") != "audit_already_active":
            _LOGGER.debug("Brewday audit autostart skipped (%s): %s", trigger, result.get("reason"))

    async def _handle_state_change(event: Event) -> None:
        entity_id = str(event.data.get("entity_id") or "")
        old_state = event.data.get("old_state")
        new_state = event.data.get("new_state")
        old_value = getattr(old_state, "state", None)
        new_value = getattr(new_state, "state", None)
        if old_value == new_value:
            return
        await _check(f"state_changed:{entity_id}")
        if get_brewday_audit_log(hass).active:
            await _record_transition(
                hass,
                trigger="state_changed",
                changed_entity=entity_id,
                old_value=old_value,
                new_value=new_value,
            )

    def _schedule_check(trigger: str) -> None:
        hass.create_task(_check(trigger))

    @callback
    def _state_changed(event: Event) -> None:
        hass.create_task(_handle_state_change(event))

    def _scheduled_check(trigger: str) -> Callable[[Any], None]:
        @callback
        def _run(_: Any) -> None:
            _schedule_check(trigger)
        return _run

    @callback
    def _watchdog_tick(_: Any) -> None:
        if not get_brewday_audit_log(hass).active:
            _schedule_check("watchdog_30s")

    remove_state_listener = async_track_state_change_event(
        hass,
        list(FLIGHT_RECORDER_TRIGGER_ENTITIES),
        _state_changed,
    )
    remove_scheduled_checks = [
        async_call_later(hass, INITIAL_CHECK_DELAY_SECONDS, _scheduled_check("initial_check"))
    ]
    remove_scheduled_checks.extend(
        async_call_later(hass, delay, _scheduled_check(f"retry_check_{delay}s"))
        for delay in RETRY_CHECK_DELAYS_SECONDS
    )
    remove_watchdog = async_track_time_interval(
        hass,
        _watchdog_tick,
        timedelta(seconds=WATCHDOG_INTERVAL_SECONDS),
    )

    def _unsub() -> None:
        remove_state_listener()
        remove_watchdog()
        for remove_scheduled_check in remove_scheduled_checks:
            remove_scheduled_check()

    return _unsub
