"""Binary sensor platform for BrewAssistant."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import BrewAssistantCoordinator, BrewAssistantData
from .entity import BrewAssistantEntity
from .smart_recommendations import build_smart_recommendations


@dataclass(frozen=True, kw_only=True)
class BrewAssistantBinarySensorDescription(BinarySensorEntityDescription):
    """Describes a BrewAssistant binary sensor."""

    value_fn: Callable[[BrewAssistantData], bool]


def _display_name_from_key(key: str) -> str:
    """Return a stable human-readable name from an entity key."""
    return f"BrewAssistant {key.replace('_', ' ').title()}"


def _smart_data(coordinator: BrewAssistantCoordinator):
    data = coordinator.data
    if data is None:
        return None
    return build_smart_recommendations(
        coordinator.hass,
        liquid_temp=data.liquid_temperature,
        target_temp=data.recipe_target_temperature,
        delta=data.temperature_delta,
        chamber_temp=data.chamber_temperature,
        fallback_active=data.fallback_active,
        source=data.liquid_temperature_source,
    )


BINARY_SENSORS: tuple[BrewAssistantBinarySensorDescription, ...] = (
    BrewAssistantBinarySensorDescription(
        key="temperature_fallback_active",
        translation_key="temperature_fallback_active",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda data: data.fallback_active,
    ),
    BrewAssistantBinarySensorDescription(
        key="runtime_ready",
        translation_key="runtime_ready",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda data: data.ready,
    ),
    BrewAssistantBinarySensorDescription(
        key="smart_heat_needed_core",
        translation_key="smart_heat_needed_core",
        value_fn=lambda data: False,
    ),
    BrewAssistantBinarySensorDescription(
        key="smart_heat_permitted_core",
        translation_key="smart_heat_permitted_core",
        value_fn=lambda data: False,
    ),
    BrewAssistantBinarySensorDescription(
        key="smart_cooling_recommended_core",
        translation_key="smart_cooling_recommended_core",
        value_fn=lambda data: False,
    ),
    BrewAssistantBinarySensorDescription(
        key="smart_fan_recommended_core",
        translation_key="smart_fan_recommended_core",
        value_fn=lambda data: False,
    ),
    BrewAssistantBinarySensorDescription(
        key="smart_rising_too_fast_core",
        translation_key="smart_rising_too_fast_core",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda data: False,
    ),
    BrewAssistantBinarySensorDescription(
        key="smart_pill_stale_core",
        translation_key="smart_pill_stale_core",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda data: False,
    ),
)


SMART_BINARY_KEYS = {
    "smart_heat_needed_core",
    "smart_heat_permitted_core",
    "smart_cooling_recommended_core",
    "smart_fan_recommended_core",
    "smart_rising_too_fast_core",
    "smart_pill_stale_core",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BrewAssistant binary sensors."""
    coordinator: BrewAssistantCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        BrewAssistantBinarySensor(coordinator, description)
        for description in BINARY_SENSORS
    )


class BrewAssistantBinarySensor(BrewAssistantEntity, BinarySensorEntity):
    """BrewAssistant binary sensor entity."""

    entity_description: BrewAssistantBinarySensorDescription

    def __init__(
        self,
        coordinator: BrewAssistantCoordinator,
        description: BrewAssistantBinarySensorDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description
        if description.key in SMART_BINARY_KEYS:
            self._attr_has_entity_name = False
            self._attr_name = _display_name_from_key(description.key)
            self._attr_suggested_object_id = f"{DOMAIN}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return whether the binary sensor is on."""
        if self.coordinator.data is None:
            return None
        if self.entity_description.key in SMART_BINARY_KEYS:
            smart = _smart_data(self.coordinator)
            if smart is None:
                return None
            if self.entity_description.key == "smart_heat_needed_core":
                return smart.heat_needed
            if self.entity_description.key == "smart_heat_permitted_core":
                return smart.heat_permitted
            if self.entity_description.key == "smart_cooling_recommended_core":
                return smart.cooling_recommended
            if self.entity_description.key == "smart_fan_recommended_core":
                return smart.fan_recommended
            if self.entity_description.key == "smart_rising_too_fast_core":
                return smart.rising_too_fast
            if self.entity_description.key == "smart_pill_stale_core":
                return smart.pill_stale
        return self.entity_description.value_fn(self.coordinator.data)
