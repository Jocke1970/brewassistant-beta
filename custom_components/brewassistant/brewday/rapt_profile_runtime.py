"""RAPT BrewZilla profile runtime adapter for BrewAssistant.

RAPT/RAPT Cloud Link supplies the active BrewZilla profile, current process
step, target and next-step context. BrewAssistant normalizes that information
into Brewday Runtime. The BrewZilla profile runner owns step/timer progression;
BrewAssistant owns hot-side target transport and heat/pump regulation while the
RAPT control bridge is installed.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util import dt as dt_util

from ..const import DOMAIN
from ..brewzilla.brewzilla_owned_control import (
    BREWZILLA_HEAT_UTILIZATION,
    BREWZILLA_PUMP_UTILIZATION,
    clear_owned_control,
)

_LOGGER = logging.getLogger(__name__)

RAPT_PROFILE_SOURCE = "RAPT BrewZilla Profile"
RAPT_PROFILE_ENTITY = "binary_sensor.brewzilla_profile_active"
RAPT_PROFILE_BA_SOURCE = "rapt_cloud_link_brewzilla_profile_runtime"
RAPT_PROFILE_RUNTIME_STATE = "running"

BREWZILLA_HEATER_SWITCH = "switch.brewzilla_heater"
BREWZILLA_PUMP_SWITCH = "switch.brewzilla_pump"
BREWZILLA_TEMPERATURE = "sensor.brewzilla_temperature"

DATA_KEY = "rapt_brewzilla_profile_runtime"
LISTENER_KEY = "rapt_brewzilla_profile_runtime_listener"

_BAD = {"unknown", "unavailable", "none", ""}


def _store(hass: HomeAssistant) -> dict[str, Any]:
    return hass.data.setdefault(DOMAIN, {}).setdefault(
        DATA_KEY,
        {
            "was_active": False,
            "last_known": {},
            "active_session_key": None,
            "control_cleared_for_session": None,
            "source_unavailable_since": None,
            "stop_guard_active": False,
            "stopped_at": None,
            "safe_off_token": None,
            "last_safe_off": None,
        },
    )


def _profile_state(hass: HomeAssistant) -> State | None:
    """Return the operational RCL profile entity when available."""
    state = hass.states.get(RAPT_PROFILE_ENTITY)
    if state is not None:
        return state

    # Fallback for a renamed BrewZilla entity. The BA source marker is the
    # stable contract; entity-id discovery is intentionally read-only.
    try:
        states = hass.states.async_all()
    except AttributeError:
        return None
    for candidate in states:
        if (
            candidate.entity_id.startswith("binary_sensor.")
            and candidate.attributes.get("ba_source") == RAPT_PROFILE_BA_SOURCE
        ):
            return candidate
    return None


def _is_restored(state: State | None) -> bool:
    if state is None:
        return False
    value = state.attributes.get("restored")
    return value is True or str(value).strip().lower() in {"true", "on", "1", "yes"}


def _is_rcl_contract(state: State | None) -> bool:
    return bool(
        state is not None
        and state.attributes.get("ba_source") == RAPT_PROFILE_BA_SOURCE
        and not _is_restored(state)
    )


def _active_contract(state: State | None) -> bool:
    return bool(_is_rcl_contract(state) and state is not None and state.state == "on")


def _fresh_stopped_contract(state: State | None) -> bool:
    return bool(_is_rcl_contract(state) and state is not None and state.state == "off")


def _safe_float(value: Any) -> float | None:
    try:
        if value is None or str(value).strip().lower() in _BAD:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int | None:
    number = _safe_float(value)
    return int(number) if number is not None else None


def _actual_temperature(hass: HomeAssistant) -> float | None:
    state = hass.states.get(BREWZILLA_TEMPERATURE)
    return _safe_float(state.state) if state is not None else None


def _snapshot_age(state: State | None) -> tuple[int | None, str | None]:
    if state is None:
        return None, None
    age = max(0, int((dt_util.utcnow() - dt_util.as_utc(state.last_updated)).total_seconds()))
    return age, state.last_updated.isoformat()


def _last_known_from_state(state: State) -> dict[str, Any]:
    attrs = state.attributes
    return {
        "entity_id": state.entity_id,
        "profile_id": attrs.get("profile_id"),
        "profile_name": attrs.get("profile_name"),
        "profile_session_id": attrs.get("profile_session_id"),
        "profile_session_start_date": attrs.get("profile_session_start_date"),
        "profile_length": attrs.get("profile_length"),
        "profile_contract_complete": bool(attrs.get("profile_contract_complete")),
        "step_id": attrs.get("step_id"),
        "step_number": attrs.get("step_number"),
        "step_name": attrs.get("step_name"),
        "step_target_temperature": attrs.get("step_target_temperature"),
        "step_control_type": attrs.get("step_control_type"),
        "step_end_type": attrs.get("step_end_type"),
        "step_duration_type": attrs.get("step_duration_type"),
        "step_length": attrs.get("step_length"),
        "step_pid_enabled": attrs.get("step_pid_enabled"),
        "next_step_id": attrs.get("next_step_id"),
        "next_step_name": attrs.get("next_step_name"),
        "next_step_target_temperature": attrs.get("next_step_target_temperature"),
        "step_count": attrs.get("step_count"),
        "profile_steps": attrs.get("profile_steps") if isinstance(attrs.get("profile_steps"), list) else [],
        "profile_steps_truncated": bool(attrs.get("profile_steps_truncated")),
    }


def _remember_active(hass: HomeAssistant, state: State) -> dict[str, Any]:
    store = _store(hass)
    known = _last_known_from_state(state)
    session_key = known.get("profile_session_id") or known.get("profile_id")

    store.update(
        {
            "was_active": True,
            "last_known": known,
            "active_session_key": session_key,
            "source_unavailable_since": None,
            "stop_guard_active": False,
            "stopped_at": None,
        }
    )

    # RAPT now owns process intent. Drop utilization remembered from an earlier
    # Brewfather/Manual session so that the new RAPT session starts with fresh
    # BA calculations rather than inheriting stale Advice ownership.
    if session_key and store.get("control_cleared_for_session") != session_key:
        clear_owned_control(hass, reason="rapt_profile_source_started")
        store["control_cleared_for_session"] = session_key

    return known


def _mark_source_unavailable(hass: HomeAssistant) -> None:
    store = _store(hass)
    if store.get("was_active") and not store.get("source_unavailable_since"):
        store["source_unavailable_since"] = dt_util.utcnow().isoformat()


def _mark_confirmed_stop(hass: HomeAssistant, state: State) -> str:
    store = _store(hass)
    stopped_at = state.last_updated.isoformat()
    session_key = store.get("active_session_key") or store.get("last_known", {}).get("profile_id") or "unknown"
    token = f"{session_key}:{stopped_at}"
    store.update(
        {
            "was_active": False,
            "source_unavailable_since": None,
            "stop_guard_active": True,
            "stopped_at": stopped_at,
            "active_session_key": None,
        }
    )
    clear_owned_control(hass, reason="rapt_profile_stop_confirmed")
    return token


async def _async_call_if_entity_exists(
    hass: HomeAssistant,
    domain: str,
    service: str,
    entity_id: str,
    data: dict[str, Any] | None = None,
) -> str:
    if hass.states.get(entity_id) is None:
        return f"missing:{entity_id}"
    payload = {"entity_id": entity_id, **(data or {})}
    await hass.services.async_call(domain, service, payload, blocking=True)
    return f"{service}:{entity_id}"


async def _async_safe_off_after_profile_stop(hass: HomeAssistant, token: str) -> None:
    """Force the BrewZilla into BA's safe output state after confirmed STOP."""
    store = _store(hass)
    if store.get("safe_off_token") == token:
        return

    # Claim the token before any awaited call so duplicate state callbacks do
    # not issue the same cloud commands in parallel.
    store["safe_off_token"] = token
    actions: list[str] = []
    errors: list[str] = []

    operations = (
        ("switch", "turn_off", BREWZILLA_HEATER_SWITCH, None),
        ("switch", "turn_off", BREWZILLA_PUMP_SWITCH, None),
        ("number", "set_value", BREWZILLA_HEAT_UTILIZATION, {"value": 0}),
        ("number", "set_value", BREWZILLA_PUMP_UTILIZATION, {"value": 0}),
    )
    for domain, service, entity_id, data in operations:
        try:
            actions.append(
                await _async_call_if_entity_exists(hass, domain, service, entity_id, data)
            )
        except Exception as err:  # noqa: BLE001 - each safe command is best-effort
            errors.append(f"{entity_id}:{err}")
            _LOGGER.exception("RAPT profile STOP safe-off failed for %s", entity_id)

    result = {
        "token": token,
        "at": dt_util.utcnow().isoformat(),
        "actions": actions,
        "errors": errors,
        "ok": not errors,
    }
    store["last_safe_off"] = result
    _LOGGER.warning("RAPT BrewZilla profile STOP safe-off: %s", result)


