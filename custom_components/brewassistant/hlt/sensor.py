"""Read-only HLT dashboard entities: physical readings never masquerade as simulation.

These sensors are updated by the normal 30 s BrewAssistant coordinator. The HLT
runtime is a separate 30 s simulation-only timer, so the UI may lag one refresh.
"""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import UnitOfPower, UnitOfTemperature

from ..const import DOMAIN
from ..entity import BrewAssistantEntity
from .metrics import build_hlt_dashboard_snapshot


HLT_SENSORS: dict[str, dict[str, Any]] = {
    "hlt_status": {"field": "status"},
    "hlt_reason": {"field": "reason"},
    "hlt_power_priority": {"field": "power_priority"},
    "hlt_power_owner": {"field": "power_owner"},
    "hlt_actual_energy_recipient": {"field": "actual_energy_recipient"},
    "hlt_virtual_energy_recipient": {"field": "virtual_energy_recipient"},
    "hlt_brewzilla_power_observed": {"field": "bz_power_observed_w", "unit": UnitOfPower.WATT, "device_class": SensorDeviceClass.POWER},
    "hlt_power_observed": {"field": "hlt_power_observed_w", "unit": UnitOfPower.WATT, "device_class": SensorDeviceClass.POWER},
    "hlt_power_virtual": {"field": "hlt_power_virtual_w", "unit": UnitOfPower.WATT, "device_class": SensorDeviceClass.POWER},
    "hlt_total_power_observed": {"field": "actual_total_observed_w", "unit": UnitOfPower.WATT, "device_class": SensorDeviceClass.POWER},
    "hlt_total_power_virtual_scenario": {"field": "virtual_total_scenario_w", "unit": UnitOfPower.WATT, "device_class": SensorDeviceClass.POWER},
    "hlt_budget_scenario": {"field": "budget_scenario_w", "unit": UnitOfPower.WATT, "device_class": SensorDeviceClass.POWER},
    "hlt_headroom_observed": {"field": "actual_headroom_observed_w", "unit": UnitOfPower.WATT, "device_class": SensorDeviceClass.POWER},
    "hlt_temperature": {"field": "hlt_temperature_c", "unit": UnitOfTemperature.CELSIUS, "device_class": SensorDeviceClass.TEMPERATURE},
    "hlt_temperature_measured": {"field": "hlt_temperature_measured_c", "unit": UnitOfTemperature.CELSIUS, "device_class": SensorDeviceClass.TEMPERATURE},
    "hlt_temperature_estimated": {"field": "hlt_temperature_estimated_c", "unit": UnitOfTemperature.CELSIUS, "device_class": SensorDeviceClass.TEMPERATURE},
    "hlt_temperature_source": {"field": "hlt_temperature_source"},
    "hlt_target_temperature": {"field": "hlt_target_c", "unit": UnitOfTemperature.CELSIUS, "device_class": SensorDeviceClass.TEMPERATURE},
    "hlt_volume": {"field": "hlt_volume_l", "unit": "L"},
    "hlt_total_session_seconds": {"field": "total_session_seconds", "unit": "s"},
    "hlt_virtual_heating_seconds": {"field": "virtual_heating_seconds", "unit": "s"},
    "hlt_observed_heating_estimate_seconds": {"field": "observed_heating_estimate_seconds", "unit": "s"},
    "hlt_waiting_seconds": {"field": "waiting_seconds", "unit": "s"},
    "hlt_yielding_seconds": {"field": "yielding_seconds", "unit": "s"},
    "hlt_unknown_sample_seconds": {"field": "unknown_sample_seconds", "unit": "s"},
    "hlt_brewzilla_energy_estimate_wh": {"field": "bz_energy_estimate_wh", "unit": "Wh"},
    "hlt_energy_estimate_wh": {"field": "hlt_energy_estimate_wh", "unit": "Wh"},
    "hlt_yield_count": {"field": "yield_count"},
    "hlt_reclaim_count": {"field": "reclaim_count"},
    "hlt_trace_path": {"field": "trace_path"},
    "hlt_timing_quality": {"field": "timing_quality"},
}


def create_hlt_sensors(coordinator: Any) -> list[SensorEntity]:
    """Create UI entities without adding a new power-control platform."""
    return [BrewAssistantHLTSensor(coordinator, key) for key in HLT_SENSORS]


class BrewAssistantHLTSensor(BrewAssistantEntity, SensorEntity):
    _attr_has_entity_name = False

    def __init__(self, coordinator: Any, key: str) -> None:
        super().__init__(coordinator, key)
        self._key = key
        self._field = HLT_SENSORS[key]["field"]
        self._attr_name = f"BrewAssistant {key.replace('_', ' ').title()}"
        self._attr_suggested_object_id = f"{DOMAIN}_{key}"
        self._attr_native_unit_of_measurement = HLT_SENSORS[key].get("unit")
        self._attr_device_class = HLT_SENSORS[key].get("device_class")
        if self._attr_device_class in {SensorDeviceClass.POWER, SensorDeviceClass.TEMPERATURE}:
            self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> Any:
        return build_hlt_dashboard_snapshot(self.coordinator.hass).get(self._field)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self._key != "hlt_status":
            return None
        snapshot = build_hlt_dashboard_snapshot(self.coordinator.hass)
        return {
            "simulation_only": snapshot.get("simulation_only", True),
            "physical_control_enabled": False,
            "power_budget_verified": False,
            "session_started_at_epoch": snapshot.get("session_started_at_epoch"),
            "updated_at_epoch": snapshot.get("updated_at_epoch"),
            "hlt_virtual_heater_on": snapshot.get("hlt_virtual_heater_on"),
            "hlt_switch_observed": snapshot.get("hlt_switch_observed"),
            "bz_cruising_observed": snapshot.get("bz_cruising_observed"),
            "bz_ramp_requested": snapshot.get("bz_ramp_requested"),
            "temperature_uncertainty": snapshot.get("hlt_temperature_uncertainty"),
            "timing_quality": snapshot.get("timing_quality"),
        }
