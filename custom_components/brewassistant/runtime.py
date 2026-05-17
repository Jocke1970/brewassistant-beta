"""Runtime normalization helpers for BrewAssistant."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .const import (
    CONF_RUNTIME_COLD_CRASH_TARGET_ENTITY,
    CONF_RUNTIME_PRIMARY_TARGET_ENTITY,
    CONF_RUNTIME_RECIPE_NAME_ENTITY,
    CONF_RUNTIME_STATUS_ENTITY,
    CONF_RUNTIME_TARGET_FG_ENTITY,
)

BAD_STATES = {"unknown", "unavailable", "none", ""}
NUMERIC_KEYS = {
    CONF_RUNTIME_PRIMARY_TARGET_ENTITY,
    CONF_RUNTIME_COLD_CRASH_TARGET_ENTITY,
    CONF_RUNTIME_TARGET_FG_ENTITY,
}


def _state(hass: HomeAssistant, entity_id: str | None) -> str | None:
    """Return a usable string state."""
    if not entity_id:
        return None
    state_obj = hass.states.get(entity_id)
    if state_obj is None or state_obj.state.lower() in BAD_STATES:
        return None
    return str(state_obj.state)


def _float_state(hass: HomeAssistant, entity_id: str | None) -> float | None:
    """Return a usable float state."""
    value = _state(hass, entity_id)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _available(hass: HomeAssistant, entity_id: str | None, *, numeric: bool = False) -> bool:
    """Return whether a runtime source exists and has a usable value."""
    if not entity_id:
        return False
    state_obj = hass.states.get(entity_id)
    if state_obj is None or state_obj.state.lower() in BAD_STATES:
        return False
    if numeric:
        try:
            float(state_obj.state)
        except (TypeError, ValueError):
            return False
    return True


def build_runtime_snapshot(hass: HomeAssistant, configured_entities: dict[str, Any]) -> dict[str, Any]:
    """Return normalized runtime data from configured source entities."""
    recipe_entity = str(configured_entities.get(CONF_RUNTIME_RECIPE_NAME_ENTITY, ""))
    status_entity = str(configured_entities.get(CONF_RUNTIME_STATUS_ENTITY, ""))
    primary_entity = str(configured_entities.get(CONF_RUNTIME_PRIMARY_TARGET_ENTITY, ""))
    crash_entity = str(configured_entities.get(CONF_RUNTIME_COLD_CRASH_TARGET_ENTITY, ""))
    fg_entity = str(configured_entities.get(CONF_RUNTIME_TARGET_FG_ENTITY, ""))

    recipe_name = _state(hass, recipe_entity) or "No active recipe"
    status = _state(hass, status_entity) or "Unknown"
    primary = _float_state(hass, primary_entity)
    cold_crash = _float_state(hass, crash_entity)
    target_fg = _float_state(hass, fg_entity)

    availability = {
        CONF_RUNTIME_RECIPE_NAME_ENTITY: _available(hass, recipe_entity),
        CONF_RUNTIME_STATUS_ENTITY: _available(hass, status_entity),
        CONF_RUNTIME_PRIMARY_TARGET_ENTITY: _available(hass, primary_entity, numeric=True),
        CONF_RUNTIME_COLD_CRASH_TARGET_ENTITY: _available(hass, crash_entity, numeric=True),
        CONF_RUNTIME_TARGET_FG_ENTITY: _available(hass, fg_entity, numeric=True),
    }

    available_count = sum(1 for ok in availability.values() if ok)
    total = len(availability)

    brewfather_available = availability[CONF_RUNTIME_RECIPE_NAME_ENTITY] or availability[CONF_RUNTIME_STATUS_ENTITY]
    if available_count == total:
        source_status = f"OK · {available_count}/{total} runtime sources available"
    elif brewfather_available:
        source_status = f"Partial · {available_count}/{total} runtime sources available"
    else:
        source_status = f"Unavailable · {available_count}/{total} runtime sources available"

    return {
        "recipe_name": recipe_name,
        "status": status,
        "primary_target_temperature": round(primary, 2) if primary is not None else None,
        "cold_crash_target_temperature": round(cold_crash, 2) if cold_crash is not None else None,
        "target_fg": round(target_fg, 3) if target_fg is not None else None,
        "source_status": source_status,
        "brewfather_available": brewfather_available,
        "available_count": available_count,
        "total_count": total,
        "availability": availability,
        "entities": {
            CONF_RUNTIME_RECIPE_NAME_ENTITY: recipe_entity,
            CONF_RUNTIME_STATUS_ENTITY: status_entity,
            CONF_RUNTIME_PRIMARY_TARGET_ENTITY: primary_entity,
            CONF_RUNTIME_COLD_CRASH_TARGET_ENTITY: crash_entity,
            CONF_RUNTIME_TARGET_FG_ENTITY: fg_entity,
        },
    }


def runtime_attrs(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Return runtime snapshot attributes."""
    attrs = {
        "source_status": snapshot["source_status"],
        "brewfather_available": snapshot["brewfather_available"],
        "available_count": snapshot["available_count"],
        "total_count": snapshot["total_count"],
    }
    for key, entity_id in snapshot["entities"].items():
        attrs[f"{key}_entity"] = entity_id
        attrs[f"{key}_available"] = snapshot["availability"].get(key)
    return attrs
