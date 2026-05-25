"""BrewAssistant orchestration safety switches."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN
from .coordinator import BrewAssistantCoordinator
from .entity import BrewAssistantEntity
from .kegerator_guard import (
    async_disable_kegerator_guard,
    async_enable_kegerator_guard,
    build_kegerator_guard_snapshot,
)


ORCHESTRATION_SWITCHES: dict[str, dict[str, Any]] = {
    "brewzilla_orchestration_enabled": {
        "name": "BrewAssistant BrewZilla Orchestration Enabled",
        "object_id": "brewassistant_brewzilla_orchestration_enabled",
        "icon": "mdi:robot-outline",
    },
    "brewzilla_apply_target_temp": {
        "name": "BrewAssistant BrewZilla Apply Target Temp",
        "object_id": "brewassistant_brewzilla_apply_target_temp",
        "icon": "mdi:target",
    },
    "brewzilla_allow_heater_control": {
        "name": "BrewAssistant BrewZilla Allow Heater Control",
        "object_id": "brewassistant_brewzilla_allow_heater_control",
        "icon": "mdi:fire-alert",
    },
    "brewzilla_allow_pump_control": {
        "name": "BrewAssistant BrewZilla Allow Pump Control",
        "object_id": "brewassistant_brewzilla_allow_pump_control",
        "icon": "mdi:pump",
    },
    "brewzilla_allow_boil_mode": {
        "name": "BrewAssistant BrewZilla Allow Boil Mode",
        "object_id": "brewassistant_brewzilla_allow_boil_mode",
        "icon": "mdi:kettle-steam",
    },
    "brewzilla_safe_mode": {
        "name": "BrewAssistant BrewZilla Safe Mode",
        "object_id": "brewassistant_brewzilla_safe_mode",
        "icon": "mdi:shield-check",
        "default": True,
    },
    "kegerator_guard_enabled": {
        "name": "BrewAssistant Kegerator Guard Enabled",
        "object_id": "brewassistant_kegerator_guard_enabled",
        "icon": "mdi:snowflake-alert",
        "default": False,
        "kind": "kegerator_guard",
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
        self._config = config
        self._kind = str(config.get("kind", "safety"))
        self._attr_unique_id = f"{DOMAIN}_switch_{key}"
        self._attr_name = str(config["name"])
        self._attr_icon = str(config["icon"])
        self._attr_is_on = bool(config.get("default", False))
        self._attr_suggested_object_id = str(config["object_id"])

    @property
    def name(self) -> str:
        """Return explicit display name."""
        return self._attr_name

    async def async_added_to_hass(self) -> None:
        """Restore last known switch state."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None:
            self._attr_is_on = last_state.state == "on"
        if self._kind == "kegerator_guard" and self._attr_is_on:
            await async_enable_kegerator_guard(self.coordinator.hass)

    @property
    def is_on(self) -> bool:
        """Return switch state."""
        return bool(self._attr_is_on)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn switch on."""
        self._attr_is_on = True
        if self._kind == "kegerator_guard":
            await async_enable_kegerator_guard(self.coordinator.hass)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn switch off."""
        self._attr_is_on = False
        if self._kind == "kegerator_guard":
            async_disable_kegerator_guard(self.coordinator.hass)
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return switch diagnostics."""
        if self._kind == "kegerator_guard":
            return build_kegerator_guard_snapshot(self.coordinator.hass)
        return {
            "source": "python_runtime_control",
            "kind": self._kind,
        }
