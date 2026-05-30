"""BrewZilla learning sensor entities."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import PERCENTAGE, UnitOfTemperature

from .brewzilla_learning import build_brewzilla_learning_snapshot
from .const import DOMAIN
from .coordinator import BrewAssistantCoordinator
from .entity import BrewAssistantEntity


BREWZILLA_LEARNING_SENSORS: dict[str, dict[str, Any]] = {
    "brewzilla_learning_phase": {"field": "phase"},
    "brewzilla_learning_confidence": {"field": "confidence"},
    "brewzilla_stage_kind": {"field": "stage_kind"},
    "brewzilla_temp_rate": {
        "field": "temp_rate_c_per_min",
        "unit": "°C/min",
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "brewzilla_temp_rate_hourly": {
        "field": "temp_rate_c_per_hour",
        "unit": "°C/h",
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "brewzilla_delta_to_target": {
        "field": "delta_to_target",
        "unit": UnitOfTemperature.CELSIUS,
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "brewzilla_suggested_heat_utilization": {
        "field": "suggested_heat_utilization",
        "unit": PERCENTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "brewzilla_heat_adjustment": {
        "field": "heat_adjustment",
        "unit": PERCENTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "brewzilla_overshoot_risk": {"field": "overshoot_risk"},
    "brewzilla_heat_strategy_reason": {"field": "strategy_reason"},
}


def _display_name_from_key(key: str) -> str:
    return f"BrewAssistant {key.replace('_', ' ').title()}"


def create_brewzilla_learning_sensors(coordinator: BrewAssistantCoordinator) -> list[SensorEntity]:
    """Create BrewZilla learning sensors."""
    return [BrewAssistantBrewZillaLearningSensor(coordinator, key) for key in BREWZILLA_LEARNING_SENSORS]


class BrewAssistantBrewZillaLearningSensor(BrewAssistantEntity, SensorEntity):
    """Read-only BrewZilla learning/suggestion sensor."""

    _attr_has_entity_name = False

    def __init__(self, coordinator: BrewAssistantCoordinator, key: str) -> None:
        super().__init__(coordinator, key)
        self._key = key
        self._field = str(BREWZILLA_LEARNING_SENSORS[key]["field"])
        self._attr_name = _display_name_from_key(key)
        self._attr_suggested_object_id = f"{DOMAIN}_{key}"
        self._attr_native_unit_of_measurement = BREWZILLA_LEARNING_SENSORS[key].get("unit")
        self._attr_device_class = BREWZILLA_LEARNING_SENSORS[key].get("device_class")
        self._attr_state_class = BREWZILLA_LEARNING_SENSORS[key].get("state_class")

    @property
    def native_value(self) -> Any:
        return build_brewzilla_learning_snapshot(self.coordinator.hass).get(self._field)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return build_brewzilla_learning_snapshot(self.coordinator.hass)