async def _async_process_transition(hass: HomeAssistant, state: State | None) -> None:
    store = _store(hass)

    if _active_contract(state):
        _remember_active(hass, state)  # type: ignore[arg-type]
        return

    if _fresh_stopped_contract(state) and store.get("was_active"):
        token = _mark_confirmed_stop(hass, state)  # type: ignore[arg-type]
        await _async_safe_off_after_profile_stop(hass, token)
        return

    if store.get("was_active"):
        _mark_source_unavailable(hass)


def _ensure_transition_listener(hass: HomeAssistant) -> None:
    data = hass.data.setdefault(DOMAIN, {})
    if LISTENER_KEY in data:
        return

    @callback
    def _state_changed(event: Event) -> None:
        hass.async_create_task(_async_process_transition(hass, event.data.get("new_state")))

    data[LISTENER_KEY] = async_track_state_change_event(
        hass,
        [RAPT_PROFILE_ENTITY],
        _state_changed,
    )


def _step_timeline(known: dict[str, Any]) -> list[dict[str, Any]]:
    raw_steps = known.get("profile_steps")
    if not isinstance(raw_steps, list):
        return []

    current_id = known.get("step_id")
    current_number = _safe_int(known.get("step_number"))
    rows: list[dict[str, Any]] = []
    for index, raw_step in enumerate(raw_steps):
        if not isinstance(raw_step, dict):
            continue
        number = _safe_int(raw_step.get("step_number")) or index + 1
        step_id = raw_step.get("id")
        active = bool(current_id and step_id == current_id)
        completed = bool(current_number is not None and number < current_number)
        upcoming = not active and not completed
        name = str(raw_step.get("name") or f"Step {number}")
        rows.append(
            {
                "index": index,
                "step_number": number,
                "name": name,
                "raw_name": name,
                "type": raw_step.get("control_type"),
                "value": raw_step.get("target_temperature"),
                "rapt_end_type": raw_step.get("end_type"),
                "rapt_duration_type": raw_step.get("duration_type"),
                "rapt_length": raw_step.get("length"),
                "completed": completed,
                "active": active,
                "upcoming": upcoming,
                "state": "active" if active else "completed" if completed else "upcoming",
            }
        )
    return rows


