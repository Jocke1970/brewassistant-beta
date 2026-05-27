"""Read-only fermentation chamber-air target recommendations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import UnitOfTemperature

from .const import DOMAIN
from .coordinator import BrewAssistantCoordinator
from .entity import BrewAssistantEntity

FALLBACK_SOURCES = {"chamber fallback", "unavailable"}
ACTIVE_STAGES = {"fermentation", "cold_crash"}
ACTIVE_STATUSES = {"primary fermentation", "cold crash"}
LIQUID_AVG_ENTITY = "sensor.brewassistant_fermentation_liquid_temperature_average"
CHAMBER_AVG_ENTITY = "sensor.brewassistant_fermentation_chamber_air_temperature_average"
DELTA_AVG_ENTITY = "sensor.brewassistant_fermentation_air_liquid_delta_average"


@dataclass(frozen=True, kw_only=True)
class AirTargetSensorConfig:
    key: str
    name: str
    snapshot_key: str
    icon: str
    unit: str | None = None
    device_class: SensorDeviceClass | None = None
    state_class: SensorStateClass | None = None


def _float_state(coordinator: BrewAssistantCoordinator, entity_id: str) -> float | None:
    state = coordinator.hass.states.get(entity_id)
    if state is None or state.state in {"unknown", "unavailable", "none", ""}:
        return None
    try:
        return float(state.state)
    except (TypeError, ValueError):
        return None


def _float_attr(coordinator: BrewAssistantCoordinator, entity_id: str, attr: str) -> float | None:
    state = coordinator.hass.states.get(entity_id)
    if state is None:
        return None
    try:
        value = state.attributes.get(attr)
        if value is None or str(value).lower() in {"unknown", "unavailable", "none", ""}:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _scope_active(coordinator: BrewAssistantCoordinator) -> bool:
    data = coordinator.data
    if data is None:
        return False
    return (
        (data.process_current_action_stage or "").lower() in ACTIVE_STAGES
        or (data.process_status or "").lower() in ACTIVE_STATUSES
    )


def _real_liquid_available(coordinator: BrewAssistantCoordinator) -> bool:
    data = coordinator.data
    if data is None or data.fallback_active:
        return False
    if (data.liquid_temperature_source or "").lower() in FALLBACK_SOURCES:
        return False
    return data.liquid_temperature is not None and data.liquid_temperature_entity is not None


def _mode(coordinator: BrewAssistantCoordinator) -> str:
    data = coordinator.data
    if data is None or not _scope_active(coordinator):
        return "standby"
    if (
        (data.process_current_action_stage or "").lower() == "cold_crash"
        or (data.process_status or "").lower() == "cold crash"
        or (data.temperature_target_mode or "").lower() == "cold crash"
    ):
        return "cold_crash"
    return "fermentation"


def _liquid(coordinator: BrewAssistantCoordinator) -> float | None:
    avg = _float_state(coordinator, LIQUID_AVG_ENTITY)
    if avg is not None:
        return avg
    data = coordinator.data
    return data.liquid_temperature if data is not None and _real_liquid_available(coordinator) else None


def _chamber(coordinator: BrewAssistantCoordinator) -> float | None:
    avg = _float_state(coordinator, CHAMBER_AVG_ENTITY)
    if avg is not None:
        return avg
    data = coordinator.data
    return data.chamber_temperature if data is not None else None


def _trend(coordinator: BrewAssistantCoordinator) -> float | None:
    return _float_attr(coordinator, LIQUID_AVG_ENTITY, "trend_c_per_hour")


def _clamp(value: float, low: float, high: float) -> float:
    return round(max(low, min(high, value)), 1)


def _recommend(mode: str, delta: float, target: float, trend: float | None) -> tuple[float, str, str]:
    if mode == "cold_crash":
        if delta >= 8:
            air, demand, reason = target - 1.5, "strong_cooling", "liquid far above cold-crash target"
        elif delta >= 4:
            air, demand, reason = target - 1.0, "cooling", "liquid above cold-crash target"
        elif delta >= 1:
            air, demand, reason = target - 0.5, "mild_cooling", "liquid approaching cold-crash target"
        elif delta >= 0.3:
            air, demand, reason = target, "settle", "liquid close to cold-crash target"
        elif delta >= -0.2:
            air, demand, reason = target + 0.5, "hold", "liquid at cold-crash target"
        else:
            air, demand, reason = target + 1.0, "relax", "liquid below cold-crash target"
        if trend is not None and trend < -2 and delta < 2:
            air += 0.5
            reason = f"{reason}; liquid falling quickly"
        return _clamp(air, 0.5, 8.0), demand, reason

    if delta >= 1:
        air, demand, reason = target - 1.5, "cooling", "liquid above fermentation target"
    elif delta >= 0.5:
        air, demand, reason = target - 1.0, "mild_cooling", "liquid slightly above fermentation target"
    elif delta >= 0.2:
        air, demand, reason = target - 0.5, "nudge_cooling", "liquid just above fermentation target"
    elif delta <= -1:
        air, demand, reason = target + 1.5, "warm_or_relax", "liquid below fermentation target"
    elif delta <= -0.5:
        air, demand, reason = target + 1.0, "hold_warm", "liquid slightly below fermentation target"
    elif delta <= -0.2:
        air, demand, reason = target + 0.5, "ease_cooling", "liquid just below fermentation target"
    else:
        air, demand, reason = target, "hold", "liquid close to fermentation target"
    return _clamp(air, 7.0, 35.0), demand, reason


def build_air_target_snapshot(coordinator: BrewAssistantCoordinator) -> dict[str, Any]:
    data = coordinator.data
    mode = _mode(coordinator)
    active = _scope_active(coordinator)
    real_liquid = _real_liquid_available(coordinator)
    target = data.recipe_target_temperature if data is not None else None
    liquid = _liquid(coordinator) if active and real_liquid else None
    chamber = _chamber(coordinator)
    trend = _trend(coordinator) if active and real_liquid else None

    liquid_delta = round(liquid - target, 2) if active and liquid is not None and target is not None else None
    avg_air_liquid_delta = _float_state(coordinator, DELTA_AVG_ENTITY) if active else None
    air_liquid_delta = avg_air_liquid_delta
    if active and air_liquid_delta is None and chamber is not None and liquid is not None:
        air_liquid_delta = round(chamber - liquid, 2)

    air_target = None
    demand = "standby"
    reason = "no active fermentation or cold-crash scope"
    ready = False

    if not active:
        reason = "no active fermentation or cold-crash scope"
    elif not real_liquid:
        demand = "unavailable"
        reason = "real liquid source unavailable"
    elif target is None:
        demand = "unavailable"
        reason = "target temperature unavailable"
    elif liquid_delta is None:
        demand = "unavailable"
        reason = "liquid temperature unavailable"
    else:
        air_target, demand, reason = _recommend(mode, liquid_delta, target, trend)
        ready = True

    air_target_delta = round(chamber - air_target, 2) if chamber is not None and air_target is not None else None
    summary = f"{mode} · {demand} · {reason}"
    if liquid is not None and target is not None and air_target is not None:
        summary = f"{mode} · {demand} · liquid {liquid:.1f} → {target:.1f} °C · air target {air_target:.1f} °C"

    return {
        "ready": ready,
        "scope_active": active,
        "mode": mode,
        "demand": demand,
        "reason": reason,
        "liquid_temperature": round(liquid, 2) if liquid is not None else None,
        "liquid_target_temperature": round(target, 2) if active and target is not None else None,
        "liquid_delta": liquid_delta,
        "liquid_trend_c_per_hour": trend,
        "chamber_air_temperature": round(chamber, 2) if chamber is not None else None,
        "air_liquid_delta": air_liquid_delta,
        "effective_air_target": air_target,
        "air_target_delta": air_target_delta,
        "real_liquid_source_available": real_liquid,
        "liquid_source": data.liquid_temperature_source if data is not None else None,
        "liquid_source_entity": data.liquid_temperature_entity if data is not None else None,
        "target_mode": data.temperature_target_mode if data is not None else None,
        "process_status": data.process_status if data is not None else None,
        "process_stage": data.process_current_action_stage if data is not None else None,
        "summary": summary,
        "source": "python_fermentation_air_target",
        "control": "read_only",
    }


SENSORS: tuple[AirTargetSensorConfig, ...] = (
    AirTargetSensorConfig(key="fermentation_effective_air_target", name="BrewAssistant Fermentation Effective Air Target", snapshot_key="effective_air_target", icon="mdi:target", unit=UnitOfTemperature.CELSIUS, device_class=SensorDeviceClass.TEMPERATURE, state_class=SensorStateClass.MEASUREMENT),
    AirTargetSensorConfig(key="fermentation_climate_demand", name="BrewAssistant Fermentation Climate Demand", snapshot_key="demand", icon="mdi:thermostat-auto"),
    AirTargetSensorConfig(key="fermentation_climate_mode", name="BrewAssistant Fermentation Climate Mode", snapshot_key="mode", icon="mdi:state-machine"),
    AirTargetSensorConfig(key="fermentation_air_target_reason", name="BrewAssistant Fermentation Air Target Reason", snapshot_key="reason", icon="mdi:text-box-check-outline"),
    AirTargetSensorConfig(key="fermentation_liquid_delta", name="BrewAssistant Fermentation Liquid Delta", snapshot_key="liquid_delta", icon="mdi:delta", unit=UnitOfTemperature.CELSIUS, device_class=SensorDeviceClass.TEMPERATURE, state_class=SensorStateClass.MEASUREMENT),
    AirTargetSensorConfig(key="fermentation_air_liquid_delta", name="BrewAssistant Fermentation Air Liquid Delta", snapshot_key="air_liquid_delta", icon="mdi:arrow-expand-vertical", unit=UnitOfTemperature.CELSIUS, device_class=SensorDeviceClass.TEMPERATURE, state_class=SensorStateClass.MEASUREMENT),
    AirTargetSensorConfig(key="fermentation_air_target_summary", name="BrewAssistant Fermentation Air Target Summary", snapshot_key="summary", icon="mdi:script-text-outline"),
)


class BrewAssistantAirTargetSensor(BrewAssistantEntity, SensorEntity):
    _attr_has_entity_name = False

    def __init__(self, coordinator: BrewAssistantCoordinator, config: AirTargetSensorConfig) -> None:
        super().__init__(coordinator, config.key)
        self._config = config
        self._attr_name = config.name
        self._attr_suggested_object_id = f"{DOMAIN}_{config.key}"
        self._attr_icon = config.icon
        if config.unit is not None:
            self._attr_native_unit_of_measurement = config.unit
        if config.device_class is not None:
            self._attr_device_class = config.device_class
        if config.state_class is not None:
            self._attr_state_class = config.state_class

    @property
    def native_value(self) -> Any:
        return build_air_target_snapshot(self.coordinator).get(self._config.snapshot_key)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return build_air_target_snapshot(self.coordinator)


def create_fermentation_air_target_sensors(coordinator: BrewAssistantCoordinator) -> list[BrewAssistantAirTargetSensor]:
    return [BrewAssistantAirTargetSensor(coordinator, config) for config in SENSORS]
