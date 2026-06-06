"""Brewday addition alert sensor entities."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass

from .brewday_addition_alerts import build_addition_alert_snapshot
from ..const import DOMAIN
from ..coordinator import BrewAssistantCoordinator
from ..entity import BrewAssistantEntity


ADDITION_ALERT_SENSORS: dict[str, dict[str, Any]] = {
    "brewday_addition_alert_state": {"field": "state"},
    "brewday_addition_alert_message": {"field": "message"},
    "brewday_addition_due": {"field": "due"},
    "brewday_addition_due_now": {"field": "due_now"},
    "brewday_addition_due_soon": {"field": "due_soon"},
    "brewday_next_addition_name": {"field": "next_addition_name"},
    "brewday_next_addition_in_minutes": {
        "field": "next_addition_in_minutes",
        "unit": "min",
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "brewday_next_addition_in_seconds": {
        "field": "next_addition_in_seconds",
        "unit": "s",
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "brewday_addition_candidate_count": {
        "field": "candidate_count",
        "state_class": SensorStateClass.MEASUREMENT,
    },
}


def _display_name_from_key(key: str) -> str:
    return f"BrewAssistant {key.replace('_', ' ').title()}"


def create_brewday_addition_alert_sensors(coordinator: BrewAssistantCoordinator) -> list[SensorEntity]:
    """Create brewday addition alert sensors."""
    return [BrewAssistantBrewdayAdditionAlertSensor(coordinator, key) for key in ADDITION_ALERT_SENSORS]


class BrewAssistantBrewdayAdditionAlertSensor(BrewAssistantEntity, SensorEntity):
    """Read-only brewday addition alert sensor."""

    _attr_has_entity_name = False

    def __init__(self, coordinator: BrewAssistantCoordinator, key: str) -> None:
        super().__init__(coordinator, key)
        self._key = key
        self._field = str(ADDITION_ALERT_SENSORS[key]["field"])
        self._attr_name = _display_name_from_key(key)
        self._attr_suggested_object_id = f"{DOMAIN}_{key}"
        self._attr_native_unit_of_measurement = ADDITION_ALERT_SENSORS[key].get("unit")
        self._attr_state_class = ADDITION_ALERT_SENSORS[key].get("state_class")

    @property
    def native_value(self) -> Any:
        return build_addition_alert_snapshot(self.coordinator.hass).get(self._field)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return build_addition_alert_snapshot(self.coordinator.hass)