def _active_snapshot(hass: HomeAssistant, state: State, known: dict[str, Any]) -> dict[str, Any]:
    age, updated_at = _snapshot_age(state)
    step_number = _safe_int(known.get("step_number"))
    step_count = _safe_int(known.get("step_count")) or 0
    progress = 0.0
    if step_number is not None and step_count > 0:
        progress = round(max(0.0, min(100.0, ((step_number - 1) / step_count) * 100.0)), 1)

    step_name = str(known.get("step_name") or (f"Step {step_number}" if step_number else "Profile step"))
    profile_name = str(known.get("profile_name") or "RAPT BrewZilla profile")
    next_name = str(known.get("next_step_name") or "None")
    target = _safe_float(known.get("step_target_temperature"))
    steps = _step_timeline(known)

    return {
        "source": RAPT_PROFILE_SOURCE,
        "status": "running",
        "source_status": "active",
        "runtime_state": RAPT_PROFILE_RUNTIME_STATE,
        "stage": "RAPT Profile",
        "step": step_name,
        "raw_step_name": step_name,
        "next_step": next_name,
        "progress": progress,
        "progress_basis": "profile_step_index",
        "time_remaining_seconds": None,
        "time_remaining_minutes": None,
        "target_temperature": target,
        "target_temperature_source": "rapt_profile_step",
        "actual_temperature": _actual_temperature(hass),
        "summary": f"RAPT directive · {profile_name} · {step_name}",
        "source_entity": state.entity_id,
        "source_entity_candidates": [RAPT_PROFILE_ENTITY],
        "snapshot_entity": state.entity_id,
        "snapshot_updated_at": updated_at,
        "snapshot_age_seconds": age,
        "snapshot_age_minutes": round(age / 60, 1) if age is not None else None,
        "raw_remaining_seconds": None,
        "raw_stage_remaining_seconds": None,
        "live_elapsed_since_snapshot_seconds": 0,
        "live_timer_active": False,
        "refresh_recommended": False,
        "awaiting_snapshot": False,
        "paused_freeze": False,
        "stage_paused": False,
        "current_step_pause_before": False,
        "next_step_pause_before": False,
        "confirmation_hint": False,
        "terminal_complete_inferred": False,
        "stage_duration_seconds": None,
        "stage_elapsed_seconds": None,
        "stage_remaining_seconds": None,
        "stage_remaining_minutes": None,
        "stage_progress_percent": progress,
        "raw_step_index": (step_number - 1) if step_number is not None else None,
        "resolved_step_index": (step_number - 1) if step_number is not None else None,
        "current_step_remaining_seconds": None,
        "current_step_remaining_minutes": None,
        "current_step_description": None,
        "next_step_description": None,
        "timeline": [
            {
                "index": 0,
                "name": profile_name,
                "type": "rapt_profile",
                "duration": None,
                "remaining_seconds": None,
                "progress_percent": progress,
                "paused": False,
                "completed": False,
                "active": True,
                "upcoming": False,
                "state": "active",
                "steps": steps,
            }
        ],
        "process_executor": "rapt_profile_step_runner",
        "control_owner": "brewassistant",
        "brewassistant_role": "hot_side_controller",
        "profile_active": True,
        "profile_contract_complete": bool(known.get("profile_contract_complete")),
        "profile_id": known.get("profile_id"),
        "profile_name": known.get("profile_name"),
        "profile_session_id": known.get("profile_session_id"),
        "profile_session_start_date": known.get("profile_session_start_date"),
        "profile_length": known.get("profile_length"),
        "profile_step_id": known.get("step_id"),
        "profile_step_number": step_number,
        "profile_step_control_type": known.get("step_control_type"),
        "profile_step_end_type": known.get("step_end_type"),
        "profile_step_duration_type": known.get("step_duration_type"),
        "profile_step_length": known.get("step_length"),
        "profile_step_pid_enabled": known.get("step_pid_enabled"),
        "profile_next_step_id": known.get("next_step_id"),
        "profile_next_step_target_temperature": known.get("next_step_target_temperature"),
        "profile_step_count": step_count,
        "profile_steps_truncated": bool(known.get("profile_steps_truncated")),
        "profile_source_available": True,
        "profile_stop_guard_active": False,
        "profile_stop_confirmed": False,
        "direct_brewzilla_control_allowed": True,
    }


