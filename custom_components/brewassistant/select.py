"""BrewAssistant select controls."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .carbonation_runtime import get_carbonation_runtime, update_carbonation_runtime
from .const import DOMAIN
from .coordinator import BrewAssistantCoordinator
from .entity import BrewAssistantEntity

METHOD_OPTIONS = [
    "Set-and-forget",
    "Burst carbonation",
    "Natural carbonation",
    "Conditioning",
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BrewAssistant select controls."""
    coordinator: BrewAssistantCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([BrewAssistantCarbonationMethodSelect(coordinator)])


class BrewAssistantCarbonationMethodSelect(BrewAssistantEntity, RestoreEntity, SelectEntity):
    """Python-owned carbonation method select."""

    _attr_has_entity_name = False
    _attr_options = METHOD_OPTIONS
    _attr_icon = "mdi:format-list-bulleted-type"

    def __init__(self, coordinator: BrewAssistantCoordinator) -> None:
        super().__init__(coordinator, "carbonation_method_control")
        self._attr_unique_id = f"{DOMAIN}_select_carbonation_method_control"
        self._attr_name = "BrewAssistant Carbonation Method"
        self._attr_suggested_object_id = f"{DOMAIN}_carbonation_method_control"

    async def async_added_to_hass(self) -> None:
        """Restore the selected method into the runtime."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state in METHOD_OPTIONS:
            update_carbonation_runtime(self.coordinator.hass, {"method": last_state.state})

    @property
    def current_option(self) -> str | None:
        """Return current carbonation method."""
        return get_carbonation_runtime(self.coordinator.hass).method

    async def async_select_option(self, option: str) -> None:
        """Set carbonation method."""
        if option not in METHOD_OPTIONS:
            return
        update_carbonation_runtime(self.coordinator.hass, {"method": option})
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return diagnostic attributes."""
        return {"source": "python_runtime_control", "runtime_key": "method"}
