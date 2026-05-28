"""BrewAssistant buttons."""

from __future__ import annotations

from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import BrewAssistantCoordinator
from .entity import BrewAssistantEntity
from .supervised_apply import (
    async_confirm_pending_action,
    build_supervised_apply_snapshot,
    cancel_pending_action,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BrewAssistant buttons."""
    coordinator: BrewAssistantCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            BrewAssistantConfirmSupervisedApplyButton(coordinator),
            BrewAssistantCancelSupervisedApplyButton(coordinator),
        ]
    )


class BrewAssistantSupervisedApplyButton(BrewAssistantEntity, ButtonEntity):
    """Base supervised apply button."""

    _attr_has_entity_name = False

    def __init__(self, coordinator: BrewAssistantCoordinator, key: str, name: str, icon: str) -> None:
        super().__init__(coordinator, key)
        self._attr_unique_id = f"{DOMAIN}_button_{key}"
        self._attr_name = name
        self._attr_icon = icon
        self._attr_suggested_object_id = f"{DOMAIN}_{key}"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return supervised apply diagnostics."""
        return build_supervised_apply_snapshot(self.coordinator.hass)


class BrewAssistantConfirmSupervisedApplyButton(BrewAssistantSupervisedApplyButton):
    """Confirm pending supervised action."""

    def __init__(self, coordinator: BrewAssistantCoordinator) -> None:
        super().__init__(
            coordinator,
            "confirm_supervised_apply",
            "BrewAssistant Confirm Supervised Apply",
            "mdi:check-decagram",
        )

    async def async_press(self) -> None:
        """Confirm and execute pending supervised action."""
        await async_confirm_pending_action(self.coordinator.hass)
        self.async_write_ha_state()


class BrewAssistantCancelSupervisedApplyButton(BrewAssistantSupervisedApplyButton):
    """Cancel pending supervised action."""

    def __init__(self, coordinator: BrewAssistantCoordinator) -> None:
        super().__init__(
            coordinator,
            "cancel_supervised_apply",
            "BrewAssistant Cancel Supervised Apply",
            "mdi:cancel",
        )

    async def async_press(self) -> None:
        """Cancel pending supervised action."""
        cancel_pending_action(self.coordinator.hass)
        self.async_write_ha_state()
