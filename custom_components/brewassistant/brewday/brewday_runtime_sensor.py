"""Brewday Runtime sensor entities."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import PERCENTAGE, UnitOfTemperature

from .brewday_addition_alert_sensor import create_brewday_addition_alert_sensors
from .brewday_audit_sensor import create_brewday_audit_sensors
from .brewday_runtime import build_brewday_runtime_snapshot, brewday_runtime_attrs
from .brewday_stage_sensor import create_brewday_stage_sensors
from .manual_brewday_store import get_manual_brewday_session
from ..brewzilla.brewzilla_energy_sensor import create_brewzilla_energy_sensors
from ..brewzilla.brewzilla_learning_sensor import create_brewzilla_learning_sensors
from ..brewzilla.brewzilla_orchestration_sensor import BrewAssistantBrewZillaOrchestrationSensor, ORCHESTRATION_SENSORS
from ..brewzilla.brewzilla_sensor import create_brewzilla_sensors
from ..const import DOMAIN
from ..coordinator import BrewAssistantCoordinator
from ..entity import BrewAssistantEntity


BREWDAY_RUNTIME_SENSORS: dict[str, dict[str, Any]] = {
    "brewday_runtime_source": {"field": "source"},
    "brewday_runtime_status": {"field": "status"},
    "brewday_runtime_state": {"field": "runtime_state"},
    "brewday_operator_control_state": {"field": "operator_control_state"},
    "brewday_runtime_stage": {"field": "stage"},
    "brewday_runtime_step": {"field": "step"},
    "brewday_runtime_next_step": {"field": "next_step"},
    "brewday_runtime_summary": {"field": "summary"},
    "brewday_live_progress": {
        "field": "progress",
        "unit": PERCENTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "brewday_live_time_remaining": {
        "field": "time_remaining_seconds",
        "unit": "s",
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "brewday_live_time_remaining_minutes": {
        "field": "time_remaining_minutes",
        "unit": "min",
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "brewday_target_temperature": {
        "field": "target_temperature",
        "unit": UnitOfTemperature.CELSIUS,
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "brewday_actual_temperature": {
        "field": "actual_temperature",
        "unit": UnitOfTemperature.CELSIUS,
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "brewday_snapshot_age_minutes": {
        "field": "snapshot_age_minutes",
        "unit": "min",
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "brewday_snapshot_updated_at": {"field": "snapshot_updated_at"},
    "brewday_awaiting_snapshot": {"field": "awaiting_snapshot"},
    "brewday_refresh_recommended": {"field": "refresh_recommended"},
}

MANUAL_BREWDAY_SESSION_SENSORS: dict[str, str] = {
    "manual_brewday_status": "status",
    "manual_brewday_stage": "stage",
}


def _display_name_from_key(key: str) -> str:
    """Return a stable human-readable name from an entity key."""
    return f"BrewAssistant {key.replace('_', ' ').title()}"


def create_brewday_runtime_sensors(
    coordinator: BrewAssistantCoordinator,
) -> list[SensorEntity]:
    """Create all Brewday Runtime, BrewZilla, Stage Engine, Audit, Learning, Energy and Addition sensors."""
    return (
        [BrewAssistantBrewdayRuntimeSensor(coordinator, key) for key in BREWDAY_RUNTIME_SENSORS]
        + [
            BrewAssistantManualBrewdaySessionSensor(coordinator, key, field)
            for key, field in MANUAL_BREWDAY_SESSION_SENSORS.items()
        ]
        + create_brewzilla_sensors(coordinator)
        + [
            BrewAssistantBrewZillaOrchestrationSensor(coordinator, key)
            for key in ORCHESTRATION_SENSORS
        ]
        + create_brewday_stage_sensors(coordinator)
        + create_brewday_audit_sensors(coordinator)
        + create_brewzilla_learning_sensors(coordinator)
        + create_brewzilla_energy_sensors(coordinator)
        + create_brewday_addition_alert_sensors(coordinator)
    )


class BrewAssistantBrewdayRuntimeSensor(BrewAssistantEntity, SensorEntity):
    """Read-only Brewday Runtime sensor."""

    _attr_has_entity_name = False

    def __init__(self, coordinator: BrewAssistantCoordinator, key: str) -> None:
        """Initialize the Brewday Runtime sensor."""
        super().__init__(coordinator, key)
        self._key = key
        self._field = str(BREWDAY_RUNTIME_SENSORS[key]["field"])
        self._attr_name = _display_name_from_key(key)
        self._attr_suggested_object_id = f"{DOMAIN}_{key}"
        self._attr_native_unit_of_measurement = BREWDAY_RUNTIME_SENSORS[key].get("unit")
        self._attr_device_class = BREWDAY_RUNTIME_SENSORS[key].get("device_class")
        self._attr_state_class = BREWDAY_RUNTIME_SENSORS[key].get("state_class")

    @property
    def native_value(self) -> Any:
        """Return Brewday Runtime value."""
        return build_brewday_runtime_snapshot(self.coordinator.hass).get(self._field)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return Brewday Runtime attributes."""
        snapshot = build_brewday_runtime_snapshot(self.coordinator.hass)
        attrs = brewday_runtime_attrs(snapshot)
        if self._key in {"brewday_runtime_summary", "brewday_runtime_state", "brewday_runtime_next_step"}:
            attrs["timeline"] = snapshot.get("timeline")
        return attrs


class BrewAssistantManualBrewdaySessionSensor(BrewAssistantEntity, SensorEntity):
    """Expose the Python-owned Manual Brewday session independently of runtime ownership."""

    _attr_has_entity_name = False

    def __init__(self, coordinator: BrewAssistantCoordinator, key: str, field: str) -> None:
        """Initialize one Manual Brewday session sensor."""
        super().__init__(coordinator, key)
        self._key = key
        self._field = field
        self._attr_name = _display_name_from_key(key)
        self._attr_suggested_object_id = f"{DOMAIN}_{key}"

    def _snapshot(self) -> dict[str, Any]:
        return get_manual_brewday_session(self.coordinator.hass).to_snapshot()

    @property
    def native_value(self) -> Any:
        """Return the requested Manual Brewday session field."""
        return self._snapshot().get(self._field)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return useful Manual Brewday session diagnostics."""
        snapshot = self._snapshot()
        return {
            "source": "Manual Brewday",
            "runtime_state": snapshot.get("runtime_state"),
            "stage": snapshot.get("stage"),
            "step": snapshot.get("step"),
            "next_step": snapshot.get("next_step"),
            "progress": snapshot.get("progress"),
            "summary": snapshot.get("summary"),
        }
