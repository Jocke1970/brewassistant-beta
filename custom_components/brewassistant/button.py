"""BrewAssistant buttons."""

from __future__ import annotations

from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .brewzilla_learning import (
    async_apply_brewzilla_learning_recommendation,
    async_deny_brewzilla_learning_recommendation,
    build_brewzilla_learning_snapshot,
)
from .const import DOMAIN
from .coordinator import BrewAssistantCoordinator
from .counterflow_chiller import async_counterflow_chiller_ready, get_counterflow_chiller_snapshot
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
            BrewAssistantCounterflowChillerReadyButton(coordinator),
            BrewAssistantBrewZillaLearningApplyButton(coordinator),
            BrewAssistantBrewZillaLearningDenyButton(coordinator),
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


class BrewAssistantCounterflowChillerReadyButton(BrewAssistantEntity, ButtonEntity):
    """Mark the Counter Flow Chiller as connected and start hot-wort circulation."""

    _attr_has_entity_name = False

    def __init__(self, coordinator: BrewAssistantCoordinator) -> None:
        super().__init__(coordinator, "counterflow_chiller_ready")
        self._attr_unique_id = f"{DOMAIN}_button_counterflow_chiller_ready"
        self._attr_name = "BrewAssistant CFC Ready"
        self._attr_icon = "mdi:snowflake-thermometer"
        self._attr_suggested_object_id = f"{DOMAIN}_counterflow_chiller_ready"

    async def async_press(self) -> None:
        """Start the configured CFC sanitation circulation."""
        await async_counterflow_chiller_ready(self.coordinator.hass)
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return CFC diagnostics."""
        return get_counterflow_chiller_snapshot(self.coordinator.hass)


class BrewAssistantBrewZillaLearningApplyButton(BrewAssistantEntity, ButtonEntity):
    """Apply current BrewZilla Learning recommendation."""

    _attr_has_entity_name = False

    def __init__(self, coordinator: BrewAssistantCoordinator) -> None:
        super().__init__(coordinator, "brewzilla_learning_apply")
        self._attr_unique_id = f"{DOMAIN}_button_brewzilla_learning_apply"
        self._attr_name = "BrewAssistant BrewZilla Learning APPLY"
        self._attr_icon = "mdi:check-decagram"
        self._attr_suggested_object_id = f"{DOMAIN}_brewzilla_learning_apply"

    async def async_press(self) -> None:
        """Apply current recommendation."""
        await async_apply_brewzilla_learning_recommendation(self.coordinator.hass)
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return recommendation diagnostics."""
        return build_brewzilla_learning_snapshot(self.coordinator.hass)


class BrewAssistantBrewZillaLearningDenyButton(BrewAssistantEntity, ButtonEntity):
    """Deny current BrewZilla Learning recommendation."""

    _attr_has_entity_name = False

    def __init__(self, coordinator: BrewAssistantCoordinator) -> None:
        super().__init__(coordinator, "brewzilla_learning_deny")
        self._attr_unique_id = f"{DOMAIN}_button_brewzilla_learning_deny"
        self._attr_name = "BrewAssistant BrewZilla Learning DENY"
        self._attr_icon = "mdi:close-octagon"
        self._attr_suggested_object_id = f"{DOMAIN}_brewzilla_learning_deny"

    async def async_press(self) -> None:
        """Deny current recommendation."""
        await async_deny_brewzilla_learning_recommendation(self.coordinator.hass)
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return recommendation diagnostics."""
        return build_brewzilla_learning_snapshot(self.coordinator.hass)
