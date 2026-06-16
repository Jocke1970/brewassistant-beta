"""BrewAssistant select controls."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .carbonation_backend.carbonation_runtime import async_save_carbonation_runtime, get_carbonation_runtime, update_carbonation_runtime
from .const import DOMAIN
from .brewzilla.brewzilla_temperature import MASH_SOURCE_OPTIONS
from .control_policy import POLICY_OPTIONS, SECTION_CONFIG, section_policy
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

BREWZILLA_LEARNING_CONTEXT_OPTIONS = [
    "Unknown",
    "Water only",
    "Real mash",
]

KEGERATOR_FAN_MODE_OPTIONS = [
    "Off",
    "Cooling only",
    "Afterrun",
    "Always on",
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
            BrewAssistantBrewZillaLearningContextSelect(coordinator),
            BrewAssistantBrewZillaMashTemperatureSourceSelect(coordinator),
            BrewAssistantKegeratorFanModeSelect(coordinator),
        ]
        + [
            BrewAssistantSectionPolicySelect(coordinator, section, config)
            for section, config in SECTION_CONFIG.items()
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
        self._attr_suggested_object_id = f"{DOMAIN}_carbonation_method"

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


class BrewAssistantBrewZillaLearningContextSelect(BrewAssistantEntity, RestoreEntity, SelectEntity):
    """Context selector for BrewZilla learning observations."""

    _attr_has_entity_name = False
    _attr_options = BREWZILLA_LEARNING_CONTEXT_OPTIONS
    _attr_icon = "mdi:beaker-question-outline"

    def __init__(self, coordinator: BrewAssistantCoordinator) -> None:
        super().__init__(coordinator, "brewzilla_learning_context")
        self._attr_unique_id = f"{DOMAIN}_select_brewzilla_learning_context"
        self._attr_name = "BrewAssistant BrewZilla Learning Context"
        self._attr_suggested_object_id = f"{DOMAIN}_brewzilla_learning_context"
        self._current_option = "Unknown"

    async def async_added_to_hass(self) -> None:
        """Restore learning context after restart."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state in BREWZILLA_LEARNING_CONTEXT_OPTIONS:
            self._current_option = last_state.state
        self.async_write_ha_state()

    @property
    def current_option(self) -> str | None:
        """Return selected option."""
        return self._current_option

    async def async_select_option(self, option: str) -> None:
        """Set learning context."""
        if option not in BREWZILLA_LEARNING_CONTEXT_OPTIONS:
            return
        self._current_option = option
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    @property
    def extra_state_attributes(self) -> dict[str, str | bool]:
        """Return diagnostic attributes."""
        return {
            "source": "brewzilla_learning",
            "runtime_key": "learning_context",
            "advisory_only": True,
            "water_only_profile_weight": "0.25",
            "real_mash_profile_weight": "1.0",
        }


