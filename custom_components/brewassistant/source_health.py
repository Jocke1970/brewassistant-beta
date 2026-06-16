"""Source health helpers for BrewAssistant."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .const import (
    CONF_CHAMBER_TEMP_ENTITY,
    CONF_COLD_CRASH_ACTIVE_ENTITY,
    CONF_COLD_CRASH_TARGET_ENTITY,
    CONF_GRAVITY_ENTITY,
    CONF_LIQUID_TEMP_ENTITY,
    CONF_RECIPE_TARGET_ENTITY,
)

BAD_STATES = {"unknown", "unavailable", "none", ""}
NUMERIC_KEYS = {
    CONF_LIQUID_TEMP_ENTITY,
    CONF_CHAMBER_TEMP_ENTITY,
    CONF_RECIPE_TARGET_ENTITY,
    CONF_COLD_CRASH_TARGET_ENTITY,
    CONF_GRAVITY_ENTITY,
}

SOURCE_LABELS = {
    CONF_LIQUID_TEMP_ENTITY: "Liquid temperature",
    CONF_CHAMBER_TEMP_ENTITY: "Chamber temperature fallback",
    CONF_RECIPE_TARGET_ENTITY: "Recipe target temperature",
    CONF_COLD_CRASH_ACTIVE_ENTITY: "Cold crash active helper",
    CONF_COLD_CRASH_TARGET_ENTITY: "Cold crash target temperature",
    CONF_GRAVITY_ENTITY: "Gravity source",
}

SOURCE_SENSOR_KEYS = {
    "configured_liquid_temp_entity": CONF_LIQUID_TEMP_ENTITY,
    "configured_chamber_temp_entity": CONF_CHAMBER_TEMP_ENTITY,
    "configured_recipe_target_entity": CONF_RECIPE_TARGET_ENTITY,
    "configured_cold_crash_active_entity": CONF_COLD_CRASH_ACTIVE_ENTITY,
    "configured_cold_crash_target_entity": CONF_COLD_CRASH_TARGET_ENTITY,
    "configured_gravity_entity": CONF_GRAVITY_ENTITY,
}

SOURCE_BINARY_KEYS = {
    "source_liquid_temp_available": CONF_LIQUID_TEMP_ENTITY,
    "source_chamber_temp_available": CONF_CHAMBER_TEMP_ENTITY,
    "source_recipe_target_available": CONF_RECIPE_TARGET_ENTITY,
    "source_cold_crash_active_available": CONF_COLD_CRASH_ACTIVE_ENTITY,
    "source_cold_crash_target_available": CONF_COLD_CRASH_TARGET_ENTITY,
    "source_gravity_available": CONF_GRAVITY_ENTITY,
}


def diagnose_source(hass: HomeAssistant, key: str, entity_id: str) -> dict[str, Any]:
    """Return diagnostic information for one source entity."""
    state_obj = hass.states.get(entity_id)
    numeric_required = key in NUMERIC_KEYS
    label = SOURCE_LABELS.get(key, key)

    if state_obj is None:
        return {
            "key": key,
            "label": label,
            "entity_id": entity_id,
            "available": False,
            "state": None,
            "reason": "entity missing",
        }

    state = str(state_obj.state)
    if state.lower() in BAD_STATES:
        return {
            "key": key,
            "label": label,
            "entity_id": entity_id,
            "available": False,
            "state": state,
            "reason": f"state is {state}",
        }

    if numeric_required:
        try:
            float(state)
        except (TypeError, ValueError):
            return {
                "key": key,
                "label": label,
                "entity_id": entity_id,
                "available": False,
                "state": state,
                "reason": "state is not numeric",
            }

    return {
        "key": key,
        "label": label,
        "entity_id": entity_id,
        "available": True,
        "state": state,
        "reason": "OK",
    }


def build_source_health(hass: HomeAssistant, configured_entities: dict[str, Any]) -> dict[str, Any]:
    """Return aggregate source diagnostics."""
    sources = {
        key: diagnose_source(hass, key, str(entity_id))
        for key, entity_id in configured_entities.items()
    }
    total = len(sources)
    available = sum(1 for item in sources.values() if item["available"])
    bad = [item for item in sources.values() if not item["available"]]

    if not bad:
        level = "ok"
        summary = f"OK · {available}/{total} sources available"
    else:
        critical = False
        liquid_ok = sources.get(CONF_LIQUID_TEMP_ENTITY, {}).get("available", False)
        chamber_ok = sources.get(CONF_CHAMBER_TEMP_ENTITY, {}).get("available", False)
        target_ok = sources.get(CONF_RECIPE_TARGET_ENTITY, {}).get("available", False)
        crash_ok = sources.get(CONF_COLD_CRASH_TARGET_ENTITY, {}).get("available", False)
        if (not liquid_ok and not chamber_ok) or not target_ok or not crash_ok:
            critical = True
        first = bad[0]
        level = "problem" if critical else "warning"
        summary = f"{level.title()} · {available}/{total} sources available · {first['label']}: {first['reason']}"

    return {"level": level, "summary": summary, "sources": sources}


def source_health_attrs(health: dict[str, Any]) -> dict[str, Any]:
    """Flatten source diagnostics into HA attributes."""
    attrs = {
        "level": health["level"],
        "summary": health["summary"],
        "sources_total": len(health["sources"]),
        "sources_available": sum(1 for item in health["sources"].values() if item["available"]),
    }
    for key, item in health["sources"].items():
        attrs[f"{key}_entity"] = item["entity_id"]
        attrs[f"{key}_available"] = item["available"]
        attrs[f"{key}_state"] = item["state"]
        attrs[f"{key}_reason"] = item["reason"]
    return attrs
