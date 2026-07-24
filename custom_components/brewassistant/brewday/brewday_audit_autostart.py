"""Auto-start Brewday audit log from active Brewfather Brewday runtime.

This backend hook keeps the manual Brewday audit start service intact, but starts
recording automatically when Brewfather/Brewday Runtime is active and the
BrewZilla/RAPT backend entities are present.
"""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any, Callable

from homeassistant.core import Event, HomeAssistant, State
from homeassistant.helpers.event import async_call_later, async_track_state_change_event, async_track_time_interval

from .brewday_audit import async_start_brewday_audit_log, get_brewday_audit_log
from .brewday_runtime import build_brewday_runtime_snapshot

_LOGGER = logging.getLogger(__name__)

BREWFATHER_STATUS_ENTITY = "sensor.brewfather_brew_tracker_status"
BREWFATHER_RUNTIME_SOURCE = "Brewfather Brew Tracker"
PLANNING_STATUS = "planning"
DATA_KEY_LAST_RESULT = "brewday_audit_autostart_last_result"

# Brewfather/RAPT may expose the live tracker state as "paused" while the batch
# itself is still in Planning.  The autostart gate therefore keeps the legacy
# Planning fallback, but the primary signal is now the normalized Brewday Runtime.
BREWFATHER_BATCH_STATUS_ATTRIBUTES = (
    "brew_tracker_batch_status",
    "batch_status",
)

ACTIVE_RUNTIME_STATES = {
    "live",
    "running",
    "paused",
    "prepared",
    "awaiting_snapshot",
    "awaiting_confirm",
}
TERMINAL_RUNTIME_STATES = {"idle", "inactive", "completed", "complete", "done", "archived"}
HOT_SIDE_WORDS = (
    "mash",
    "mäsk",
    "ramp",
    "heat",
    "värm",
    "strike",
    "boil",
    "kok",
    "sparge",
    "lak",
    "whirlpool",
    "hop stand",
    "hopstand",
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
# Keep retrying briefly, react when entities change, and keep a lightweight
# watchdog running so an already-active Brewfather runtime is not missed.
INITIAL_CHECK_DELAY_SECONDS = 10
RETRY_CHECK_DELAYS_SECONDS = (30, 60, 120, 180, 300)
WATCHDOG_INTERVAL_SECONDS = 30


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


def _runtime_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    try:
        snapshot = build_brewday_runtime_snapshot(hass)
    except Exception as exc:  # pragma: no cover - diagnostics must never break HA setup
        return {"runtime_error": f"{type(exc).__name__}: {exc}"}
    return snapshot if isinstance(snapshot, dict) else {"runtime_error": "invalid_snapshot"}


def _runtime_state(runtime: dict[str, Any]) -> str:
    return str(runtime.get("runtime_state") or runtime.get("status") or "idle").strip().lower()


def _runtime_text(runtime: dict[str, Any]) -> str:
    return " ".join(
        str(runtime.get(key) or "")
        for key in ("stage", "step", "next_step", "raw_step_name")
    ).lower()


def _runtime_is_brewfather_hot_side(runtime: dict[str, Any]) -> bool:
    source = str(runtime.get("source") or "")
    if source != BREWFATHER_RUNTIME_SOURCE:
        return False

    state = _runtime_state(runtime)
    if state in TERMINAL_RUNTIME_STATES or state not in ACTIVE_RUNTIME_STATES:
        return False
    if bool(runtime.get("completed_runtime")) or bool(runtime.get("terminal_complete_inferred")):
        return False

    text = _runtime_text(runtime)
    target = runtime.get("target_temperature")
    return bool(any(word in text for word in HOT_SIDE_WORDS) or target is not None)


def _autostart_allowed(hass: HomeAssistant) -> tuple[bool, str, dict[str, Any]]:
    runtime = _runtime_snapshot(hass)

    if not _brewfather_backend_available(hass):
        return False, "brewfather_backend_missing", runtime
    if not _brewzilla_backend_available(hass):
        return False, "brewzilla_backend_missing", runtime
    if get_brewday_audit_log(hass).active:
        return False, "audit_already_active", runtime

    if _runtime_is_brewfather_hot_side(runtime):
        return True, "brewfather_runtime_active", runtime

    # Legacy fallback: useful when the normalized runtime has not built a hot-side
    # snapshot yet, but the BF batch is already known to be in Planning.
    if _brewfather_status(hass) == PLANNING_STATUS:
        return True, "brewfather_planning", runtime

    return False, "brewfather_runtime_not_active", runtime


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
        "runtime_raw_step_name": runtime.get("raw_step_name"),
        "runtime_raw_step_index": runtime.get("raw_step_index"),
        "runtime_resolved_step_index": runtime.get("resolved_step_index"),
        "runtime_error": runtime.get("runtime_error"),
    }


