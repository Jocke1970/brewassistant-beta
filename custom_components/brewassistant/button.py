"""BrewAssistant buttons."""

from __future__ import annotations

from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .brewday.brewday_audit import async_record_brewday_audit_event
from .brewday.brewday_operator_abort import (
    async_clear_brewday_operator_abort,
    async_latch_brewday_operator_abort,
    async_load_brewday_operator_abort,
    brewday_operator_abort_snapshot,
)
from .brewday.brewday_runtime import build_brewday_runtime_snapshot
from .brewday.manual_brewday_store import get_manual_brewday_session
from .brewzilla.brewzilla_learning import (
    async_apply_brewzilla_learning_recommendation,
    async_deny_brewzilla_learning_recommendation,
    build_brewzilla_learning_snapshot,
)
from .brewzilla.brewzilla_mash_in_gate import (
    async_confirm_mash_in_complete,
    async_mark_mash_in_started,
    async_start_mash_circulation,
    build_mash_in_gate_snapshot,
)
from .brewzilla.brewzilla_orchestration import async_abort_brewzilla
from .brewzilla.brewzilla_owned_control import remember_owned_control_from_apply_result
from .const import DOMAIN
from .coordinator import BrewAssistantCoordinator
from .cooling.counterflow_chiller import async_counterflow_chiller_ready, get_counterflow_chiller_snapshot
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
    await async_load_brewday_operator_abort(hass)
    coordinator: BrewAssistantCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            BrewAssistantConfirmSupervisedApplyButton(coordinator),
            BrewAssistantCancelSupervisedApplyButton(coordinator),
            BrewAssistantAbortBrewdayButton(coordinator),
            BrewAssistantRearmBrewdayControlButton(coordinator),
            BrewAssistantCounterflowChillerReadyButton(coordinator),
            BrewAssistantBrewZillaMashInStartedButton(coordinator),
            BrewAssistantBrewZillaMashInCompleteButton(coordinator),
            BrewAssistantBrewZillaStartMashCirculationButton(coordinator),
            BrewAssistantBrewZillaLearningApplyButton(coordinator),
            BrewAssistantBrewZillaLearningDenyButton(coordinator),
        ]
    )


class BrewAssistantButtonEntity(BrewAssistantEntity, ButtonEntity):
    """Base class for BrewAssistant operator action buttons."""

    _attr_has_entity_name = True

    @property
    def available(self) -> bool:
        """Return true for explicit operator action buttons.

        Buttons are commands, not telemetry. They must remain pressable even if
        the coordinator has a stale or failed refresh, otherwise recovery actions
        such as mash circulation cannot be used exactly when they are needed.
        """
        return True


class BrewAssistantSupervisedApplyButton(BrewAssistantButtonEntity):
    """Base supervised apply button."""

    def __init__(self, coordinator: BrewAssistantCoordinator, key: str, icon: str) -> None:
        super().__init__(coordinator, key)
        self._attr_unique_id = f"{DOMAIN}_button_{key}"
        self._attr_translation_key = key
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
            "mdi:cancel",
        )

    async def async_press(self) -> None:
        """Cancel pending supervised action."""
        cancel_pending_action(self.coordinator.hass)
        self.async_write_ha_state()


class BrewAssistantAbortBrewdayButton(BrewAssistantButtonEntity):
    """Operator ABORT for the whole Brewday hot-side control path."""

    def __init__(self, coordinator: BrewAssistantCoordinator) -> None:
        super().__init__(coordinator, "abort_brewday")
        self._attr_unique_id = f"{DOMAIN}_button_abort_brewday"
        self._attr_name = "Abort Brewday"
        self._attr_icon = "mdi:alert-octagon-outline"
        self._attr_suggested_object_id = f"{DOMAIN}_abort_brewday"

    async def async_press(self) -> None:
        """Latch ownership off, cancel pending work and physically safe-down BrewZilla."""
        hass = self.coordinator.hass
        runtime = build_brewday_runtime_snapshot(hass)
        await async_latch_brewday_operator_abort(
            hass,
            source=str(runtime.get("source") or "None"),
            stage=str(runtime.get("stage") or "Idle"),
            step=str(runtime.get("step") or "Idle"),
        )

        # A Brewday ABORT is stronger than rejecting one pending plan: pending
        # positive intent is discarded and Manual Brewday is returned to idle.
        cancel_pending_action(hass)
        get_manual_brewday_session(hass).reset()

        # Reuse the authoritative BrewZilla ABORT path for physical safe-down
        # and its independent hardware lockout.
        result = await async_abort_brewzilla(hass)
        await async_record_brewday_audit_event(
            hass,
            "brewday_abort",
            note="Operator ABORT: Brewday ownership latched off; BrewZilla safe-down executed.",
            brewzilla_result=result,
            always_record=True,
        )
        await self.coordinator.async_request_refresh()
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return operator ABORT latch diagnostics."""
        return brewday_operator_abort_snapshot(self.coordinator.hass)


class BrewAssistantRearmBrewdayControlButton(BrewAssistantButtonEntity):
    """Explicitly rearm Brewday ownership after an operator ABORT."""

    def __init__(self, coordinator: BrewAssistantCoordinator) -> None:
        super().__init__(coordinator, "rearm_brewday_control")
        self._attr_unique_id = f"{DOMAIN}_button_rearm_brewday_control"
        self._attr_name = "Rearm Brewday Control"
        self._attr_icon = "mdi:shield-check-outline"
        self._attr_suggested_object_id = f"{DOMAIN}_rearm_brewday_control"

    async def async_press(self) -> None:
        """Release only the Brewday ownership latch; hardware ABORT lockout remains authoritative."""
        hass = self.coordinator.hass
        previous = brewday_operator_abort_snapshot(hass)
        await async_clear_brewday_operator_abort(hass)
        await async_record_brewday_audit_event(
            hass,
            "brewday_control_rearmed",
            note=(
                "Operator rearmed Brewday ownership after ABORT; "
                f"previous source {previous.get('source')} · {previous.get('stage')} · {previous.get('step')}."
            ),
            always_record=True,
        )
        await self.coordinator.async_request_refresh()
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return operator ABORT latch diagnostics."""
        return brewday_operator_abort_snapshot(self.coordinator.hass)


