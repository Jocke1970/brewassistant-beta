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


def build_manual_engine_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    """Return a normalized Manual Brewday snapshot from the Python engine."""
    session = get_manual_brewday_session(hass)
    snapshot = session.to_snapshot()

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
