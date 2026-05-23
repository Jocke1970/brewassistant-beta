"""BrewAssistant orchestration safety switches."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN
from .coordinator import BrewAssistantCoordinator
from .entity import BrewAssistantEntity


ORCHESTRATION_SWITCHES: dict[str, dict[str, Any]] = {
    "brewzilla_orchestration_enabled": {
        "name": "BrewZilla orchestration",
        "icon": "mdi:robot-outline",
    },
    "brewzilla_apply_target_temp": {
        "name": "Apply Brewday target",
        "icon": "mdi:target",
    },
    "brewzilla_allow_heater_control": {
        "name": "Allow heater control",
        "icon": "mdi:fire-alert",
    },
    "brewzilla_allow_pump_control": {
        "name": "Allow pump control",
        "icon": "mdi:pump",
    },
    "brewzilla_allow_boil_mode": {
        "name": "Allow boil mode",
        "icon": "mdi:kettle-steam",
    },
    "brewzilla_safe_mode": {
        "name": "Safe mode",
        "icon": "mdi:shield-check",
        "default": True,
    },
}


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up BrewAssistant orchestration switches."""
    coordinator: BrewAssistantCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            BrewAssistantSafetySwitch(coordinator, key, config)
            for key, config in ORCHESTRATION_SWITCHES.items()
        ]
    )


class BrewAssistantSafetySwitch(BrewAssistantEntity, RestoreEntity, SwitchEntity):
    """Persistent orchestration safety switch."""

    _attr_has_entity_name = False

    def __init__(
        self,
        coordinator: BrewAssistantCoordinator,
        key: str,
        config: dict[str, Any],
    ) -> None:
        super().__init__(coordinator, key)
        self._key = key
        self._attr_name = f"BrewAssistant {config['name']}"
        self._attr_icon = config["icon"]
        self._attr_is_on = bool(config.get("default", False))
        self._attr_suggested_object_id = f"{DOMAIN}_{key}"

    async def async_added_to_hass(self) -> None:
        """Restore last known switch state."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None:
            self._attr_is_on = last_state.state == "on"

    @property
    def is_on(self) -> bool:
        """Return switch state."""
        return self._attr_is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn switch on."""
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn switch off."""
        self._attr_is_on = False
        self.async_write_ha_state()