def _unavailable_snapshot(hass: HomeAssistant, store: dict[str, Any]) -> dict[str, Any]:
    known = store.get("last_known") if isinstance(store.get("last_known"), dict) else {}
    profile_name = str(known.get("profile_name") or "RAPT BrewZilla profile")
    step_name = str(known.get("step_name") or "Last known step")
    return {
        "source": RAPT_PROFILE_SOURCE,
        "status": "unavailable",
        "source_status": "unavailable",
        "runtime_state": "source_unavailable",
        "stage": "RAPT Profile",
        "step": step_name,
        "raw_step_name": step_name,
        "next_step": "None",
        "progress": None,
        "time_remaining_seconds": None,
        "time_remaining_minutes": None,
        "target_temperature": None,
        "target_temperature_source": None,
        "actual_temperature": _actual_temperature(hass),
        "summary": f"source unavailable · holding RAPT ownership · {profile_name} · {step_name}",
        "source_entity": known.get("entity_id") or RAPT_PROFILE_ENTITY,
        "source_entity_candidates": [RAPT_PROFILE_ENTITY],
        "snapshot_entity": known.get("entity_id") or RAPT_PROFILE_ENTITY,
        "snapshot_updated_at": None,
        "snapshot_age_seconds": None,
        "snapshot_age_minutes": None,
        "live_timer_active": False,
        "refresh_recommended": False,
        "awaiting_snapshot": True,
        "paused_freeze": True,
        "terminal_complete_inferred": False,
        "raw_step_index": None,
        "resolved_step_index": None,
        "current_step_remaining_seconds": None,
        "current_step_remaining_minutes": None,
        "timeline": [],
        "process_executor": "rapt_profile_step_runner_unknown_state",
        "control_owner": "unknown_preserve_rapt_handoff",
        "brewassistant_role": "control_suspended_source_unavailable",
        "profile_active": None,
        "profile_id": known.get("profile_id"),
        "profile_name": known.get("profile_name"),
        "profile_session_id": known.get("profile_session_id"),
        "profile_step_id": known.get("step_id"),
        "profile_step_number": known.get("step_number"),
        "profile_source_available": False,
        "profile_source_unavailable_since": store.get("source_unavailable_since"),
        "profile_stop_guard_active": False,
        "profile_stop_confirmed": False,
        "direct_brewzilla_control_allowed": False,
    }


