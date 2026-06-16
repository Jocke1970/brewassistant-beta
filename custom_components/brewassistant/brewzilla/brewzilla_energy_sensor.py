"""BrewZilla energy sensor entities."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import UnitOfEnergy, UnitOfPower

from .brewzilla_energy import build_brewzilla_energy_snapshot
from ..const import DOMAIN
from ..coordinator import BrewAssistantCoordinator
from ..entity import BrewAssistantEntity


BREWZILLA_ENERGY_SENSORS: dict[str, dict[str, Any]] = {
    "brewzilla_energy_session": {
        "field": "energy_kwh",
        "unit": UnitOfEnergy.KILO_WATT_HOUR,
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
    },
    "brewzilla_energy_session_wh": {
        "field": "energy_wh",
        "unit": UnitOfEnergy.WATT_HOUR,
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
    },
    "brewzilla_energy_power": {
        "field": "power_w",
        "unit": UnitOfPower.WATT,
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "brewzilla_energy_cost_session": {
        "field": "cost_sek",
        "unit": "SEK",
        "state_class": SensorStateClass.TOTAL_INCREASING,
    },
    "brewzilla_energy_current_price_cost_estimate": {
        "field": "current_price_cost_estimate_sek",
        "unit": "SEK",
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "brewzilla_energy_price": {
        "field": "price_sek_per_kwh",
        "unit": "SEK/kWh",
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "brewzilla_energy_tracking_active": {"field": "tracking_active"},
}


def _display_name_from_key(key: str) -> str:
    return f"BrewAssistant {key.replace('_', ' ').title()}"


def create_brewzilla_energy_sensors(coordinator: BrewAssistantCoordinator) -> list[SensorEntity]:
    """Create BrewZilla energy sensors."""
    return [BrewAssistantBrewZillaEnergySensor(coordinator, key) for key in BREWZILLA_ENERGY_SENSORS]


class BrewAssistantBrewZillaEnergySensor(BrewAssistantEntity, SensorEntity):
    """Read-only BrewZilla energy sensor."""

    _attr_has_entity_name = False

    def __init__(self, coordinator: BrewAssistantCoordinator, key: str) -> None:
        super().__init__(coordinator, key)
        self._key = key
        self._field = str(BREWZILLA_ENERGY_SENSORS[key]["field"])
        self._attr_name = _display_name_from_key(key)
        self._attr_suggested_object_id = f"{DOMAIN}_{key}"
        self._attr_native_unit_of_measurement = BREWZILLA_ENERGY_SENSORS[key].get("unit")
        self._attr_device_class = BREWZILLA_ENERGY_SENSORS[key].get("device_class")
        self._attr_state_class = BREWZILLA_ENERGY_SENSORS[key].get("state_class")

    @property
    def native_value(self) -> Any:
        return build_brewzilla_energy_snapshot(self.coordinator.hass).get(self._field)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return build_brewzilla_energy_snapshot(self.coordinator.hass)
