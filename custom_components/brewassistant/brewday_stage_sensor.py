"""Brewday Stage Engine sensor entities."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.const import PERCENTAGE, UnitOfPower, UnitOfTemperature

from .brewday_stage_engine import build_brewday_stage_snapshot, brewday_stage_attrs
from .const import DOMAIN
from .coordinator import BrewAssistantCoordinator
from .entity import BrewAssistantEntity


BREWDAY_STAGE_SENSORS: dict[str, dict[str, Any]] = {
    "brewday_stage": {"field": "stage"},
    "brewday_stage_reason": {"field": "stage_reason"},
    "brewday_stage_status_line": {"field": "status_line"},
    "brewday_stage_icon": {"field": "stage_icon"},
    "brewday_stage_remaining_minutes": {
        "field": "remaining_minutes",
        "unit": "min",
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "brewday_stage_progress": {
        "field": "progress_percent",
        "unit": PERCENTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "brewday_stage_temperature": {
        "field": "brewzilla_temperature",
        "unit": UnitOfTemperature.CELSIUS,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "brewday_stage_target_temperature": {
        "field": "brewzilla_target",
        "unit": UnitOfTemperature.CELSIUS,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "brewday_stage_power": {
        "field": "brewzilla_power",
        "unit": UnitOfPower.WATT,
        "state_class": SensorStateClass.MEASUREMENT,
    },
}


def create_brewday_stage_sensors(
    coordinator: BrewAssistantCoordinator,
) -> list["BrewAssistantBrewdayStageSensor"]:
    """Create Brewday Stage Engine sensors."""
    return [BrewAssistantBrewdayStageSensor(coordinator, key) for key in BREWDAY_STAGE_SENSORS]


class BrewAssistantBrewdayStageSensor(BrewAssistantEntity, SensorEntity):
    """Read-only Brewday Stage Engine sensor."""

    _attr_has_entity_name = False

    def __init__(self, coordinator: BrewAssistantCoordinator, key: str) -> None:
        super().__init__(coordinator, key)
        self._key = key
        self._field = str(BREWDAY_STAGE_SENSORS[key]["field"])
        self._attr_name = f"BrewAssistant {key.replace('_', ' ').title()}"
        self._attr_suggested_object_id = f"{DOMAIN}_{key}"
        self._attr_native_unit_of_measurement = BREWDAY_STAGE_SENSORS[key].get("unit")
        self._attr_state_class = BREWDAY_STAGE_SENSORS[key].get("state_class")

    @property
    def native_value(self) -> Any:
        return build_brewday_stage_snapshot(self.coordinator.hass).get(self._field)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return brewday_stage_attrs(build_brewday_stage_snapshot(self.coordinator.hass))
