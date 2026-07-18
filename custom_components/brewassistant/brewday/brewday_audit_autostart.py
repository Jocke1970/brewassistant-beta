"""Auto-start Brewday audit log from Brewfather Planning status.

This backend hook keeps the manual Brewday audit start service intact, but starts
recording automatically when a Brewfather Brew Tracker enters Planning and the
BrewZilla/RAPT backend entities are present.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from homeassistant.core import Event, HomeAssistant, State
from homeassistant.helpers.event import async_call_later, async_track_state_change_event

from .brewday_audit import async_start_brewday_audit_log, get_brewday_audit_log

_LOGGER = logging.getLogger(__name__)

BREWFATHER_STATUS_ENTITY = "sensor.brewfather_brew_tracker_status"
PLANNING_STATUS = "planning"

# Brewfather/RAPT may expose the live tracker state as "paused" while the batch
# itself is still in Planning.  The autostart gate must therefore resolve
# Planning from both the entity state and the batch-status attributes.
BREWFATHER_BATCH_STATUS_ATTRIBUTES = (
    "brew_tracker_batch_status",
    "batch_status",
)

# Use the upstream/RCL BrewZilla entities rather than BA-derived sensors so the
# feature only activates when the actual BrewZilla backend/integration is present.
BREWZILLA_BACKEND_ENTITY_CANDIDATES = (
    "number.brewzilla_target_temperature",
    "number.brewzilla_heat_utilization",
    "number.brewzilla_pump_utilization",
    "sensor.brewzilla_temperature",
    "sensor.brewzilla_power",
    "switch.brewzilla_heater",
    "switch.brewzilla_pump",
)

# Initial setup can race RAPT/RCL entity availability after HA restart/update.
# Keep retrying briefly and also react when one of the backend candidates changes.
INITIAL_CHECK_DELAY_SECONDS = 10
RETRY_CHECK_DELAYS_SECONDS = (30, 60, 120, 180, 300)


def _normalize_status(value: Any) -> str | None:
    status = str(value or "").strip().lower()
    return status or None


def _state_available(hass: HomeAssistant, entity_id: str) -> bool:
    state = hass.states.get(entity_id)
    return bool(state is not None and str(state.state).lower() not in {"unknown", "unavailable"})


def _brewfather_backend_available(hass: HomeAssistant) -> bool:
    return _state_available(hass, BREWFATHER_STATUS_ENTITY)


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
    status, _source = _brewfather_status_from_state(hass.states.get(BREWFATHER_STATUS_ENTITY))
    return status


def _brewfather_status_source(hass: HomeAssistant) -> str | None:
    _status, source = _brewfather_status_from_state(hass.states.get(BREWFATHER_STATUS_ENTITY))
    return source


def _autostart_allowed(hass: HomeAssistant) -> tuple[bool, str]:
    if not _brewfather_backend_available(hass):
        return False, "brewfather_backend_missing"
    if not _brewzilla_backend_available(hass):
        return False, "brewzilla_backend_missing"
    if _brewfather_status(hass) != PLANNING_STATUS:
        return False, "brewfather_not_planning"
    if get_brewday_audit_log(hass).active:
        return False, "audit_already_active"
    return True, "brewfather_planning"


async def async_maybe_autostart_brewday_audit_log(
    hass: HomeAssistant,
    *,
    trigger: str,
) -> dict[str, Any]:
    """Start Brewday audit log if Brewfather is Planning and backends exist."""

    allowed, reason = _autostart_allowed(hass)
    if not allowed:
        return {
            "started": False,
            "reason": reason,
            "trigger": trigger,
            "brewfather_status": _brewfather_status(hass),
            "brewfather_status_source": _brewfather_status_source(hass),
            "brewfather_backend_available": _brewfather_backend_available(hass),
            "brewzilla_backend_available": _brewzilla_backend_available(hass),
        }

    note = "Auto-started: Brewfather batch status Planning and BrewZilla/Brewfather backends are available."
    snapshot = await async_start_brewday_audit_log(hass, note=note)
    _LOGGER.info(
        "Brewday audit auto-started from Brewfather Planning (%s, source=%s)",
        trigger,
        _brewfather_status_source(hass),
    )
    return {
        "started": True,
        "reason": reason,
        "trigger": trigger,
        "brewfather_status": _brewfather_status(hass),
        "brewfather_status_source": _brewfather_status_source(hass),
        "brewfather_backend_available": True,
        "brewzilla_backend_available": True,
        "snapshot": snapshot,
    }


def async_setup_brewday_audit_autostart(hass: HomeAssistant) -> Callable[[], None]:
    """Register Brewfather Planning -> Brewday audit autostart hook."""

    async def _check(trigger: str) -> None:
        result = await async_maybe_autostart_brewday_audit_log(hass, trigger=trigger)
        if result.get("started"):
            return
        _LOGGER.debug(
            "Brewday audit autostart skipped (%s): %s",
            result.get("trigger"),
            result.get("reason"),
        )

    def _status_changed(event: Event) -> None:
        old_state = event.data.get("old_state")
        new_state = event.data.get("new_state")
        old_status, _old_source = _brewfather_status_from_state(old_state)
        new_status, _new_source = _brewfather_status_from_state(new_state)
        if old_status == new_status or new_status != PLANNING_STATUS:
            return
        hass.async_create_task(_check("brewfather_status_changed"))

    def _backend_candidate_changed(event: Event) -> None:
        old_state = event.data.get("old_state")
        new_state = event.data.get("new_state")
        old_available = old_state is not None and str(getattr(old_state, "state", "") or "").lower() not in {
            "unknown",
            "unavailable",
        }
        new_available = new_state is not None and str(getattr(new_state, "state", "") or "").lower() not in {
            "unknown",
            "unavailable",
        }
        if old_available == new_available and _brewfather_status(hass) != PLANNING_STATUS:
            return
        hass.async_create_task(_check(f"backend_candidate_changed:{event.data.get('entity_id')}"))

    def _scheduled_check(trigger: str) -> Callable[[Any], None]:
        def _run(_: Any) -> None:
            hass.async_create_task(_check(trigger))

        return _run

    remove_brewfather_listener = async_track_state_change_event(
        hass,
        [BREWFATHER_STATUS_ENTITY],
        _status_changed,
    )
    remove_backend_listener = async_track_state_change_event(
        hass,
        [BREWFATHER_STATUS_ENTITY, *BREWZILLA_BACKEND_ENTITY_CANDIDATES],
        _backend_candidate_changed,
    )
    remove_scheduled_checks = [
        async_call_later(hass, INITIAL_CHECK_DELAY_SECONDS, _scheduled_check("initial_check"))
    ]
    remove_scheduled_checks.extend(
        async_call_later(hass, delay, _scheduled_check(f"retry_check_{delay}s"))
        for delay in RETRY_CHECK_DELAYS_SECONDS
    )

    def _unsub() -> None:
        remove_brewfather_listener()
        remove_backend_listener()
        for remove_scheduled_check in remove_scheduled_checks:
            remove_scheduled_check()

    return _unsub