def _stopped_snapshot(hass: HomeAssistant, state: State | None, store: dict[str, Any]) -> dict[str, Any]:
    known = store.get("last_known") if isinstance(store.get("last_known"), dict) else {}
    profile_name = str(known.get("profile_name") or "RAPT BrewZilla profile")
    _, updated_at = _snapshot_age(state)
    return {
        "source": RAPT_PROFILE_SOURCE,
        "status": "stopped",
        "source_status": "stopped",
        "runtime_state": "inactive",
        "stage": "Idle",
        "step": "Profile stopped",
        "raw_step_name": known.get("step_name"),
        "next_step": "None",
        "progress": None,
        "time_remaining_seconds": None,
        "time_remaining_minutes": None,
        "target_temperature": None,
        "target_temperature_source": None,
        "actual_temperature": _actual_temperature(hass),
        "summary": f"stopped · safe-off · RAPT handoff guard · {profile_name}",
        "source_entity": state.entity_id if state is not None else RAPT_PROFILE_ENTITY,
        "source_entity_candidates": [RAPT_PROFILE_ENTITY],
        "snapshot_entity": state.entity_id if state is not None else RAPT_PROFILE_ENTITY,
        "snapshot_updated_at": updated_at,
        "snapshot_age_seconds": 0 if state is not None else None,
        "snapshot_age_minutes": 0 if state is not None else None,
        "live_timer_active": False,
        "refresh_recommended": False,
        "awaiting_snapshot": False,
        "paused_freeze": False,
        "terminal_complete_inferred": False,
        "raw_step_index": None,
        "resolved_step_index": None,
        "current_step_remaining_seconds": None,
        "current_step_remaining_minutes": None,
        "timeline": [],
        "process_executor": "none",
        "control_owner": "none",
        "brewassistant_role": "handoff_guard",
        "profile_active": False,
        "profile_id": known.get("profile_id"),
        "profile_name": known.get("profile_name"),
        "profile_session_id": known.get("profile_session_id"),
        "profile_source_available": True,
        "profile_stop_guard_active": True,
        "profile_stop_confirmed": True,
        "profile_stopped_at": store.get("stopped_at"),
        "profile_last_safe_off": store.get("last_safe_off"),
        "direct_brewzilla_control_allowed": False,
    }


def build_rapt_profile_runtime_snapshot(hass: HomeAssistant) -> dict[str, Any] | None:
    """Return a normalized RAPT profile runtime while it owns the handoff."""
    _ensure_transition_listener(hass)
    store = _store(hass)
    state = _profile_state(hass)

    if _active_contract(state):
        known = _remember_active(hass, state)  # type: ignore[arg-type]
        return _active_snapshot(hass, state, known)  # type: ignore[arg-type]

    if _fresh_stopped_contract(state):
        if store.get("was_active"):
            token = _mark_confirmed_stop(hass, state)  # type: ignore[arg-type]
            if store.get("safe_off_token") != token:
                hass.async_create_task(_async_safe_off_after_profile_stop(hass, token))
        if store.get("stop_guard_active"):
            return _stopped_snapshot(hass, state, store)
        return None

    if store.get("was_active"):
        _mark_source_unavailable(hass)
        return _unavailable_snapshot(hass, store)

    if store.get("stop_guard_active"):
        return _stopped_snapshot(hass, state, store)

    return None


def rapt_profile_runtime_claims_source(hass: HomeAssistant) -> bool:
    """Return true while RAPT owns, has lost, or guards the runtime handoff."""
    return build_rapt_profile_runtime_snapshot(hass) is not None


def clear_rapt_profile_stop_guard(hass: HomeAssistant, *, reason: str) -> bool:
    """Explicitly release a confirmed STOP handoff guard.

    This never releases an active or unavailable-after-active RAPT profile.
    It is intentionally not called automatically by Brewfather state changes.
    """
    store = _store(hass)
    state = _profile_state(hass)
    if _active_contract(state) or store.get("was_active"):
        return False
    if not store.get("stop_guard_active"):
        return False
    store["stop_guard_active"] = False
    store["stop_guard_released_at"] = dt_util.utcnow().isoformat()
    store["stop_guard_release_reason"] = reason
    return True