class BrewAssistantBrewZillaMashTemperatureSourceSelect(BrewAssistantEntity, RestoreEntity, SelectEntity):
    """Mash temperature source selector for BrewZilla."""

    _attr_has_entity_name = False
    _attr_options = MASH_SOURCE_OPTIONS
    _attr_icon = "mdi:thermometer-lines"

    def __init__(self, coordinator: BrewAssistantCoordinator) -> None:
        super().__init__(coordinator, "brewzilla_mash_temperature_source_select")
        self._attr_unique_id = f"{DOMAIN}_select_brewzilla_mash_temperature_source"
        self._attr_name = "BrewAssistant BrewZilla Mash Temperature Source"
        self._attr_suggested_object_id = f"{DOMAIN}_brewzilla_mash_temperature_source"
        self._current_option = "Auto"

    async def async_added_to_hass(self) -> None:
        """Restore mash temperature source after restart."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state in MASH_SOURCE_OPTIONS:
            self._current_option = last_state.state
        self.async_write_ha_state()

    @property
    def current_option(self) -> str | None:
        """Return selected option."""
        return self._current_option

    async def async_select_option(self, option: str) -> None:
        """Set mash temperature source."""
        if option not in MASH_SOURCE_OPTIONS:
            return
        self._current_option = option
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    @property
    def extra_state_attributes(self) -> dict[str, str | bool]:
        """Return diagnostic attributes."""
        return {
            "source": "brewzilla_temperature_resolver",
            "runtime_key": "mash_temperature_source",
            "default": "Auto",
            "auto_priority": "BLE > Control Device > Internal",
            "wort_temperature_source": "BrewZilla Internal",
        }


class BrewAssistantKegeratorFanModeSelect(BrewAssistantEntity, RestoreEntity, SelectEntity):
    """Simple kegerator fan mode selector."""

    _attr_has_entity_name = False
    _attr_options = KEGERATOR_FAN_MODE_OPTIONS
    _attr_icon = "mdi:fan-auto"

    def __init__(self, coordinator: BrewAssistantCoordinator) -> None:
        super().__init__(coordinator, "kegerator_fan_mode")
        self._attr_unique_id = f"{DOMAIN}_select_kegerator_fan_mode"
        self._attr_name = "BrewAssistant Kegerator Fan Mode"
        self._attr_suggested_object_id = f"{DOMAIN}_kegerator_fan_mode"
        self._current_option = "Afterrun"

    async def async_added_to_hass(self) -> None:
        """Restore fan mode after restart."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state in KEGERATOR_FAN_MODE_OPTIONS:
            self._current_option = last_state.state
        self.async_write_ha_state()

    @property
    def current_option(self) -> str | None:
        """Return selected fan mode."""
        return self._current_option

    async def async_select_option(self, option: str) -> None:
        """Set fan mode."""
        if option not in KEGERATOR_FAN_MODE_OPTIONS:
            return
        self._current_option = option
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    @property
    def extra_state_attributes(self) -> dict[str, str | bool]:
        """Return fan mode diagnostics."""
        return {
            "source": "kegerator_fan_simple_control",
            "default": "Afterrun",
            "off": "Fan is kept off while fan-auto is enabled",
            "cooling_only": "Fan follows compressor activity",
            "afterrun": "Fan follows compressor activity and stays on after stop",
            "always_on": "Fan stays on while fan-auto is enabled",
        }


class BrewAssistantSectionPolicySelect(BrewAssistantEntity, RestoreEntity, SelectEntity):
    """Section-scoped BrewZilla policy selector."""

    _attr_has_entity_name = False
    _attr_options = POLICY_OPTIONS

    def __init__(self, coordinator: BrewAssistantCoordinator, section: str, config: dict) -> None:
        key = f"{section}_policy"
        super().__init__(coordinator, key)
        self._section = section
        self._config = config
        self._attr_unique_id = f"{DOMAIN}_select_{section}_policy"
        self._attr_name = f"BrewAssistant {config['name']} Policy"
        self._attr_suggested_object_id = str(config["policy_entity"]).removeprefix("select.")
        self._attr_icon = self._icon_for_section(section)
        self._current_option = str(config.get("default_policy", POLICY_OPTIONS[0]))

    @staticmethod
    def _icon_for_section(section: str) -> str:
        return {
            "target": "mdi:target",
            "heater": "mdi:fire",
            "pump": "mdi:pump",
            "boil": "mdi:kettle-steam",
            "stage": "mdi:debug-step-over",
            "cleaning": "mdi:spray-bottle",
            "brew_tracker_feed": "mdi:cloud-sync-outline",
        }.get(section, "mdi:tune-variant")

    async def async_added_to_hass(self) -> None:
        """Restore section policy after restart."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state in POLICY_OPTIONS:
            self._current_option = last_state.state
        self.async_write_ha_state()

    @property
    def current_option(self) -> str | None:
        """Return selected section policy."""
        return self._current_option

    async def async_select_option(self, option: str) -> None:
        """Set section policy."""
        if option not in POLICY_OPTIONS:
            return
        self._current_option = option
        if option == POLICY_OPTIONS[0]:
            pending = self.coordinator.hass.data.setdefault(DOMAIN, {}).get("supervised_apply_pending_action")
            if isinstance(pending, dict) and pending.get("section") == self._section:
                cancel_pending_action(self.coordinator.hass)
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    @property
    def extra_state_attributes(self) -> dict[str, str | bool]:
        """Return policy diagnostics."""
        return {
            "source": "python_control_policy",
            "section": self._section,
            "effective_policy": section_policy(self.coordinator.hass, self._section),
            "default_policy": str(self._config.get("default_policy")),
            "direct_unlock_entity": str(self._config.get("direct_unlock_entity")),
        }
