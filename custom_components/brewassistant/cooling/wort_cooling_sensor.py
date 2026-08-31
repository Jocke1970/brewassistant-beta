"""Cooling Runtime v2 sensor entities.

Keeps the legacy wort-cooling sensor IDs while adding generic Cooling v2
entities so dashboards can migrate without a flag day.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import UnitOfTemperature

from ..const import DOMAIN
from ..coordinator import BrewAssistantCoordinator
from ..entity import BrewAssistantEntity
from .cooling_advice import build_cooling_snapshot, cooling_attrs


WORT_COOLING_SENSORS: dict[str, dict[str, Any]] = {
    # Cooling v2 canonical entities.
    "cooling_state": {"field": "state"},
    "cooling_method": {"field": "method"},
    "cooling_status": {"field": "status"},
    "cooling_advice": {"field": "advice"},
    "cooling_summary": {"field": "summary"},
    "cooling_process_temperature": {
        "field": "process_temperature",
        "unit": UnitOfTemperature.CELSIUS,
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "cooling_target_temperature": {
        "field": "target_temperature",
        "unit": UnitOfTemperature.CELSIUS,
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "cooling_delta": {
        "field": "delta",
        "unit": UnitOfTemperature.CELSIUS,
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "cooling_rate": {
        "field": "cooling_rate_c_per_h",
        "unit": "°C/h",
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "cooling_eta_minutes": {
        "field": "eta_minutes",
        "unit": "min",
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "cooling_target_ready": {"field": "target_ready"},
    "cooling_process_temperature_source": {"field": "process_temperature_source"},

    # Compatibility aliases for existing dashboards/automations.
    "wort_cooling_status": {"field": "status"},
    "wort_cooling_summary": {"field": "summary"},
    "wort_cooling_reference_temperature": {
        "field": "process_temperature",
        "unit": UnitOfTemperature.CELSIUS,
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "wort_cooling_target_temperature": {
        "field": "target_temperature",
        "unit": UnitOfTemperature.CELSIUS,
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "wort_cooling_delta": {
        "field": "delta",
        "unit": UnitOfTemperature.CELSIUS,
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "wort_cooling_rate": {
        "field": "cooling_rate_c_per_h",
        "unit": "°C/h",
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "wort_cooling_eta_minutes": {
        "field": "eta_minutes",
        "unit": "min",
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "wort_pitch_ready": {"field": "pitch_ready"},
}


def create_wort_cooling_sensors(
    coordinator: BrewAssistantCoordinator,
) -> list["BrewAssistantWortCoolingSensor"]:
    """Create Cooling v2 plus compatibility sensors."""
    return [BrewAssistantWortCoolingSensor(coordinator, key) for key in WORT_COOLING_SENSORS]


class BrewAssistantWortCoolingSensor(BrewAssistantEntity, SensorEntity):
    """Read-only Cooling Runtime sensor."""

    _attr_has_entity_name = False

    def __init__(self, coordinator: BrewAssistantCoordinator, key: str) -> None:
        super().__init__(coordinator, key)
        self._key = key
        self._field = str(WORT_COOLING_SENSORS[key]["field"])
        self._attr_name = f"BrewAssistant {key.replace('_', ' ').title()}"
        self._attr_suggested_object_id = f"{DOMAIN}_{key}"
        self._attr_native_unit_of_measurement = WORT_COOLING_SENSORS[key].get("unit")
        self._attr_device_class = WORT_COOLING_SENSORS[key].get("device_class")
        self._attr_state_class = WORT_COOLING_SENSORS[key].get("state_class")

    @property
    def native_value(self) -> Any:
        return build_cooling_snapshot(self.coordinator.hass).get(self._field)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return cooling_attrs(build_cooling_snapshot(self.coordinator.hass))
