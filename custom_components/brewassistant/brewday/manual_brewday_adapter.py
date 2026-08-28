"""Adapter helpers for Manual Brewday Runtime.

This module bridges the pure ManualRuntimeSession engine into the normalized
BrewAssistant Brewday Runtime snapshot shape.

The Python manual runtime is the source of truth. Legacy YAML/helper state is
not synchronized into the engine in the Python-only branch.
"""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .manual_brewday_store import get_manual_brewday_session

MANUAL_TARGET_OVERRIDE = "switch.brewassistant_brewzilla_manual_target_override"
MANUAL_TARGET_NUMBER = "number.brewassistant_brewzilla_manual_target_temperature"


def _state(hass: HomeAssistant, entity_id: str):
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


def _state_float(hass: HomeAssistant, entity_id: str) -> float | None:
    state = _state(hass, entity_id)
    if state is None or state.state in {"unknown", "unavailable", "none", ""}:
        return None
    try:
        return float(str(state.state).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _state_is_on(hass: HomeAssistant, entity_id: str) -> bool:
    state = _state(hass, entity_id)
    return state is not None and str(state.state).lower() == "on"


def build_manual_engine_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    """Return a normalized Manual Brewday snapshot from the Python engine."""
    session = get_manual_brewday_session(hass)
    snapshot = session.to_snapshot()

    step_target = snapshot.get("target_temperature")
    target_override = _state_is_on(hass, MANUAL_TARGET_OVERRIDE)
    operator_target = _state_float(hass, MANUAL_TARGET_NUMBER) if target_override else None
    if operator_target is not None:
        snapshot["target_temperature"] = operator_target

    snapshot.update({
        "source": "Manual Brewday",
        "source_entity": "python_manual_runtime",
        "snapshot_entity": None,
        "snapshot_updated_at": None,
        "snapshot_age_seconds": 0,
        "snapshot_age_minutes": 0,
        "raw_remaining_seconds": snapshot.get("time_remaining_seconds", 0),
        "live_elapsed_since_snapshot_seconds": 0,
        "live_timer_active": snapshot.get("status") == "running",
        "refresh_recommended": False,
        "awaiting_snapshot": snapshot.get("runtime_state") == "awaiting_confirm",
        "stage_duration_seconds": None,
        "stage_elapsed_seconds": None,
        "stage_remaining_seconds": snapshot.get("time_remaining_seconds", 0),
        "stage_progress_percent": snapshot.get("progress", 0),
        "actual_temperature": None,
        "step_target_temperature": step_target,
        "operator_target_temperature": operator_target,
        "operator_target_entity": MANUAL_TARGET_NUMBER,
        "target_override_active": bool(target_override and operator_target is not None),
        "target_temperature_source": (
            "operator_override" if target_override and operator_target is not None else "manual_step"
        ),
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
