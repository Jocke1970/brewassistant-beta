"""BrewZilla runtime sensor entities."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import PERCENTAGE, UnitOfPower, UnitOfTemperature

from .brewzilla_runtime import build_brewzilla_snapshot, brewzilla_attrs
from .const import DOMAIN
from .coordinator import BrewAssistantCoordinator
from .entity import BrewAssistantEntity


BREWZILLA_SENSORS: dict[str, dict[str, Any]] = {
    "brewzilla_runtime_summary": {"field": "summary"},
    "brewzilla_runtime_state": {"field": "hardware_state"},
    "brewzilla_connection_state": {"field": "connection_state"},
    "brewzilla_current_temperature": {
        "field": "current_temperature",
        "unit": UnitOfTemperature.CELSIUS,
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "brewzilla_target_temperature": {
        "field": "target_temperature",
        "unit": UnitOfTemperature.CELSIUS,
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "brewzilla_device_target_temperature": {
        "field": "device_target_temperature",
        "unit": UnitOfTemperature.CELSIUS,
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "brewzilla_runtime_target_temperature": {
        "field": "runtime_target_temperature",
        "unit": UnitOfTemperature.CELSIUS,
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "brewzilla_temperature_delta": {
        "field": "temperature_delta",
        "unit": UnitOfTemperature.CELSIUS,
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "brewzilla_power": {
        "field": "power_w",
        "unit": UnitOfPower.WATT,
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "brewzilla_heat_utilization": {
        "field": "heat_utilization",
        "unit": PERCENTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "brewzilla_pump_utilization": {
        "field": "pump_utilization",
        "unit": PERCENTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "brewzilla_runtime_stage": {"field": "runtime_stage"},
    "brewzilla_runtime_step": {"field": "runtime_step"},
}


def _display_name_from_key(key: str) -> str:
    """Return a stable human-readable name from an entity key."""
    return f"BrewAssistant {key.replace('_', ' ').title()}"


def create_brewzilla_sensors(
    coordinator: BrewAssistantCoordinator,
) -> list["BrewAssistantBrewZillaSensor"]:
    """Create BrewZilla runtime sensors."""
    return [BrewAssistantBrewZillaSensor(coordinator, key) for key in BREWZILLA_SENSORS]


class BrewAssistantBrewZillaSensor(BrewAssistantEntity, SensorEntity):
    """Read-only BrewZilla runtime sensor."""

    _attr_has_entity_name = False

    def __init__(self, coordinator: BrewAssistantCoordinator, key: str) -> None:
        """Initialize the BrewZilla runtime sensor."""
        super().__init__(coordinator, key)
        self._key = key
        self._field = str(BREWZILLA_SENSORS[key]["field"])
        self._attr_name = _display_name_from_key(key)
        self._attr_suggested_object_id = f"{DOMAIN}_{key}"
        self._attr_native_unit_of_measurement = BREWZILLA_SENSORS[key].get("unit")
        self._attr_device_class = BREWZILLA_SENSORS[key].get("device_class")
        self._attr_state_class = BREWZILLA_SENSORS[key].get("state_class")

    @property
    def native_value(self) -> Any:
        """Return BrewZilla runtime value."""
        return build_brewzilla_snapshot(self.coordinator.hass).get(self._field)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return BrewZilla runtime attributes."""
        return brewzilla_attrs(build_brewzilla_snapshot(self.coordinator.hass))