async def async_maybe_autostart_brewday_audit_log(
    hass: HomeAssistant,
    *,
    trigger: str,
) -> dict[str, Any]:
    """Start Brewday audit log if Brewfather/Brewday Runtime is active."""

    allowed, reason, runtime = _autostart_allowed(hass)
    if not allowed:
        result = {
            "started": False,
            "reason": reason,
            "trigger": trigger,
            "brewfather_status": _brewfather_status(hass),
            "brewfather_status_source": _brewfather_status_source(hass),
            "brewfather_backend_available": _brewfather_backend_available(hass),
            "brewzilla_backend_available": _brewzilla_backend_available(hass),
            **_runtime_result_fields(runtime),
        }
        _store_autostart_result(hass, result)
        return result

    note = (
        "Auto-started: Brewfather/Brewday Runtime is active and "
        f"BrewZilla/Brewfather backends are available ({trigger}; {reason})."
    )
    snapshot = await async_start_brewday_audit_log(hass, note=note)
    _LOGGER.info(
        "Brewday audit auto-started from %s (%s, BF status source=%s)",
        reason,
        trigger,
        _brewfather_status_source(hass),
    )
    result = {
        "started": True,
        "reason": reason,
        "trigger": trigger,
        "brewfather_status": _brewfather_status(hass),
        "brewfather_status_source": _brewfather_status_source(hass),
        "brewfather_backend_available": True,
        "brewzilla_backend_available": True,
        **_runtime_result_fields(runtime),
        "snapshot": snapshot,
    }
    _store_autostart_result(hass, result)
    return result


def async_setup_brewday_audit_autostart(hass: HomeAssistant) -> Callable[[], None]:
    """Register Brewfather/Brewday Runtime -> Brewday audit autostart hook."""

    async def _check(trigger: str) -> None:
        result = await async_maybe_autostart_brewday_audit_log(hass, trigger=trigger)
        if result.get("started") or result.get("reason") == "audit_already_active":
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
        if old_status == new_status and new_status != PLANNING_STATUS:
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
        if old_available == new_available and not _runtime_is_brewfather_hot_side(_runtime_snapshot(hass)):
            return
        hass.async_create_task(_check(f"backend_candidate_changed:{event.data.get('entity_id')}"))

    def _scheduled_check(trigger: str) -> Callable[[Any], None]:
        def _run(_: Any) -> None:
            hass.async_create_task(_check(trigger))

        return _run

    def _watchdog_tick(_: Any) -> None:
        if get_brewday_audit_log(hass).active:
            return
        # The watchdog intentionally does not require a state_changed event.  If
        # Brewfather is already active when BA is loaded, or if an attribute update
        # is missed by HA/RAPT, this still converges within one interval.
        hass.async_create_task(_check("watchdog_30s"))

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
    remove_watchdog = async_track_time_interval(hass, _watchdog_tick, timedelta(seconds=WATCHDOG_INTERVAL_SECONDS))

    def _unsub() -> None:
        remove_brewfather_listener()
        remove_backend_listener()
        remove_watchdog()
        for remove_scheduled_check in remove_scheduled_checks:
            remove_scheduled_check()

    return _unsub
