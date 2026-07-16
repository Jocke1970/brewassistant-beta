"""Install equipment-learning fields into BrewZilla learning snapshots."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from ..const import DOMAIN
from . import brewzilla_advice_control as advice_control
from . import brewzilla_learning as learning
from .brewzilla_equipment_learning import (
    DATA_KEY,
    async_record_equipment_learning_observation,
    async_setup_equipment_learning,
    build_equipment_learning_snapshot,
)

_INSTALLED = False
_ORIGINAL_BUILD = None


def _runtime(hass: HomeAssistant) -> dict[str, Any]:
    return hass.data.setdefault(DOMAIN, {}).setdefault(DATA_KEY, {})


def _setup_started(hass: HomeAssistant) -> bool:
    runtime = _runtime(hass)
    if runtime.get("setup_complete"):
        return True
    if runtime.get("setup_started"):
        return False
    runtime["setup_started"] = True
    runtime["setup_task"] = hass.async_create_task(async_setup_equipment_learning(hass))
    return False


def _schedule_observation(hass: HomeAssistant) -> None:
    runtime = _runtime(hass)
    task = runtime.get("record_task")
    if task is not None and not task.done():
        return
    runtime["record_task"] = hass.async_create_task(
        async_record_equipment_learning_observation(hass, reason="learning_snapshot")
    )


def _suggestion_summary(suggestion: dict[str, Any] | None) -> str | None:
    if not isinstance(suggestion, dict):
        return None
    parameter = suggestion.get("parameter")
    value = suggestion.get("suggested_floor")
    confidence = suggestion.get("confidence")
    if parameter is None or value is None:
        return None
    return f"{parameter} → {value}% ({confidence})"


def _with_equipment_learning(hass: HomeAssistant, snapshot: dict[str, Any]) -> dict[str, Any]:
    out = dict(snapshot)
    loaded = _setup_started(hass)
    if loaded:
        _schedule_observation(hass)

    equipment = build_equipment_learning_snapshot(hass)
    suggestion = equipment.get("last_suggestion") if isinstance(equipment.get("last_suggestion"), dict) else None
    out.update(
        {
            "equipment_learning_active": True,
            "equipment_learning_loaded": loaded,
            "equipment_learning_mode": equipment.get("mode"),
            "equipment_learning_summary": equipment.get("summary"),
            "equipment_learning_equipment_id": equipment.get("equipment_id"),
            "equipment_learning_observations_total": equipment.get("observations_total"),
            "equipment_learning_segment_count": equipment.get("segment_count"),
            "equipment_learning_current_profile_key": equipment.get("current_profile_key"),
            "equipment_learning_current_segment_count": equipment.get("current_segment_count"),
            "equipment_learning_last_observation_at": equipment.get("last_observation_at"),
            "equipment_learning_suggestion_summary": _suggestion_summary(suggestion),
            "equipment_learning_last_suggestion": suggestion,
            "equipment_learning_last_record_result": equipment.get("last_record_result"),
            "equipment_learning_updated_at": equipment.get("updated_at"),
            "equipment_learning_last_saved_at": equipment.get("last_saved_at"),
        }
    )
    return out


def build_brewzilla_learning_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    assert _ORIGINAL_BUILD is not None
    return _with_equipment_learning(hass, _ORIGINAL_BUILD(hass))


def install_equipment_learning_patch() -> None:
    """Install the equipment-learning snapshot wrapper."""
    global _INSTALLED, _ORIGINAL_BUILD
    if _INSTALLED:
        return
    _ORIGINAL_BUILD = learning.build_brewzilla_learning_snapshot
    learning.build_brewzilla_learning_snapshot = build_brewzilla_learning_snapshot
    advice_control.build_brewzilla_learning_snapshot = build_brewzilla_learning_snapshot
    _INSTALLED = True
