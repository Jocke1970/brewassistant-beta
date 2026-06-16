"""BrewAssistant number controls."""

from __future__ import annotations

from typing import Any

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .carbonation_backend.carbonation_runtime import async_save_carbonation_runtime, get_carbonation_runtime, update_carbonation_runtime
from .const import DOMAIN
from .coordinator import BrewAssistantCoordinator
from .cooling.counterflow_chiller import async_set_counterflow_chiller, get_counterflow_chiller_snapshot
from .entity import BrewAssistantEntity


CARBONATION_NUMBERS: dict[str, dict[str, Any]] = {
    "carbonation_pressure_bar_control": {
        "name": "BrewAssistant Carbonation Pressure Bar",
        "object_id": "brewassistant_carbonation_pressure_bar",
        "icon": "mdi:gauge",
        "unit": "bar",
        "min": 0.0,
        "max": 4.0,
        "step": 0.05,
        "default": 0.0,
        "runtime_key": "pressure_bar",
    },
    "carbonation_target_volumes_control": {
        "name": "BrewAssistant Carbonation Target Volumes",
        "object_id": "brewassistant_carbonation_target_volumes",
        "icon": "mdi:target",
        "unit": "vol",
        "min": 1.5,
        "max": 4.0,
        "step": 0.05,
        "default": 2.4,
        "runtime_key": "target_volumes",
    },
    "carbonation_start_volumes_control": {
        "name": "BrewAssistant Carbonation Start Volumes",
        "object_id": "brewassistant_carbonation_start_volumes",
        "icon": "mdi:beer-outline",
        "unit": "vol",
        "min": 0.3,
        "max": 2.5,
        "step": 0.05,
        "default": 0.85,
        "runtime_key": "start_volumes",
    },
}

CFC_NUMBERS: dict[str, dict[str, Any]] = {
    "counterflow_chiller_sanitize_minutes": {
        "name": "BrewAssistant CFC Sanitize Minutes",
        "object_id": "brewassistant_counterflow_chiller_sanitize_minutes",
        "icon": "mdi:timer-outline",
        "unit": "min",
        "min": 10.0,
        "max": 25.0,
        "step": 1.0,
        "default": 15.0,
        "runtime_key": "sanitize_minutes",
    },
    "counterflow_chiller_pump_utilization": {
        "name": "BrewAssistant CFC Pump Utilization",
        "object_id": "brewassistant_counterflow_chiller_pump_utilization",
        "icon": "mdi:pump",
        "unit": "%",
        "min": 0.0,
        "max": 100.0,
        "step": 5.0,
        "default": 100.0,
        "runtime_key": "pump_utilization",
    },
}