class BrewAssistantCounterflowChillerReadyButton(BrewAssistantButtonEntity):
    """Mark the Counter Flow Chiller as connected and start hot-wort circulation."""

    def __init__(self, coordinator: BrewAssistantCoordinator) -> None:
        super().__init__(coordinator, "counterflow_chiller_ready")
        self._attr_unique_id = f"{DOMAIN}_button_counterflow_chiller_ready"
        self._attr_translation_key = "counterflow_chiller_ready"
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


class BrewAssistantBrewZillaMashInStartedButton(BrewAssistantButtonEntity):
    """Mark that malt addition has started and release strike target."""

    def __init__(self, coordinator: BrewAssistantCoordinator) -> None:
        super().__init__(coordinator, "brewzilla_mash_in_started")
        self._attr_unique_id = f"{DOMAIN}_button_brewzilla_mash_in_started"
        self._attr_translation_key = "brewzilla_mash_in_started"
        self._attr_icon = "mdi:barley"
        self._attr_suggested_object_id = f"{DOMAIN}_mash_in_started"

    async def async_press(self) -> None:
        """Release strike target and hold pump paused while grain is added."""
        await async_mark_mash_in_started(self.coordinator.hass)
        await self.coordinator.async_request_refresh()
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return mash-in gate diagnostics."""
        return build_mash_in_gate_snapshot(self.coordinator.hass)


class BrewAssistantBrewZillaMashInCompleteButton(BrewAssistantButtonEntity):
    """Confirm that manual mash-in is complete and start mash circulation."""

    def __init__(self, coordinator: BrewAssistantCoordinator) -> None:
        super().__init__(coordinator, "brewzilla_mash_in_complete")
        self._attr_unique_id = f"{DOMAIN}_button_brewzilla_mash_in_complete"
        self._attr_translation_key = "brewzilla_mash_in_complete"
        self._attr_icon = "mdi:pump"
        self._attr_suggested_object_id = f"{DOMAIN}_mash_in_complete"

    async def async_press(self) -> None:
        """Release the mash-in pump pause gate and start circulation."""
        await async_confirm_mash_in_complete(self.coordinator.hass)
        await self.coordinator.async_request_refresh()
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return mash-in gate diagnostics."""
        return build_mash_in_gate_snapshot(self.coordinator.hass)


class BrewAssistantBrewZillaStartMashCirculationButton(BrewAssistantButtonEntity):
    """Explicitly start BrewZilla mash circulation."""

    def __init__(self, coordinator: BrewAssistantCoordinator) -> None:
        super().__init__(coordinator, "brewzilla_start_mash_circulation")
        self._attr_unique_id = f"{DOMAIN}_button_brewzilla_start_mash_circulation"
        self._attr_translation_key = "brewzilla_start_mash_circulation"
        self._attr_icon = "mdi:pump"
        self._attr_suggested_object_id = f"{DOMAIN}_start_mash_circulation"

    async def async_press(self) -> None:
        """Set pump utilization and turn the pump on."""
        await async_start_mash_circulation(self.coordinator.hass)
        await self.coordinator.async_request_refresh()
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return mash-in gate/circulation diagnostics."""
        return build_mash_in_gate_snapshot(self.coordinator.hass)


class BrewAssistantBrewZillaLearningApplyButton(BrewAssistantButtonEntity):
    """Apply current BrewZilla Learning recommendation."""

    def __init__(self, coordinator: BrewAssistantCoordinator) -> None:
        super().__init__(coordinator, "brewzilla_learning_apply")
        self._attr_unique_id = f"{DOMAIN}_button_brewzilla_learning_apply"
        self._attr_translation_key = "brewzilla_learning_apply"
        self._attr_icon = "mdi:check-decagram"
        self._attr_suggested_object_id = f"{DOMAIN}_brewzilla_learning_apply"

    async def async_press(self) -> None:
        """Apply current recommendation."""
        result = await async_apply_brewzilla_learning_recommendation(self.coordinator.hass)
        remember_owned_control_from_apply_result(self.coordinator.hass, result)
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return recommendation diagnostics."""
        return build_brewzilla_learning_snapshot(self.coordinator.hass)


class BrewAssistantBrewZillaLearningDenyButton(BrewAssistantButtonEntity):
    """Deny current BrewZilla Learning recommendation."""

    def __init__(self, coordinator: BrewAssistantCoordinator) -> None:
        super().__init__(coordinator, "brewzilla_learning_deny")
        self._attr_unique_id = f"{DOMAIN}_button_brewzilla_learning_deny"
        self._attr_translation_key = "brewzilla_learning_deny"
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
