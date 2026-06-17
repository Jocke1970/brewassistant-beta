"""BrewAssistant orchestration safety switches."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.restore_state import RestoreEntity

from .climate_backend.climate_supervisor import (
    async_apply_climate_supervisor,
    async_disable_climate_supervisor,
    async_enable_climate_supervisor,
    build_climate_supervisor_snapshot,
    supervisor_interval,
)
from .const import DOMAIN
from .coordinator import BrewAssistantCoordinator
from .cooling.counterflow_chiller import async_set_counterflow_chiller, get_counterflow_chiller_snapshot
from .entity import BrewAssistantEntity
from .fermentation.fermentation_climate_supervisor import (
    async_disable_fermentation_climate_supervisor,
    async_enable_fermentation_climate_supervisor,
    build_fermentation_climate_supervisor_snapshot,
    fermentation_supervisor_interval,
)
from .kegerator.fan_control import (
    async_apply_kegerator_fan_auto,
    async_disable_kegerator_fan_auto,
    build_kegerator_fan_snapshot,
    kegerator_fan_auto_interval,
)
from .kegerator.guard import (
    async_apply_kegerator_guard,
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
    "brewzilla_manual_target_override": {
        "name": "BrewAssistant BrewZilla Manual Target Override",
        "object_id": "brewassistant_brewzilla_manual_target_override",
        "icon": "mdi:hand-back-right-outline",
        "default": False,
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
    "counterflow_chiller_enabled": {
        "name": "BrewAssistant Counter Flow Chiller Enabled",
        "object_id": "brewassistant_counterflow_chiller_enabled",
        "icon": "mdi:snowflake-thermometer",
        "default": False,
        "kind": "counterflow_chiller",
    },
    "kegerator_guard_enabled": {
        "name": "BrewAssistant Kegerator Guard Enabled",
        "object_id": "brewassistant_kegerator_guard_enabled",
        "icon": "mdi:snowflake-alert",
        "default": False,
        "kind": "kegerator_guard",
    },
    "kegerator_fan_auto_enabled": {
        "name": "BrewAssistant Kegerator Fan Auto Enabled",
        "object_id": "brewassistant_kegerator_fan_auto_enabled",
        "icon": "mdi:fan-auto",
        "default": False,
        "kind": "kegerator_fan_auto",
    },
    "climate_supervisor_enabled": {
        "name": "BrewAssistant Climate Supervisor Enabled",
        "object_id": "brewassistant_climate_supervisor_enabled",
        "icon": "mdi:thermostat-auto",
        "default": False,
        "kind": "climate_supervisor",
    },
    "fermentation_climate_supervisor_enabled": {
        "name": "BrewAssistant Fermentation Climate Supervisor Enabled",
        "object_id": "brewassistant_fermentation_climate_supervisor_enabled",
        "icon": "mdi:thermostat-auto",
        "default": False,
        "kind": "fermentation_climate_supervisor",
    },
    "show_brewday": {
        "name": "BrewAssistant Show Brewday",
        "object_id": "brewassistant_show_brewday",
        "icon": "mdi:calendar-clock",
        "default": True,
        "kind": "dashboard_visibility",
        "module": "brewday",
        "card": "dashboard/cards/brewassistant_brewday.yaml",
    },
    "show_event_log": {
        "name": "BrewAssistant Show Event Log",
        "object_id": "brewassistant_show_event_log",
        "icon": "mdi:clipboard-text-clock-outline",
        "default": True,
        "kind": "dashboard_visibility",
        "module": "event_log",
        "card": "dashboard/cards/brewassistant_brewday_event_log.yaml",
    },
    "show_cfc": {
        "name": "BrewAssistant Show CFC",
        "object_id": "brewassistant_show_cfc",
        "icon": "mdi:snowflake-thermometer",
        "default": False,
        "kind": "dashboard_visibility",
        "module": "cfc",
        "card": "dashboard/cards/counterflow_chiller.yaml",
    },
    "show_fermentation": {
        "name": "BrewAssistant Show Fermentation",
        "object_id": "brewassistant_show_fermentation",
        "icon": "mdi:beer",
        "default": True,
        "kind": "dashboard_visibility",
        "module": "fermentation",
        "card": "dashboard/cards/fermentation.yaml",
    },
    "show_carbonation": {
        "name": "BrewAssistant Show Carbonation",
        "object_id": "brewassistant_show_carbonation",
        "icon": "mdi:chart-bubble",
        "default": True,
        "kind": "dashboard_visibility",
        "module": "carbonation",
        "card": "dashboard/cards/carbonation.yaml",
    },
    "show_kegerator": {
        "name": "BrewAssistant Show Kegerator",
        "object_id": "brewassistant_show_kegerator",
        "icon": "mdi:snowflake-thermometer",
        "default": True,
        "kind": "dashboard_visibility",
        "module": "kegerator",
        "card": "dashboard/cards/kegerator.yaml",
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
        self._tick_unsub = None
        self._clean_object_id = str(config["object_id"])
        self._clean_entity_id = f"switch.{self._clean_object_id}"
        self._entity_id_migration_result: str | None = None
        self._attr_unique_id = f"{DOMAIN}_switch_{key}"
        self._attr_name = str(config["name"])
        self._attr_icon = str(config["icon"])
        self._attr_is_on = bool(config.get("default", False))
        self._attr_suggested_object_id = self._clean_object_id
        if self._kind == "dashboard_visibility":
            self._attr_entity_id = self._clean_entity_id

    @property
    def name(self) -> str:
        """Return explicit display name."""
        return self._attr_name

    async def async_added_to_hass(self) -> None:
        """Restore last known switch state."""
        await super().async_added_to_hass()
        await self._async_migrate_dashboard_visibility_entity_id()
        last_state = await self.async_get_last_state()
        if last_state is not None:
            self._attr_is_on = last_state.state == "on"
        if self._kind == "counterflow_chiller":
            await async_set_counterflow_chiller(self.coordinator.hass, {"enabled": self._attr_is_on})
        if self._kind in {"kegerator_guard", "climate_supervisor", "fermentation_climate_supervisor", "kegerator_fan_auto"}:
            self._ensure_tick()
            if self._attr_is_on:
                if self._kind == "kegerator_guard":
                    await async_enable_kegerator_guard(self.coordinator.hass)
                if self._kind == "climate_supervisor":
                    await async_enable_climate_supervisor(self.coordinator.hass)
                if self._kind == "fermentation_climate_supervisor":
                    await async_enable_fermentation_climate_supervisor(self.coordinator.hass)
                await self._async_tick()

    async def _async_migrate_dashboard_visibility_entity_id(self) -> None:
        """Rename HA-prefixed dashboard visibility entity IDs back to clean IDs.

        Home Assistant may create area/device-prefixed entity IDs such as
        switch.bryggeriet_brewassistant_show_fermentation. The dashboard cards
        should be able to rely on the clean canonical switch IDs.
        """
        if self._kind != "dashboard_visibility":
            return
        current_entity_id = self.entity_id
        desired_entity_id = self._clean_entity_id
        if current_entity_id == desired_entity_id:
            self._entity_id_migration_result = "already_clean"
            return
        if not current_entity_id or "." not in current_entity_id:
            self._entity_id_migration_result = "missing_current_entity_id"
            return
        current_domain, current_object_id = current_entity_id.split(".", 1)
        if current_domain != "switch" or not current_object_id.endswith(self._clean_object_id):
            self._entity_id_migration_result = "manual_or_unexpected_entity_id_left_unchanged"
            return
        registry = er.async_get(self.coordinator.hass)
        if registry.async_get(desired_entity_id) is not None:
            self._entity_id_migration_result = "clean_entity_id_already_exists"
            return
        try:
            registry.async_update_entity(current_entity_id, new_entity_id=desired_entity_id)
            self.entity_id = desired_entity_id
            self._entity_id_migration_result = f"renamed:{current_entity_id}->{desired_entity_id}"
        except (KeyError, ValueError):
            self._entity_id_migration_result = "rename_failed"

    def _ensure_tick(self) -> None:
        """Ensure periodic apply/monitor loop for active switches."""
        if self._kind not in {"kegerator_guard", "climate_supervisor", "fermentation_climate_supervisor", "kegerator_fan_auto"} or self._tick_unsub is not None:
            return

        if self._kind == "climate_supervisor":
            interval = supervisor_interval()
        elif self._kind == "fermentation_climate_supervisor":
            interval = fermentation_supervisor_interval()
        elif self._kind == "kegerator_fan_auto":
            interval = kegerator_fan_auto_interval()
        else:
            interval = timedelta(seconds=30)

        async def _tick(now) -> None:
            await self._async_tick()

        self._tick_unsub = async_track_time_interval(
            self.coordinator.hass,
            _tick,
            interval,
        )
        self.async_on_remove(self._tick_unsub)

    async def _async_tick(self) -> None:
        """Apply/monitor active controller once and refresh this entity's attributes."""
        if self._attr_is_on and self._kind == "kegerator_guard":
            await async_apply_kegerator_guard(self.coordinator.hass)
        if self._attr_is_on and self._kind == "climate_supervisor":
            await async_apply_climate_supervisor(self.coordinator.hass)
        if self._attr_is_on and self._kind == "fermentation_climate_supervisor":
            build_fermentation_climate_supervisor_snapshot(self.coordinator.hass)
        if self._attr_is_on and self._kind == "kegerator_fan_auto":
            await async_apply_kegerator_fan_auto(self.coordinator.hass)
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        """Return switch state."""
        return bool(self._attr_is_on)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn switch on."""
        self._attr_is_on = True
        if self._kind == "counterflow_chiller":
            await async_set_counterflow_chiller(self.coordinator.hass, {"enabled": True})
            self.async_write_ha_state()
            return
        if self._kind == "kegerator_guard":
            self._ensure_tick()
            self.async_write_ha_state()
            await async_enable_kegerator_guard(self.coordinator.hass)
            await self._async_tick()
            return
        if self._kind == "kegerator_fan_auto":
            self._ensure_tick()
            self.async_write_ha_state()
            await self._async_tick()
            return
        if self._kind == "climate_supervisor":
            self._ensure_tick()
            self.async_write_ha_state()
            await async_enable_climate_supervisor(self.coordinator.hass)
            await self._async_tick()
            return
        if self._kind == "fermentation_climate_supervisor":
            self._ensure_tick()
            self.async_write_ha_state()
            await async_enable_fermentation_climate_supervisor(self.coordinator.hass)
            await self._async_tick()
            return
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn switch off."""
        self._attr_is_on = False
        if self._kind == "counterflow_chiller":
            await async_set_counterflow_chiller(self.coordinator.hass, {"enabled": False})
        if self._kind == "kegerator_guard":
            async_disable_kegerator_guard(self.coordinator.hass)
        if self._kind == "kegerator_fan_auto":
            async_disable_kegerator_fan_auto(self.coordinator.hass)
        if self._kind == "climate_supervisor":
            async_disable_climate_supervisor(self.coordinator.hass)
        if self._kind == "fermentation_climate_supervisor":
            async_disable_fermentation_climate_supervisor(self.coordinator.hass)
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return switch diagnostics."""
        if self._kind == "counterflow_chiller":
            return get_counterflow_chiller_snapshot(self.coordinator.hass)
        if self._kind == "kegerator_guard":
            return build_kegerator_guard_snapshot(self.coordinator.hass)
        if self._kind == "kegerator_fan_auto":
            return build_kegerator_fan_snapshot(self.coordinator.hass)
        if self._kind == "climate_supervisor":
            return build_climate_supervisor_snapshot(self.coordinator.hass)
        if self._kind == "fermentation_climate_supervisor":
            return build_fermentation_climate_supervisor_snapshot(self.coordinator.hass)
        if self._kind == "dashboard_visibility":
            return {
                "source": "dashboard_visibility",
                "kind": self._kind,
                "module": self._config.get("module"),
                "card": self._config.get("card"),
                "default_visible": bool(self._config.get("default", False)),
                "clean_entity_id": self._clean_entity_id,
                "entity_id_migration_result": self._entity_id_migration_result,
                "purpose": "Controls whether the matching BrewAssistant dashboard card should be shown by default.",
            }
        return {
            "source": "python_runtime_control",
            "kind": self._kind,
        }
