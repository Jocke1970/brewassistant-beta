"""Sensor platform for BrewAssistant."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_SOURCE, ATTR_SOURCE_ENTITY, ATTR_TARGET_ENTITY, ATTR_TARGET_MODE, DOMAIN
from .coordinator import BrewAssistantCoordinator, BrewAssistantData
from .entity import BrewAssistantEntity


@dataclass(frozen=True, kw_only=True)
class BrewAssistantSensorDescription(SensorEntityDescription):
    """Describes a BrewAssistant sensor."""

    value_fn: Callable[[BrewAssistantData], Any]
    extra_attributes_fn: Callable[[BrewAssistantCoordinator], dict[str, Any]] | None = None


def _liquid_attrs(coordinator: BrewAssistantCoordinator) -> dict[str, Any]:
    data = coordinator.data
    return {
        ATTR_SOURCE: data.liquid_temperature_source if data else None,
        ATTR_SOURCE_ENTITY: data.liquid_temperature_entity if data else None,
    }


def _target_attrs(coordinator: BrewAssistantCoordinator) -> dict[str, Any]:
    data = coordinator.data
    return {
        ATTR_TARGET_ENTITY: data.recipe_target_temperature_entity if data else None,
        ATTR_TARGET_MODE: data.temperature_target_mode if data else None,
    }


def _source_attrs(coordinator: BrewAssistantCoordinator) -> dict[str, Any]:
    data = coordinator.data
    return {ATTR_SOURCE_ENTITY: data.liquid_temperature_entity if data else None}


SENSORS: tuple[BrewAssistantSensorDescription, ...] = (
    BrewAssistantSensorDescription(
        key="liquid_temperature",
        translation_key="liquid_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.liquid_temperature,
        extra_attributes_fn=_liquid_attrs,
    ),
    BrewAssistantSensorDescription(
        key="liquid_temperature_source",
        translation_key="liquid_temperature_source",
        value_fn=lambda data: data.liquid_temperature_source,
        extra_attributes_fn=_source_attrs,
    ),
    BrewAssistantSensorDescription(
        key="chamber_temperature",
        translation_key="chamber_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.chamber_temperature,
    ),
    BrewAssistantSensorDescription(
        key="recipe_target_temperature",
        translation_key="recipe_target_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.recipe_target_temperature,
        extra_attributes_fn=_target_attrs,
    ),
    BrewAssistantSensorDescription(
        key="temperature_delta",
        translation_key="temperature_delta",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.temperature_delta,
    ),
    BrewAssistantSensorDescription(
        key="gravity",
        translation_key="gravity",
        native_unit_of_measurement="SG",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.gravity,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BrewAssistant sensors."""
    coordinator: BrewAssistantCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        BrewAssistantSensor(coordinator, description) for description in SENSORS
    )


class BrewAssistantSensor(BrewAssistantEntity, SensorEntity):
    """BrewAssistant sensor entity."""

    entity_description: BrewAssistantSensorDescription

    def __init__(
        self,
        coordinator: BrewAssistantCoordinator,
        description: BrewAssistantSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        """Return the native sensor value."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional sensor attributes."""
        if self.entity_description.extra_attributes_fn is None:
            return None
        return self.entity_description.extra_attributes_fn(self.coordinator)
