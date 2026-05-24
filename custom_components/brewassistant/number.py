"""BrewAssistant number controls."""

from __future__ import annotations

from typing import Any

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .carbonation_runtime import get_carbonation_runtime, update_carbonation_runtime
from .const import DOMAIN
from .coordinator import BrewAssistantCoordinator
from .entity import BrewAssistantEntity


CARBONATION_NUMBERS: dict[str, dict[str, Any]] = {
    "carbonation_pressure_bar_control": {
        "name": "BrewAssistant Carbonation Pressure Bar",
        "object_id": "brewassistant_carbonation_pressure_bar_control",
        "icon": "mdi:gauge",
        "unit": "bar",
        "min": 0.0,
        "max": 4.0,
        "step": 0.05,
        "runtime_key": "pressure_bar",
    },
    "carbonation_target_volumes_control": {
        "name": "BrewAssistant Carbonation Target Volumes",
        "object_id": "brewassistant_carbonation_target_volumes_control",
        "icon": "mdi:target",
        "unit": "vol",
        "min": 1.5,
        "max": 4.0,
        "step": 0.05,
        "runtime_key": "target_volumes",
    },
    "carbonation_start_volumes_control": {
        "name": "BrewAssistant Carbonation Start Volumes",
        "object_id": "brewassistant_carbonation_start_volumes_control",
        "icon": "mdi:beer-outline",
        "unit": "vol",
        "min": 0.3,
        "max": 2.5,
        "step": 0.05,
        "runtime_key": "start_volumes",
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BrewAssistant number controls."""
    coordinator: BrewAssistantCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        BrewAssistantCarbonationNumber(coordinator, key, config)
        for key, config in CARBONATION_NUMBERS.items()
    ])


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

    @property
    def native_value(self) -> float | None:
        """Return current value."""
        runtime = get_carbonation_runtime(self.coordinator.hass)
        value = getattr(runtime, str(self._config["runtime_key"]), None)
        return float(value) if value is not None else None

    async def async_set_native_value(self, value: float) -> None:
        """Set current value."""
        update_carbonation_runtime(self.coordinator.hass, {str(self._config["runtime_key"]): float(value)})
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return diagnostic attributes."""
        return {"source": "python_runtime_control", "runtime_key": self._config["runtime_key"]}
