"""Wort cooling sensor entities."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import UnitOfTemperature

from .const import DOMAIN
from .coordinator import BrewAssistantCoordinator
from .entity import BrewAssistantEntity
from .wort_cooling import build_wort_cooling_snapshot, wort_cooling_attrs


WORT_COOLING_SENSORS: dict[str, dict[str, Any]] = {
    "wort_cooling_status": {"field": "status"},
    "wort_cooling_summary": {"field": "summary"},
    "wort_cooling_reference_temperature": {
        "field": "reference_temperature",
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
    """Create wort cooling sensors."""
    return [BrewAssistantWortCoolingSensor(coordinator, key) for key in WORT_COOLING_SENSORS]


class BrewAssistantWortCoolingSensor(BrewAssistantEntity, SensorEntity):
    """Read-only wort cooling sensor."""

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
        return build_wort_cooling_snapshot(self.coordinator.hass).get(self._field)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return wort_cooling_attrs(build_wort_cooling_snapshot(self.coordinator.hass))
