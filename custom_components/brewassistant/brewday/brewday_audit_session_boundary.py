"""Deterministic Brewday flight-recorder session boundaries.

The original audit autostart intentionally keeps one continuous log across
Manual <-> Brewfather handoffs. A finished brewday, however, must arm a durable
in-memory boundary so the next brewday rotates the recorder even if a new
runtime/orchestration event races ahead and becomes the log's latest event.

This module wraps the existing autostart setup rather than duplicating its
logging behavior. It only owns session-boundary detection and rotation.
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable

from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers.event import async_track_state_change_event

from . import brewday_audit_autostart as autostart
from .brewday_audit import async_start_brewday_audit_log, get_brewday_audit_log

DATA_KEY_BOUNDARY = "brewday_audit_session_boundary"
DATA_KEY_LAST_ROTATION = "brewday_audit_session_rotation_last_result"

TERMINAL_STATES = {"idle", "inactive", "completed", "finished"}
ACTIVE_BREWFATHER_PHASES = {"planning", "brewing"}
INACTIVE_BREWFATHER_PHASES = {"inactive", "fermenting", ""}

_ORIGINAL_SETUP = autostart.async_setup_brewday_audit_autostart
_INSTALLED = False


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def _state_value(hass: HomeAssistant, entity_id: str) -> str:
    state = autostart._entity_state(hass, entity_id)
    return _norm(getattr(state, "state", None))


def _manual_state(hass: HomeAssistant) -> str:
    return _state_value(hass, autostart.MANUAL_STATUS_ENTITY) or "idle"


def _runtime_state(hass: HomeAssistant) -> str:
    return _state_value(hass, autostart.RUNTIME_STATE_ENTITY) or "idle"


def _runtime_source(hass: HomeAssistant) -> str:
    state = autostart._entity_state(hass, autostart.RUNTIME_SOURCE_ENTITY)
    value = str(getattr(state, "state", "") or "").strip()
    return "" if value.lower() in {"", "none", "unknown", "unavailable"} else value


def _brewfather_phase_from_state(state: State | None) -> str:
    if state is None:
        return "inactive"

    attrs = getattr(state, "attributes", {}) or {}
    for key in autostart.BREWFATHER_BATCH_STATUS_ATTRIBUTES:
        phase = _norm(attrs.get(key))
        if phase in {"planning", "brewing", "fermenting"}:
            return phase

    raw = _norm(getattr(state, "state", None))
    if raw in {"planning", "brewing", "fermenting"}:
        return raw

    completed = attrs.get("completed")
    enabled = attrs.get("enabled")
    active = attrs.get("active")
    if completed is True or enabled is False:
        return "inactive"
    if active is True or raw in {"running", "live", "active"}:
        return "brewing"
    return "inactive"


def _brewfather_phase(hass: HomeAssistant) -> str:
    for entity_id in autostart.BREWFATHER_STATUS_ENTITIES:
        state = hass.states.get(entity_id)
        if state is not None:
            return _brewfather_phase_from_state(state)
    return "inactive"


def _log_started_at(hass: HomeAssistant) -> str | None:
    started_at = get_brewday_audit_log(hass).started_at
    return started_at.isoformat() if started_at is not None else None


def _boundary(hass: HomeAssistant) -> dict[str, Any] | None:
    value = hass.data.setdefault("brewassistant", {}).get(DATA_KEY_BOUNDARY)
    return value if isinstance(value, dict) else None


def _arm_boundary(hass: HomeAssistant, *, reason: str) -> None:
    data = hass.data.setdefault("brewassistant", {})
    existing = _boundary(hass)
    if existing and existing.get("armed"):
        return
    data[DATA_KEY_BOUNDARY] = {
        "armed": True,
        "reason": reason,
        "log_started_at": _log_started_at(hass),
    }


def _clear_boundary(hass: HomeAssistant) -> None:
    hass.data.setdefault("brewassistant", {}).pop(DATA_KEY_BOUNDARY, None)


def _current_session_is_terminal(hass: HomeAssistant) -> bool:
    """Return true only when no Manual/BF hot-side runtime still owns Brewday."""
    return bool(
        _runtime_source(hass) == ""
        and _runtime_state(hass) in TERMINAL_STATES
        and _manual_state(hass) in TERMINAL_STATES
        and _brewfather_phase(hass) in INACTIVE_BREWFATHER_PHASES
    )


def _last_log_event_is_terminal(hass: HomeAssistant) -> bool:
    log = get_brewday_audit_log(hass)
    if not log.events:
        return False
    event = log.events[-1]
    state = _norm(event.get("runtime_state") or event.get("status"))
    source = _norm(event.get("source"))
    return state in {"completed", "finished"} or (
        state in {"idle", "inactive"} and source in {"", "none"}
    )


def _manual_session_started(entity_id: str, old_state: State | None, new_state: State | None) -> bool:
    if entity_id == autostart.MANUAL_STATUS_ENTITY:
        return _norm(getattr(new_state, "state", None)) == "prepared" and _norm(
            getattr(old_state, "state", None)
        ) in TERMINAL_STATES
    if entity_id == autostart.RUNTIME_SOURCE_ENTITY:
        new_source = str(getattr(new_state, "state", "") or "").strip()
        old_source = str(getattr(old_state, "state", "") or "").strip()
        return new_source == autostart.MANUAL_RUNTIME_SOURCE and _norm(old_source) in {"", "none"}
    return False


def _brewfather_session_started(entity_id: str, old_state: State | None, new_state: State | None) -> bool:
    if entity_id not in autostart.BREWFATHER_STATUS_ENTITIES:
        return False
    old_phase = _brewfather_phase_from_state(old_state)
    new_phase = _brewfather_phase_from_state(new_state)
    return new_phase in ACTIVE_BREWFATHER_PHASES and old_phase not in ACTIVE_BREWFATHER_PHASES


def _new_session_kind(entity_id: str, old_state: State | None, new_state: State | None) -> str | None:
    if _manual_session_started(entity_id, old_state, new_state):
        return "manual"
    if _brewfather_session_started(entity_id, old_state, new_state):
        return "brewfather"
    return None


async def _rotate_if_armed(
    hass: HomeAssistant,
    *,
    lock: asyncio.Lock,
    session_kind: str,
    trigger: str,
) -> None:
    async with lock:
        boundary = _boundary(hass)
        if not boundary or not boundary.get("armed"):
            return

        log = get_brewday_audit_log(hass)
        if not log.active:
            # The normal autostart path will create a fresh log anyway.
            _clear_boundary(hass)
            return

        armed_started_at = boundary.get("log_started_at")
        current_started_at = _log_started_at(hass)
        if armed_started_at is not None and current_started_at != armed_started_at:
            # Another autostart callback already rotated the recorder.
            _clear_boundary(hass)
            return

        reason = str(boundary.get("reason") or "terminal_runtime")
        note = (
            "Auto-rotated Brewday flight recorder before new "
            f"{session_kind} session ({trigger}; boundary={reason})."
        )
        await async_start_brewday_audit_log(hass, note=note)
        _clear_boundary(hass)
        hass.data.setdefault("brewassistant", {})[DATA_KEY_LAST_ROTATION] = {
            "rotated": True,
            "session_kind": session_kind,
            "trigger": trigger,
            "boundary_reason": reason,
            "started_at": _log_started_at(hass),
        }


def _install_setup_wrapper() -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    def _wrapped_setup(hass: HomeAssistant) -> Callable[[], None]:
        lock = asyncio.Lock()

        # Recover a boundary after an HA restart when the persisted log itself
        # clearly ended at a terminal/no-owner runtime.
        if _last_log_event_is_terminal(hass):
            _arm_boundary(hass, reason="persisted_terminal_log")

        @callback
        def _session_boundary_state_changed(event: Event) -> None:
            entity_id = str(event.data.get("entity_id") or "")
            old_state = event.data.get("old_state")
            new_state = event.data.get("new_state")

            # Arm as soon as the system reaches a true terminal/no-owner state.
            # The latch is independent of the audit log's latest event, so a
            # later orchestration tick cannot erase knowledge of the boundary.
            if _current_session_is_terminal(hass):
                _arm_boundary(hass, reason=f"terminal_state:{entity_id}")

            session_kind = _new_session_kind(entity_id, old_state, new_state)
            if session_kind is None:
                return

            hass.async_create_task(
                _rotate_if_armed(
                    hass,
                    lock=lock,
                    session_kind=session_kind,
                    trigger=f"state_changed:{entity_id}",
                )
            )

        boundary_entities = [
            autostart.MANUAL_STATUS_ENTITY,
            autostart.RUNTIME_SOURCE_ENTITY,
            autostart.RUNTIME_STATE_ENTITY,
            *autostart.BREWFATHER_STATUS_ENTITIES,
        ]
        remove_boundary_listener = async_track_state_change_event(
            hass,
            boundary_entities,
            _session_boundary_state_changed,
        )
        remove_original = _ORIGINAL_SETUP(hass)

        def _unsub() -> None:
            remove_boundary_listener()
            remove_original()

        return _unsub

    autostart.async_setup_brewday_audit_autostart = _wrapped_setup
    _INSTALLED = True


def install_audit_session_boundary_guard() -> None:
    """Install deterministic new-brewday rotation before integration setup."""
    _install_setup_wrapper()
