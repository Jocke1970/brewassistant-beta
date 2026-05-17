"""Base entities for BrewAssistant."""

from __future__ import annotations

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME
from .coordinator import BrewAssistantCoordinator


class BrewAssistantEntity(CoordinatorEntity[BrewAssistantCoordinator]):
    """Base class for BrewAssistant entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: BrewAssistantCoordinator, key: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.config_entry.entry_id)},
            "name": NAME,
            "manufacturer": "BrewAssistant",
            "model": "Python Core",
        }