KEGERATOR_FAN_NUMBERS: dict[str, dict[str, Any]] = {
    "kegerator_fan_afterrun_minutes": {
        "name": "BrewAssistant Kegerator Fan Afterrun Minutes",
        "object_id": "brewassistant_kegerator_fan_afterrun_minutes",
        "icon": "mdi:timer-outline",
        "unit": "min",
        "min": 0.0,
        "max": 60.0,
        "step": 1.0,
        "default": 10.0,
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BrewAssistant number controls."""
    coordinator: BrewAssistantCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            BrewAssistantCarbonationNumber(coordinator, key, config)
            for key, config in CARBONATION_NUMBERS.items()
        ]
        + [
            BrewAssistantCounterflowChillerNumber(coordinator, key, config)
            for key, config in CFC_NUMBERS.items()
        ]
        + [
            BrewAssistantKegeratorFanNumber(coordinator, key, config)
            for key, config in KEGERATOR_FAN_NUMBERS.items()
        ]
    )


class BrewAssistantKegeratorFanNumber(BrewAssistantEntity, RestoreEntity, NumberEntity):
    """Simple kegerator fan number control."""

    _attr_has_entity_name = False

    def __init__(self, coordinator: BrewAssistantCoordinator, key: str, config: dict[str, Any]) -> None:
        super().__init__(coordinator, key)
        self._config = config
        self._value = float(config["default"])
        self._attr_unique_id = f"{DOMAIN}_number_{key}"
        self._attr_name = str(config["name"])
        self._attr_suggested_object_id = str(config["object_id"])
        self._attr_icon = str(config["icon"])
        self._attr_native_unit_of_measurement = str(config["unit"])
        self._attr_native_min_value = float(config["min"])
        self._attr_native_max_value = float(config["max"])
        self._attr_native_step = float(config["step"])

    async def async_added_to_hass(self) -> None:
        """Restore number value after restart."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is None:
            return
        try:
            self._value = float(last_state.state)
        except (TypeError, ValueError):
            self._value = float(self._config["default"])

    @property
    def native_value(self) -> float | None:
        """Return current value."""
        return self._value

    async def async_set_native_value(self, value: float) -> None:
        """Set current value."""
        self._value = max(float(self._config["min"]), min(float(value), float(self._config["max"])))
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return diagnostics."""
        return {
            "source": "kegerator_fan_simple_control",
            "default": self._config.get("default"),
        }


class BrewAssistantCarbonationNumber(BrewAssistantEntity, RestoreEntity, NumberEntity):
    """Python-owned carbonation number control."""

    _attr_has_entity_name = False

    def __init__(self, coordinator: BrewAssistantCoordinator, key: str, config: dict[str, Any]) -> None:
        super().__init__(coordinator, key)
        self._config = config
        self._attr_unique_id = f"{DOMAIN}_number_{key}"
        self._attr_name = str(config["name"])
        self._attr_suggested_object_id = str(config["object_id"])
        self._attr_icon = str(config["icon"])
        self._attr_native_unit_of_measurement = str(config["unit"])
        self._attr_native_min_value = float(config["min"])
        self._attr_native_max_value = float(config["max"])
        self._attr_native_step = float(config["step"])

    async def async_added_to_hass(self) -> None:
        """Restore the number value into the runtime."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is None:
            return
        try:
            value = float(last_state.state)
        except (TypeError, ValueError):
            return
        update_carbonation_runtime(self.coordinator.hass, {str(self._config["runtime_key"]): value})
        await async_save_carbonation_runtime(self.coordinator.hass)

    @property
    def native_value(self) -> float | None:
        """Return current value with a UI-friendly fallback."""
        runtime = get_carbonation_runtime(self.coordinator.hass)
        value = getattr(runtime, str(self._config["runtime_key"]), None)
        if value is not None:
            return float(value)
        return float(self._config.get("default", self._config["min"]))

    async def async_set_native_value(self, value: float) -> None:
        """Set current value."""
        update_carbonation_runtime(self.coordinator.hass, {str(self._config["runtime_key"]): float(value)})
        await async_save_carbonation_runtime(self.coordinator.hass)
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return diagnostic attributes."""
        return {
            "source": "python_runtime_control",
            "runtime_key": self._config["runtime_key"],
            "display_default": self._config.get("default"),
        }


class BrewAssistantCounterflowChillerNumber(BrewAssistantEntity, RestoreEntity, NumberEntity):
    """Python-owned Counter Flow Chiller number control."""

    _attr_has_entity_name = False

    def __init__(self, coordinator: BrewAssistantCoordinator, key: str, config: dict[str, Any]) -> None:
        super().__init__(coordinator, key)
        self._config = config
        self._attr_unique_id = f"{DOMAIN}_number_{key}"
        self._attr_name = str(config["name"])
        self._attr_suggested_object_id = str(config["object_id"])
        self._attr_icon = str(config["icon"])
        self._attr_native_unit_of_measurement = str(config["unit"])
        self._attr_native_min_value = float(config["min"])
        self._attr_native_max_value = float(config["max"])
        self._attr_native_step = float(config["step"])

    async def async_added_to_hass(self) -> None:
        """Restore the number value into the CFC backend."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is None:
            return
        try:
            value = float(last_state.state)
        except (TypeError, ValueError):
            return
        await async_set_counterflow_chiller(
            self.coordinator.hass,
            {str(self._config["runtime_key"]): value},
        )

    @property
    def native_value(self) -> float | None:
        """Return current value."""
        snapshot = get_counterflow_chiller_snapshot(self.coordinator.hass)
        value = snapshot.get(str(self._config["runtime_key"]))
        if value is not None:
            return float(value)
        return float(self._config.get("default", self._config["min"]))

    async def async_set_native_value(self, value: float) -> None:
        """Set current value."""
        await async_set_counterflow_chiller(
            self.coordinator.hass,
            {str(self._config["runtime_key"]): float(value)},
        )
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return diagnostic attributes."""
        return {
            **get_counterflow_chiller_snapshot(self.coordinator.hass),
            "source": "python_runtime_control",
            "runtime_key": self._config["runtime_key"],
            "display_default": self._config.get("default"),
        }
