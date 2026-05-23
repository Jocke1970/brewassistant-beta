"""BrewZilla orchestration sensor entities."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.const import UnitOfTemperature

from .brewzilla_orchestration import build_orchestration_snapshot
from .const import DOMAIN
from .coordinator import BrewAssistantCoordinator
from .entity import BrewAssistantEntity


ORCHESTRATION_SENSORS: dict[str, dict[str, Any]] = {
    "brewzilla_orchestration_mode": {"field": "orchestration_mode"},
    "brewzilla_control_reason": {"field": "control_reason"},
    "brewzilla_safety_state": {"field": "safety_state"},
    "brewzilla_requested_target": {
        "field": "requested_target",
        "unit": UnitOfTemperature.CELSIUS,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "brewzilla_applied_target": {
        "field": "applied_target",
        "unit": UnitOfTemperature.CELSIUS,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "brewzilla_target_delta": {
        "field": "target_delta",
        "unit": UnitOfTemperature.CELSIUS,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "brewzilla_target_sync_needed": {"field": "target_sync_needed"},
    "brewzilla_can_apply_target": {"field": "can_apply_target"},
}


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up BrewZilla orchestration sensors."""
    coordinator: BrewAssistantCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            BrewAssistantBrewZillaOrchestrationSensor(coordinator, key)
            for key in ORCHESTRATION_SENSORS
        ]
    )


class BrewAssistantBrewZillaOrchestrationSensor(BrewAssistantEntity, SensorEntity):
    """Read-only BrewZilla orchestration sensor."""

    _attr_has_entity_name = False

    def __init__(self, coordinator: BrewAssistantCoordinator, key: str) -> None:
        super().__init__(coordinator, key)
        self._key = key
        self._field = str(ORCHESTRATION_SENSORS[key]["field"])
        self._attr_name = f"BrewAssistant {key.replace('_', ' ').title()}"
        self._attr_suggested_object_id = f"{DOMAIN}_{key}"
        self._attr_native_unit_of_measurement = ORCHESTRATION_SENSORS[key].get("unit")
        self._attr_state_class = ORCHESTRATION_SENSORS[key].get("state_class")

    @property
    def native_value(self) -> Any:
        return build_orchestration_snapshot(self.coordinator.hass).get(self._field)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return dict(build_orchestration_snapshot(self.coordinator.hass))
