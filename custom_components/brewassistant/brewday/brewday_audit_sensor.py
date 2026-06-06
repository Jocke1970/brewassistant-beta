"""Brewday Audit sensor entities."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass

from .brewday_audit import build_brewday_audit_snapshot
from ..const import DOMAIN
from ..coordinator import BrewAssistantCoordinator
from ..entity import BrewAssistantEntity


AUDIT_SENSORS: dict[str, dict[str, Any]] = {
    "brewday_audit_summary": {"field": "status"},
    "brewday_audit_event_count": {
        "field": "event_count",
        "unit": "events",
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "brewday_audit_last_event": {"field": "last_event_type"},
    "brewday_audit_last_step": {"field": "last_step"},
    "brewday_audit_last_target": {"field": "last_target"},
}


def _display_name_from_key(key: str) -> str:
    return f"BrewAssistant {key.replace('_', ' ').title()}"


def create_brewday_audit_sensors(coordinator: BrewAssistantCoordinator) -> list[SensorEntity]:
    """Create Brewday Audit sensors."""
    return [BrewAssistantBrewdayAuditSensor(coordinator, key) for key in AUDIT_SENSORS]


class BrewAssistantBrewdayAuditSensor(BrewAssistantEntity, SensorEntity):
    """Read-only Brewday Audit sensor."""

    _attr_has_entity_name = False

    def __init__(self, coordinator: BrewAssistantCoordinator, key: str) -> None:
        super().__init__(coordinator, key)
        self._key = key
        self._field = str(AUDIT_SENSORS[key]["field"])
        self._attr_name = _display_name_from_key(key)
        self._attr_suggested_object_id = f"{DOMAIN}_{key}"
        self._attr_native_unit_of_measurement = AUDIT_SENSORS[key].get("unit")
        self._attr_state_class = AUDIT_SENSORS[key].get("state_class")

    @property
    def native_value(self) -> Any:
        return build_brewday_audit_snapshot(self.coordinator.hass).get(self._field)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return build_brewday_audit_snapshot(self.coordinator.hass)
