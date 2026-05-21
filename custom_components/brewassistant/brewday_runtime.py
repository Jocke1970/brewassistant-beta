"""Brewday Runtime normalization and live timer helpers.

This module treats Brewfather Brew Tracker as a snapshot/checkpoint source and
calculates a live Home Assistant runtime between Brewfather updates.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.core import HomeAssistant, State
from homeassistant.util import dt as dt_util

INVALID_STATES = {"unknown", "unavailable", "none", ""}
BREWFATHER_ACTIVE_STATES = {"running", "paused", "completed"}

SOURCE_NONE = "None"
SOURCE_BREWFATHER = "Brewfather Brew Tracker"
SOURCE_MANUAL = "Manual Brewday"

# Brewfather Brew Tracker entities
BF_STATUS = "sensor.brewfather_brew_tracker_status"
BF_STAGE = "sensor.brewfather_brew_tracker_stage"
BF_STEP = "sensor.brewfather_brew_tracker_step"
BF_NEXT_STEP = "sensor.brewfather_brew_tracker_next_step"
BF_PROGRESS = "sensor.brewfather_brew_tracker_progress"
BF_TIME_REMAINING = "sensor.brewfather_brew_tracker_time_remaining"

# Manual Brewday helpers
MANUAL_MODE = "input_select.brewassistant_brewday_mode"
MANUAL_ACTIVE = "input_boolean.brewassistant_brewday_manual_active"
MANUAL_STATUS = "input_select.brewassistant_brewday_manual_status"
MANUAL_STAGE = "input_select.brewassistant_brewday_manual_stage"
MANUAL_STEP = "input_text.brewassistant_brewday_manual_step"
MANUAL_NEXT_STEP = "input_text.brewassistant_brewday_manual_next_step"
MANUAL_STEP_DESCRIPTION = "input_text.brewassistant_brewday_manual_step_description"
MANUAL_NEXT_STEP_DESCRIPTION = "input_text.brewassistant_brewday_manual_next_step_description"
MANUAL_PROGRESS = "input_number.brewassistant_brewday_manual_progress"
MANUAL_TIME_REMAINING_MIN = "input_number.brewassistant_brewday_manual_time_remaining_min"
MANUAL_TARGET_TEMP = "input_number.brewassistant_brewday_manual_target_temp"
MANUAL_ACTUAL_TEMP = "input_number.brewassistant_brewday_manual_actual_temp"


@dataclass(slots=True, frozen=True)
class BrewdayRuntimeSnapshot:
    """Normalized brewday runtime snapshot."""

    source: str
    status: str
    stage: str
    step: str
    next_step: str
    progress: float
    time_remaining_seconds: int
    time_remaining_minutes: int
    target_temperature: float | None
    actual_temperature: float | None
    summary: str
    source_entity: str | None
    snapshot_entity: str | None
    snapshot_updated_at: str | None
    raw_remaining_seconds: int | None
    live_elapsed_since_snapshot_seconds: int
    live_timer_active: bool
    stage_duration_seconds: float | None
    stage_elapsed_seconds: float | None
    stage_remaining_seconds: float | None
    stage_progress_percent: float | None
    current_step_description: str | None
    next_step_description: str | None


def _state(hass: HomeAssistant, entity_id: str, default: str = "") -> str:
    state = hass.states.get(entity_id)
    if state is None or state.state in INVALID_STATES:
        return default
    return state.state


def _state_obj(hass: HomeAssistant, entity_id: str) -> State | None:
    state = hass.states.get(entity_id)
    if state is None or state.state in INVALID_STATES:
        return None
    return state


def _float_state(hass: HomeAssistant, entity_id: str, default: float = 0.0) -> float:
    try:
        return float(_state(hass, entity_id))
    except (TypeError, ValueError):
        return default


def _int_state(hass: HomeAssistant, entity_id: str, default: int = 0) -> int:
    try:
        return int(float(_state(hass, entity_id)))
    except (TypeError, ValueError):
        return default


def _attr(hass: HomeAssistant, entity_id: str, attr: str) -> Any:
    state = hass.states.get(entity_id)
    if state is None:
        return None
    return state.attributes.get(attr)


def _valid_or(value: Any, fallback: str) -> str:
    if value is None or str(value) in INVALID_STATES:
        return fallback
    return str(value)


def _float_or_none(value: Any) -> float | None:
    if value is None or str(value) in INVALID_STATES:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_remaining(seconds: int) -> str:
    minutes = round(seconds / 60)
    if minutes < 60:
        return f"{minutes} min"
    hours = minutes // 60
    remaining_minutes = minutes % 60
    if remaining_minutes:
        return f"{hours} h {remaining_minutes} min"
    return f"{hours} h"


def _manual_active(hass: HomeAssistant) -> bool:
    return _state(hass, MANUAL_ACTIVE) == "on"


def _source(hass: HomeAssistant) -> str:
    mode = _state(hass, MANUAL_MODE, "Auto")
    bf_status = _state(hass, BF_STATUS)
    bf_active = bf_status in BREWFATHER_ACTIVE_STATES

    if mode == "Brewfather Brew Tracker" and bf_active:
        return SOURCE_BREWFATHER
    if mode == "Manual":
        return SOURCE_MANUAL
    if mode == "Auto" and bf_active:
        return SOURCE_BREWFATHER
    if mode == "Auto" and _manual_active(hass):
        return SOURCE_MANUAL
    return SOURCE_NONE


def _brewfather_snapshot_age_seconds(hass: HomeAssistant) -> int:
    """Return age of the Brewfather remaining-time snapshot in seconds."""
    # The time-remaining sensor is the best anchor, because it changes when the
    # Brewfather snapshot changes. Fall back to status if needed.
    snapshot_state = _state_obj(hass, BF_TIME_REMAINING) or _state_obj(hass, BF_STATUS)
    if snapshot_state is None:
        return 0

    age = dt_util.utcnow() - dt_util.as_utc(snapshot_state.last_updated)
    return max(0, int(age.total_seconds()))


def _brewfather_live_remaining(hass: HomeAssistant) -> tuple[int, int, bool]:
    """Return live remaining seconds, snapshot age, and active-countdown flag."""
    status = _state(hass, BF_STATUS, "inactive")
    raw_remaining = _int_state(hass, BF_TIME_REMAINING)
    age_seconds = _brewfather_snapshot_age_seconds(hass)

    if status == "running":
        return max(raw_remaining - age_seconds, 0), age_seconds, True
    if status == "completed":
        return 0, age_seconds, False
    return max(raw_remaining, 0), age_seconds, False


def _brewfather_stage_data(hass: HomeAssistant, live_remaining: int) -> dict[str, Any]:
    current_stage = _attr(hass, BF_STATUS, "current_stage") or {}
    duration = _float_or_none(current_stage.get("duration"))
    progress = _float_or_none(_state(hass, BF_PROGRESS))

    if duration and duration > 0:
        elapsed = max(duration - live_remaining, 0)
        progress = round(min(max((elapsed / duration) * 100, 0), 100), 1)
    else:
        elapsed = _float_or_none(current_stage.get("elapsedSeconds"))

    return {
        "duration": duration,
        "elapsed": elapsed,
        "remaining": live_remaining,
        "progress": progress,
        "paused": current_stage.get("paused"),
        "raw": current_stage,
    }


def _brewfather_target_temperature(hass: HomeAssistant) -> float | None:
    current_step = _attr(hass, BF_STATUS, "current_step") or {}
    next_step = _attr(hass, BF_STATUS, "next_step") or {}
    return _float_or_none(current_step.get("value")) or _float_or_none(next_step.get("value"))


def _brewfather_snapshot(hass: HomeAssistant) -> BrewdayRuntimeSnapshot:
    status = _state(hass, BF_STATUS, "inactive")
    live_remaining, age_seconds, live_timer_active = _brewfather_live_remaining(hass)
    stage_data = _brewfather_stage_data(hass, live_remaining)
    progress = stage_data["progress"] if stage_data["progress"] is not None else 0.0
    snapshot_state = _state_obj(hass, BF_TIME_REMAINING) or _state_obj(hass, BF_STATUS)
    current_step = _attr(hass, BF_STATUS, "current_step") or {}
    next_step = _attr(hass, BF_STATUS, "next_step") or {}

    stage = _valid_or(_state(hass, BF_STAGE), "Unknown")
    step = _valid_or(_state(hass, BF_STEP), "Unknown")
    next_step_name = _valid_or(_state(hass, BF_NEXT_STEP), "None")
    summary = f"{status} · {stage} · {step} · {round(progress)}% · {_format_remaining(live_remaining)} kvar"

    return BrewdayRuntimeSnapshot(
        source=SOURCE_BREWFATHER,
        status=status,
        stage=stage,
        step=step,
        next_step=next_step_name,
        progress=round(float(progress), 1),
        time_remaining_seconds=live_remaining,
        time_remaining_minutes=round(live_remaining / 60),
        target_temperature=_brewfather_target_temperature(hass),
        actual_temperature=None,
        summary=summary,
        source_entity=BF_STATUS,
        snapshot_entity=snapshot_state.entity_id if snapshot_state is not None else None,
        snapshot_updated_at=snapshot_state.last_updated.isoformat() if snapshot_state is not None else None,
        raw_remaining_seconds=_int_state(hass, BF_TIME_REMAINING),
        live_elapsed_since_snapshot_seconds=age_seconds,
        live_timer_active=live_timer_active,
        stage_duration_seconds=stage_data["duration"],
        stage_elapsed_seconds=stage_data["elapsed"],
        stage_remaining_seconds=stage_data["remaining"],
        stage_progress_percent=stage_data["progress"],
        current_step_description=current_step.get("description") or current_step.get("tooltip"),
        next_step_description=next_step.get("description") or next_step.get("tooltip"),
    )


def _manual_snapshot(hass: HomeAssistant) -> BrewdayRuntimeSnapshot:
    status = _state(hass, MANUAL_STATUS, "inactive")
    remaining_seconds = _int_state(hass, MANUAL_TIME_REMAINING_MIN) * 60
    progress = round(_float_state(hass, MANUAL_PROGRESS), 1)
    stage = _state(hass, MANUAL_STAGE, "Setup")
    step = _valid_or(_state(hass, MANUAL_STEP), "Manual step")
    next_step = _valid_or(_state(hass, MANUAL_NEXT_STEP), "None")
    summary = f"{status} · {stage} · {step} · {round(progress)}% · {_format_remaining(remaining_seconds)} kvar"

    return BrewdayRuntimeSnapshot(
        source=SOURCE_MANUAL,
        status=status,
        stage=stage,
        step=step,
        next_step=next_step,
        progress=progress,
        time_remaining_seconds=remaining_seconds,
        time_remaining_minutes=round(remaining_seconds / 60),
        target_temperature=round(_float_state(hass, MANUAL_TARGET_TEMP), 1),
        actual_temperature=round(_float_state(hass, MANUAL_ACTUAL_TEMP), 1),
        summary=summary,
        source_entity=MANUAL_MODE,
        snapshot_entity=None,
        snapshot_updated_at=None,
        raw_remaining_seconds=remaining_seconds,
        live_elapsed_since_snapshot_seconds=0,
        live_timer_active=False,
        stage_duration_seconds=None,
        stage_elapsed_seconds=None,
        stage_remaining_seconds=remaining_seconds,
        stage_progress_percent=progress,
        current_step_description=_state(hass, MANUAL_STEP_DESCRIPTION, ""),
        next_step_description=_state(hass, MANUAL_NEXT_STEP_DESCRIPTION, ""),
    )


def _inactive_snapshot() -> BrewdayRuntimeSnapshot:
    return BrewdayRuntimeSnapshot(
        source=SOURCE_NONE,
        status="inactive",
        stage="Idle",
        step="Idle",
        next_step="None",
        progress=0.0,
        time_remaining_seconds=0,
        time_remaining_minutes=0,
        target_temperature=None,
        actual_temperature=None,
        summary="inactive · Idle",
        source_entity=None,
        snapshot_entity=None,
        snapshot_updated_at=None,
        raw_remaining_seconds=None,
        live_elapsed_since_snapshot_seconds=0,
        live_timer_active=False,
        stage_duration_seconds=None,
        stage_elapsed_seconds=None,
        stage_remaining_seconds=0,
        stage_progress_percent=0,
        current_step_description=None,
        next_step_description=None,
    )


def build_brewday_runtime_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    """Build a normalized brewday runtime snapshot."""
    source = _source(hass)
    if source == SOURCE_BREWFATHER:
        snapshot = _brewfather_snapshot(hass)
    elif source == SOURCE_MANUAL:
        snapshot = _manual_snapshot(hass)
    else:
        snapshot = _inactive_snapshot()

    return {
        "source": snapshot.source,
        "status": snapshot.status,
        "stage": snapshot.stage,
        "step": snapshot.step,
        "next_step": snapshot.next_step,
        "progress": snapshot.progress,
        "time_remaining_seconds": snapshot.time_remaining_seconds,
        "time_remaining_minutes": snapshot.time_remaining_minutes,
        "target_temperature": snapshot.target_temperature,
        "actual_temperature": snapshot.actual_temperature,
        "summary": snapshot.summary,
        "source_entity": snapshot.source_entity,
        "snapshot_entity": snapshot.snapshot_entity,
        "snapshot_updated_at": snapshot.snapshot_updated_at,
        "raw_remaining_seconds": snapshot.raw_remaining_seconds,
        "live_elapsed_since_snapshot_seconds": snapshot.live_elapsed_since_snapshot_seconds,
        "live_timer_active": snapshot.live_timer_active,
        "stage_duration_seconds": snapshot.stage_duration_seconds,
        "stage_elapsed_seconds": snapshot.stage_elapsed_seconds,
        "stage_remaining_seconds": snapshot.stage_remaining_seconds,
        "stage_progress_percent": snapshot.stage_progress_percent,
        "current_step_description": snapshot.current_step_description,
        "next_step_description": snapshot.next_step_description,
    }


def brewday_runtime_attrs(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Return common runtime attributes for Brewday Runtime sensors."""
    return {
        "source": snapshot.get("source"),
        "status": snapshot.get("status"),
        "stage": snapshot.get("stage"),
        "step": snapshot.get("step"),
        "next_step": snapshot.get("next_step"),
        "summary": snapshot.get("summary"),
        "source_entity": snapshot.get("source_entity"),
        "snapshot_entity": snapshot.get("snapshot_entity"),
        "snapshot_updated_at": snapshot.get("snapshot_updated_at"),
        "raw_remaining_seconds": snapshot.get("raw_remaining_seconds"),
        "live_elapsed_since_snapshot_seconds": snapshot.get("live_elapsed_since_snapshot_seconds"),
        "live_timer_active": snapshot.get("live_timer_active"),
        "stage_duration_seconds": snapshot.get("stage_duration_seconds"),
        "stage_elapsed_seconds": snapshot.get("stage_elapsed_seconds"),
        "stage_remaining_seconds": snapshot.get("stage_remaining_seconds"),
        "stage_progress_percent": snapshot.get("stage_progress_percent"),
        "current_step_description": snapshot.get("current_step_description"),
        "next_step_description": snapshot.get("next_step_description"),
    }
