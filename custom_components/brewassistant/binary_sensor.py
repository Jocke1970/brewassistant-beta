"""Binary sensor platform for BrewAssistant."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity, BinarySensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import BrewAssistantCoordinator, BrewAssistantData
from .entity import BrewAssistantEntity


@dataclass(frozen=True, kw_only=True)
class BrewAssistantBinarySensorDescription(BinarySensorEntityDescription):
    """Describes a BrewAssistant binary sensor."""

    value_fn: Callable[[BrewAssistantData], bool]


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
)


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

    @property
    def is_on(self) -> bool | None:
        """Return whether the binary sensor is on."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)
