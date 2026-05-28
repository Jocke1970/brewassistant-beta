"""BrewAssistant select controls."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .carbonation_runtime import async_save_carbonation_runtime, get_carbonation_runtime, update_carbonation_runtime
from .const import DOMAIN
from .coordinator import BrewAssistantCoordinator
from .entity import BrewAssistantEntity
from .supervised_apply import READ_ONLY_MODE, SUPERVISED_MODE, cancel_pending_action

METHOD_OPTIONS = [
    "Set-and-forget",
    "Burst carbonation",
    "Natural carbonation",
    "Conditioning",
]

AIR_TARGET_TEST_OPTIONS = [
    "Off",
    "Fermentation",
    "Cold crash",
]

APPLY_MODE_OPTIONS = [
    READ_ONLY_MODE,
    SUPERVISED_MODE,
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BrewAssistant select controls."""
    coordinator: BrewAssistantCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            BrewAssistantCarbonationMethodSelect(coordinator),
            BrewAssistantAirTargetTestModeSelect(coordinator),
            BrewAssistantApplyModeSelect(coordinator),
        ]
    )


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
            await async_save_carbonation_runtime(self.coordinator.hass)

    @property
    def current_option(self) -> str | None:
        """Return current carbonation method."""
        return get_carbonation_runtime(self.coordinator.hass).method

    async def async_select_option(self, option: str) -> None:
        """Set carbonation method."""
        if option not in METHOD_OPTIONS:
            return
        update_carbonation_runtime(self.coordinator.hass, {"method": option})
        await async_save_carbonation_runtime(self.coordinator.hass)
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return diagnostic attributes."""
        return {"source": "python_runtime_control", "runtime_key": "method"}


class BrewAssistantAirTargetTestModeSelect(BrewAssistantEntity, RestoreEntity, SelectEntity):
    """Test mode selector for fermentation air target recommendations."""

    _attr_has_entity_name = False
    _attr_options = AIR_TARGET_TEST_OPTIONS
    _attr_icon = "mdi:beaker-question-outline"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: BrewAssistantCoordinator) -> None:
        super().__init__(coordinator, "fermentation_air_target_test_mode")
        self._attr_unique_id = f"{DOMAIN}_select_fermentation_air_target_test_mode"
        self._attr_name = "BrewAssistant Fermentation Air Target Test Mode"
        self._attr_suggested_object_id = f"{DOMAIN}_fermentation_air_target_test_mode"
        self._current_option = "Off"

    async def async_added_to_hass(self) -> None:
        """Keep the validation selector safe after reload/restart."""
        await super().async_added_to_hass()
        self._current_option = "Off"
        self.async_write_ha_state()

    @property
    def current_option(self) -> str | None:
        """Return selected option."""
        return self._current_option

    async def async_select_option(self, option: str) -> None:
        """Set selected option."""
        if option not in AIR_TARGET_TEST_OPTIONS:
            return
        self._current_option = option
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    @property
    def extra_state_attributes(self) -> dict[str, str | bool]:
        """Return diagnostic attributes."""
        return {
            "source": "python_runtime_control",
            "runtime_key": "fermentation_air_target_test_mode",
            "read_only": True,
            "resets_to_off_on_start": True,
        }


class BrewAssistantApplyModeSelect(BrewAssistantEntity, RestoreEntity, SelectEntity):
    """Global apply mode selector."""

    _attr_has_entity_name = False
    _attr_options = APPLY_MODE_OPTIONS
    _attr_icon = "mdi:shield-check-outline"

    def __init__(self, coordinator: BrewAssistantCoordinator) -> None:
        super().__init__(coordinator, "apply_mode")
        self._attr_unique_id = f"{DOMAIN}_select_apply_mode"
        self._attr_name = "BrewAssistant Apply Mode"
        self._attr_suggested_object_id = f"{DOMAIN}_apply_mode"
        self._current_option = READ_ONLY_MODE

    async def async_added_to_hass(self) -> None:
        """Restore apply mode."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state in APPLY_MODE_OPTIONS:
            self._current_option = last_state.state
        if self._current_option == READ_ONLY_MODE:
            cancel_pending_action(self.coordinator.hass)

    @property
    def current_option(self) -> str | None:
        """Return selected option."""
        return self._current_option

    async def async_select_option(self, option: str) -> None:
        """Set selected option."""
        if option not in APPLY_MODE_OPTIONS:
            return
        self._current_option = option
        if option == READ_ONLY_MODE:
            cancel_pending_action(self.coordinator.hass)
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    @property
    def extra_state_attributes(self) -> dict[str, str | bool]:
        """Return diagnostic attributes."""
        return {
            "source": "python_runtime_control",
            "runtime_key": "apply_mode",
            "read_only_default": True,
            "requires_confirmation": self._current_option == SUPERVISED_MODE,
        }
