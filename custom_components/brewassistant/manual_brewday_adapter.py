"""Adapter helpers for Manual Brewday Runtime.

This module bridges the pure ManualRuntimeSession engine into the normalized
BrewAssistant Brewday Runtime snapshot shape.
"""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .manual_brewday_store import get_manual_brewday_session

BAD = {"unknown", "unavailable", "none", ""}

MANUAL_ACTIVE = "input_boolean.brewassistant_brewday_manual_active"
MANUAL_STATUS = "input_select.brewassistant_brewday_manual_status"
MANUAL_PROGRESS = "input_number.brewassistant_brewday_manual_progress"
MANUAL_REMAINING_MIN = "input_number.brewassistant_brewday_manual_time_remaining_min"
MANUAL_ACTUAL = "input_number.brewassistant_brewday_manual_actual_temp"


def _state(hass: HomeAssistant, entity_id: str, default: str = "") -> str:
    obj = hass.states.get(entity_id)
    if obj is None or obj.state in BAD:
        return default
    return obj.state


def _float_state(hass: HomeAssistant, entity_id: str) -> float | None:
    try:
        value = _state(hass, entity_id)
        if value in BAD:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_state(hass: HomeAssistant, entity_id: str, default: int = 0) -> int:
    value = _float_state(hass, entity_id)
    return default if value is None else int(value)


def _sync_legacy_status(hass: HomeAssistant) -> None:
    """Best-effort legacy helper sync until native services replace scripts.

    Existing dashboard buttons still drive old helpers. This keeps the new
    Python session aligned without recreating it on every update.
    """
    session = get_manual_brewday_session(hass)
    manual_status = _state(hass, MANUAL_STATUS, "inactive")
    manual_active = _state(hass, MANUAL_ACTIVE) == "on"

    if manual_status == "running" and session.state.value not in {"running", "awaiting_confirm"}:
        if session.state.value == "idle":
            session.prepare()
        session.start()
    elif manual_status == "paused" and session.state.value != "paused":
        if session.state.value == "idle":
            session.prepare()
        session.pause()
    elif manual_status == "completed" and session.state.value != "completed":
        session.finish()
    elif manual_active and session.state.value == "idle":
        session.prepare()


def build_manual_engine_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    """Return a normalized Manual Brewday snapshot from the Python engine."""
    _sync_legacy_status(hass)
    session = get_manual_brewday_session(hass)
    snapshot = session.to_snapshot()

    helper_remaining = _int_state(hass, MANUAL_REMAINING_MIN, 0) * 60
    helper_progress = _float_state(hass, MANUAL_PROGRESS)
    actual_temperature = _float_state(hass, MANUAL_ACTUAL)

    if helper_remaining > 0:
        snapshot["time_remaining_seconds"] = helper_remaining
        snapshot["time_remaining_minutes"] = round(helper_remaining / 60)
        snapshot["raw_remaining_seconds"] = helper_remaining
        snapshot["stage_remaining_seconds"] = helper_remaining

    if helper_progress is not None:
        snapshot["progress"] = round(helper_progress, 1)
        snapshot["stage_progress_percent"] = round(helper_progress, 1)

    snapshot.update({
        "source": "Manual Brewday",
        "source_entity": MANUAL_STATUS,
        "snapshot_entity": None,
        "snapshot_updated_at": None,
        "snapshot_age_seconds": 0,
        "snapshot_age_minutes": 0,
        "raw_remaining_seconds": snapshot.get("raw_remaining_seconds", snapshot.get("time_remaining_seconds", 0)),
        "live_elapsed_since_snapshot_seconds": 0,
        "live_timer_active": snapshot.get("status") == "running",
        "refresh_recommended": False,
        "awaiting_snapshot": snapshot.get("runtime_state") == "awaiting_confirm",
        "stage_duration_seconds": None,
        "stage_elapsed_seconds": None,
        "stage_remaining_seconds": snapshot.get("time_remaining_seconds", 0),
        "stage_progress_percent": snapshot.get("progress", 0),
        "actual_temperature": actual_temperature,
    })

    timeline = snapshot.get("timeline") or []
    active_stage = next((stage for stage in timeline if stage.get("active")), None)
    active_step = None
    next_step = None
    if active_stage:
        active_step = next((step for step in active_stage.get("steps", []) if step.get("active")), None)
        next_step = next((step for step in active_stage.get("steps", []) if step.get("upcoming")), None)

    snapshot["current_step_description"] = active_step.get("description") if active_step else None
    snapshot["next_step_description"] = next_step.get("description") if next_step else None

    return snapshot
