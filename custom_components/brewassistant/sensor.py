"""Sensor platform for BrewAssistant."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .brewday_runtime_sensor import create_brewday_runtime_sensors
from .carbonation import build_carbonation_snapshot
from .const import (
    ATTR_COLOR_HINT,
    ATTR_ICON_HINT,
    ATTR_PROCESS_REASON,
    ATTR_SOURCE,
    ATTR_SOURCE_ENTITY,
    ATTR_TARGET_ENTITY,
    ATTR_TARGET_MODE,
    CONF_GRAVITY_ENTITY,
    CONF_RUNTIME_COLD_CRASH_TARGET_ENTITY,
    CONF_RUNTIME_PRIMARY_TARGET_ENTITY,
    CONF_RUNTIME_RECIPE_NAME_ENTITY,
    CONF_RUNTIME_STATUS_ENTITY,
    CONF_RUNTIME_TARGET_FG_ENTITY,
    DEFAULT_RUNTIME_COLD_CRASH_TARGET_ENTITY,
    DEFAULT_RUNTIME_PRIMARY_TARGET_ENTITY,
    DEFAULT_RUNTIME_RECIPE_NAME_ENTITY,
    DEFAULT_RUNTIME_STATUS_ENTITY,
    DEFAULT_RUNTIME_TARGET_FG_ENTITY,
    DOMAIN,
    VERSION,
)
from .coordinator import BrewAssistantCoordinator, BrewAssistantData
from .entity import BrewAssistantEntity
from .next_action import build_next_action
from .runtime import build_runtime_snapshot, runtime_attrs
from .smart_recommendations import SmartRecommendationData, build_smart_recommendations
from .source_health import (
    SOURCE_SENSOR_KEYS,
    build_source_health,
    source_health_attrs,
)

BREWFATHER_FERMENTATION_START_ENTITY = "sensor.brewfather_fermentation_start"
BATCH_STARTED_AT_ENTITY = "input_datetime.brew_batch_started_at"


@dataclass(frozen=True, kw_only=True)
class BrewAssistantSensorDescription(SensorEntityDescription):
    """Describes a BrewAssistant sensor."""

    value_fn: Callable[[BrewAssistantData], Any]
    extra_attributes_fn: Callable[[BrewAssistantCoordinator], dict[str, Any]] | None = None


@dataclass(frozen=True, kw_only=True)
class BrewAssistantSmartSensorDescription(SensorEntityDescription):
    """Describes a BrewAssistant smart recommendation sensor."""

    value_fn: Callable[[SmartRecommendationData], Any]


def _display_name_from_key(key: str) -> str:
    """Return a stable human-readable name from an entity key."""
    return f"BrewAssistant {key.replace('_', ' ').title()}"


def _entry_entity(coordinator: BrewAssistantCoordinator, key: str, default: str) -> str:
    """Return a configured entity id from options/data/default."""
    entry = coordinator.config_entry
    return str(entry.options.get(key) or entry.data.get(key) or default)


def _runtime_entities(coordinator: BrewAssistantCoordinator) -> dict[str, str]:
    """Return configured runtime source entities."""
    return {
        CONF_RUNTIME_RECIPE_NAME_ENTITY: _entry_entity(
            coordinator,
            CONF_RUNTIME_RECIPE_NAME_ENTITY,
            DEFAULT_RUNTIME_RECIPE_NAME_ENTITY,
        ),
        CONF_RUNTIME_STATUS_ENTITY: _entry_entity(
            coordinator,
            CONF_RUNTIME_STATUS_ENTITY,
            DEFAULT_RUNTIME_STATUS_ENTITY,
        ),
        CONF_RUNTIME_PRIMARY_TARGET_ENTITY: _entry_entity(
            coordinator,
            CONF_RUNTIME_PRIMARY_TARGET_ENTITY,
            DEFAULT_RUNTIME_PRIMARY_TARGET_ENTITY,
        ),
        CONF_RUNTIME_COLD_CRASH_TARGET_ENTITY: _entry_entity(
            coordinator,
            CONF_RUNTIME_COLD_CRASH_TARGET_ENTITY,
            DEFAULT_RUNTIME_COLD_CRASH_TARGET_ENTITY,
        ),
        CONF_RUNTIME_TARGET_FG_ENTITY: _entry_entity(
            coordinator,
            CONF_RUNTIME_TARGET_FG_ENTITY,
            DEFAULT_RUNTIME_TARGET_FG_ENTITY,
        ),
    }


def _liquid_attrs(coordinator: BrewAssistantCoordinator) -> dict[str, Any]:
    data = coordinator.data
    return {
        ATTR_SOURCE: data.liquid_temperature_source if data else None,
        ATTR_SOURCE_ENTITY: data.liquid_temperature_entity if data else None,
    }


def _target_attrs(coordinator: BrewAssistantCoordinator) -> dict[str, Any]:
    data = coordinator.data
    return {
        ATTR_TARGET_ENTITY: data.recipe_target_temperature_entity if data else None,
        ATTR_TARGET_MODE: data.temperature_target_mode if data else None,
    }


def _source_attrs(coordinator: BrewAssistantCoordinator) -> dict[str, Any]:
    data = coordinator.data
    return {ATTR_SOURCE_ENTITY: data.liquid_temperature_entity if data else None}


def _status_attrs(coordinator: BrewAssistantCoordinator) -> dict[str, Any]:
    data = coordinator.data
    return {
        ATTR_ICON_HINT: data.temperature_icon_hint if data else None,
        ATTR_COLOR_HINT: data.temperature_color_hint if data else None,
        ATTR_TARGET_MODE: data.temperature_target_mode if data else None,
    }


def _process_attrs(coordinator: BrewAssistantCoordinator) -> dict[str, Any]:
    data = coordinator.data
    return {
        ATTR_PROCESS_REASON: data.process_reason if data else None,
        ATTR_TARGET_MODE: data.temperature_target_mode if data else None,
        "source": "python_core",
    }


def _smart_data(coordinator: BrewAssistantCoordinator) -> SmartRecommendationData | None:
    data = coordinator.data
    if data is None:
        return None
    return build_smart_recommendations(
        coordinator.hass,
        liquid_temp=data.liquid_temperature,
        target_temp=data.recipe_target_temperature,
        delta=data.temperature_delta,
        chamber_temp=data.chamber_temperature,
        fallback_active=data.fallback_active,
        source=data.liquid_temperature_source,
    )


def _smart_attrs(smart: SmartRecommendationData | None) -> dict[str, Any]:
    if smart is None:
        return {}
    return {
        "mode": smart.mode,
        "enabled": smart.enabled,
        "heat_needed": smart.heat_needed,
        "heat_permitted": smart.heat_permitted,
        "cooling_recommended": smart.cooling_recommended,
        "fan_recommended": smart.fan_recommended,
        "rising_too_fast": smart.rising_too_fast,
        "block_reason": smart.block_reason,
        "pill_status": smart.pill_status,
        "pill_age_minutes": smart.pill_age_minutes,
        "pill_stale": smart.pill_stale,
    }


def _source_health(coordinator: BrewAssistantCoordinator) -> dict[str, Any]:
    return build_source_health(coordinator.hass, coordinator.configured_entities)


def _runtime_snapshot(coordinator: BrewAssistantCoordinator) -> dict[str, Any]:
    return build_runtime_snapshot(coordinator.hass, _runtime_entities(coordinator))


def _next_action(coordinator: BrewAssistantCoordinator) -> dict[str, Any]:
    return build_next_action(
        data=coordinator.data,
        smart=_smart_data(coordinator),
        source_health=_source_health(coordinator),
    )


def _gravity_last_updated(coordinator: BrewAssistantCoordinator) -> dict[str, Any]:
    """Return last-updated metadata for the configured gravity source."""
    source_entity = coordinator.configured_entities.get(CONF_GRAVITY_ENTITY)
    state = coordinator.hass.states.get(source_entity) if source_entity else None
    if state is None:
        return {
            "last_updated": None,
            "source_entity": source_entity,
            "source_state": None,
            "source_last_updated_iso": None,
        }

    last_updated = state.last_updated.isoformat()
    return {
        "last_updated": last_updated,
        "source_entity": source_entity,
        "source_state": state.state,
        "source_last_updated_iso": last_updated,
    }


def _parse_datetime_state(raw_state: str) -> Any:
    """Parse a Home Assistant datetime/date state."""
    parsed = dt_util.parse_datetime(raw_state)
    if parsed is not None:
        return parsed

    parsed_date = dt_util.parse_date(raw_state)
    if parsed_date is not None:
        return dt_util.start_of_local_day(parsed_date)

    return None


def _batch_start_source(coordinator: BrewAssistantCoordinator) -> tuple[str, Any | None]:
    """Return the best available batch start source state.

    Prefer Brewfather fermentation start for Brewfather-backed batches.
    Fall back to the manual BrewAssistant helper.
    """
    for entity_id in (BREWFATHER_FERMENTATION_START_ENTITY, BATCH_STARTED_AT_ENTITY):
        state = coordinator.hass.states.get(entity_id)
        if state is not None and state.state not in {"unknown", "unavailable", "none", ""}:
            return entity_id, state
    return BREWFATHER_FERMENTATION_START_ENTITY, None


def _parse_batch_started_at(coordinator: BrewAssistantCoordinator) -> dict[str, Any]:
    """Return parsed batch start metadata from Brewfather or manual fallback."""
    source_entity, state = _batch_start_source(coordinator)
    if state is None:
        return {
            "started_at": None,
            "source_entity": source_entity,
            "source_state": None,
            "started_at_iso": None,
            "age_hours": None,
            "age_days": None,
            "source_priority": "brewfather_then_manual",
        }

    parsed = _parse_datetime_state(state.state)
    if parsed is None:
        return {
            "started_at": None,
            "source_entity": source_entity,
            "source_state": state.state,
            "started_at_iso": None,
            "age_hours": None,
            "age_days": None,
            "source_priority": "brewfather_then_manual",
        }

    started_at = dt_util.as_utc(parsed)
    now = dt_util.utcnow()
    age_seconds = max(0.0, (now - started_at).total_seconds())
    age_hours = round(age_seconds / 3600, 1)
    age_days = round(age_seconds / 86400, 2)

    return {
        "started_at": started_at.isoformat(),
        "source_entity": source_entity,
        "source_state": state.state,
        "started_at_iso": started_at.isoformat(),
        "age_hours": age_hours,
        "age_days": age_days,
        "source_priority": "brewfather_then_manual",
    }


SENSORS: tuple[BrewAssistantSensorDescription, ...] = (
    BrewAssistantSensorDescription(
        key="liquid_temperature",
        translation_key="liquid_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.liquid_temperature,
        extra_attributes_fn=_liquid_attrs,
    ),
    BrewAssistantSensorDescription(
        key="liquid_temperature_source",
        translation_key="liquid_temperature_source",
        value_fn=lambda data: data.liquid_temperature_source,
        extra_attributes_fn=_source_attrs,
    ),
    BrewAssistantSensorDescription(
        key="chamber_temperature",
        translation_key="chamber_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.chamber_temperature,
    ),
    BrewAssistantSensorDescription(
        key="recipe_target_temperature",
        translation_key="recipe_target_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.recipe_target_temperature,
        extra_attributes_fn=_target_attrs,
    ),
    BrewAssistantSensorDescription(
        key="temperature_delta",
        translation_key="temperature_delta",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.temperature_delta,
    ),
    BrewAssistantSensorDescription(
        key="temperature_target_mode",
        translation_key="temperature_target_mode",
        value_fn=lambda data: data.temperature_target_mode,
        extra_attributes_fn=_target_attrs,
    ),
    BrewAssistantSensorDescription(
        key="temperature_status",
        translation_key="temperature_status",
        value_fn=lambda data: data.temperature_status,
        extra_attributes_fn=_status_attrs,
    ),
    BrewAssistantSensorDescription(
        key="temperature_severity",
        translation_key="temperature_severity",
        value_fn=lambda data: data.temperature_severity,
        extra_attributes_fn=_status_attrs,
    ),
    BrewAssistantSensorDescription(
        key="source_summary",
        translation_key="source_summary",
        value_fn=lambda data: data.source_summary,
    ),
    BrewAssistantSensorDescription(
        key="status_summary",
        translation_key="status_summary",
        value_fn=lambda data: data.status_summary,
        extra_attributes_fn=_status_attrs,
    ),
    BrewAssistantSensorDescription(
        key="problem_level",
        translation_key="problem_level",
        value_fn=lambda data: data.problem_level,
        extra_attributes_fn=_status_attrs,
    ),
    BrewAssistantSensorDescription(
        key="process_status",
        translation_key="process_status",
        value_fn=lambda data: data.process_status,
        extra_attributes_fn=_process_attrs,
    ),
    BrewAssistantSensorDescription(
        key="process_next_step",
        translation_key="process_next_step",
        value_fn=lambda data: data.process_next_step,
        extra_attributes_fn=_process_attrs,
    ),
    BrewAssistantSensorDescription(
        key="process_current_action_stage",
        translation_key="process_current_action_stage",
        value_fn=lambda data: data.process_current_action_stage,
        extra_attributes_fn=_process_attrs,
    ),
    BrewAssistantSensorDescription(
        key="process_next_action_stage",
        translation_key="process_next_action_stage",
        value_fn=lambda data: data.process_next_action_stage,
        extra_attributes_fn=_process_attrs,
    ),
    BrewAssistantSensorDescription(
        key="process_summary",
        translation_key="process_summary",
        value_fn=lambda data: data.process_summary,
        extra_attributes_fn=_process_attrs,
    ),
    BrewAssistantSensorDescription(
        key="gravity",
        translation_key="gravity",
        native_unit_of_measurement="SG",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.gravity,
    ),
)


SMART_SENSORS: tuple[BrewAssistantSmartSensorDescription, ...] = (
    BrewAssistantSmartSensorDescription(
        key="smart_recommendation_summary",
        translation_key="smart_recommendation_summary",
        value_fn=lambda smart: smart.summary,
    ),
    BrewAssistantSmartSensorDescription(
        key="smart_heat_recommendation",
        translation_key="smart_heat_recommendation",
        value_fn=lambda smart: smart.heat,
    ),
    BrewAssistantSmartSensorDescription(
        key="smart_cooling_recommendation",
        translation_key="smart_cooling_recommendation",
        value_fn=lambda smart: smart.cooling,
    ),
    BrewAssistantSmartSensorDescription(
        key="smart_fan_recommendation",
        translation_key="smart_fan_recommendation",
        value_fn=lambda smart: smart.fan,
    ),
    BrewAssistantSmartSensorDescription(
        key="smart_heat_block_reason_core",
        translation_key="smart_heat_block_reason_core",
        value_fn=lambda smart: smart.block_reason,
    ),
    BrewAssistantSmartSensorDescription(
        key="smart_suggested_heat_pulse_minutes",
        translation_key="smart_suggested_heat_pulse_minutes",
        native_unit_of_measurement="min",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda smart: smart.suggested_pulse_minutes,
    ),
    BrewAssistantSmartSensorDescription(
        key="smart_recommendation_mode",
        translation_key="smart_recommendation_mode",
        value_fn=lambda smart: smart.mode,
    ),
    BrewAssistantSmartSensorDescription(
        key="smart_pill_status_core",
        translation_key="smart_pill_status_core",
        value_fn=lambda smart: smart.pill_status,
    ),
    BrewAssistantSmartSensorDescription(
        key="smart_pill_temp_age_minutes_core",
        translation_key="smart_pill_temp_age_minutes_core",
        native_unit_of_measurement="min",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda smart: smart.pill_age_minutes,
    ),
)

SOURCE_SENSORS = {
    "source_health_summary": lambda coordinator: _source_health(coordinator)["summary"],
    "source_health_level": lambda coordinator: _source_health(coordinator)["level"],
    "gravity_last_updated": lambda coordinator: _gravity_last_updated(coordinator)["last_updated"],
    "batch_started_at": lambda coordinator: _parse_batch_started_at(coordinator)["started_at"],
    "batch_age_hours": lambda coordinator: _parse_batch_started_at(coordinator)["age_hours"],
    "batch_age_days": lambda coordinator: _parse_batch_started_at(coordinator)["age_days"],
    **{
        sensor_key: (lambda coordinator, source_key=source_key: coordinator.configured_entities[source_key])
        for sensor_key, source_key in SOURCE_SENSOR_KEYS.items()
    },
}

RUNTIME_SENSORS = {
    "runtime_recipe_name": lambda coordinator: _runtime_snapshot(coordinator)["recipe_name"],
    "runtime_status": lambda coordinator: _runtime_snapshot(coordinator)["status"],
    "runtime_primary_target_temperature": lambda coordinator: _runtime_snapshot(coordinator)["primary_target_temperature"],
    "runtime_cold_crash_target_temperature": lambda coordinator: _runtime_snapshot(coordinator)["cold_crash_target_temperature"],
    "runtime_target_fg": lambda coordinator: _runtime_snapshot(coordinator)["target_fg"],
    "runtime_source_status": lambda coordinator: _runtime_snapshot(coordinator)["source_status"],
}

CARBONATION_SENSORS = {
    "carbonation_status": "status",
    "carbonation_method": "method",
    "carbonation_target_volumes": "target_volumes",
    "carbonation_temperature": "temperature",
    "carbonation_recommended_pressure_bar": "recommended_pressure_bar",
    "carbonation_recommended_pressure_psi": "recommended_pressure_psi",
    "carbonation_actual_pressure_bar": "actual_pressure_bar",
    "carbonation_actual_pressure_psi": "actual_pressure_psi",
    "carbonation_equilibrium_volumes": "equilibrium_volumes",
    "carbonation_estimated_volumes": "estimated_volumes",
    "carbonation_progress_percent": "progress_percent",
    "carbonation_started_at": "started_at",
    "carbonation_age_days": "age_days",
    "carbonation_summary": "summary",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BrewAssistant sensors."""
    coordinator: BrewAssistantCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [BrewAssistantSensor(coordinator, description) for description in SENSORS]
        + [BrewAssistantSmartSensor(coordinator, description) for description in SMART_SENSORS]
        + [BrewAssistantSourceSensor(coordinator, key) for key in SOURCE_SENSORS]
        + [BrewAssistantRuntimeSensor(coordinator, key) for key in RUNTIME_SENSORS]
        + [BrewAssistantCarbonationSensor(coordinator, key) for key in CARBONATION_SENSORS]
        + create_brewday_runtime_sensors(coordinator)
        + [BrewAssistantCoreVersionSensor(coordinator)]
        + [BrewAssistantNextActionSensor(coordinator)]
    )


class BrewAssistantSensor(BrewAssistantEntity, SensorEntity):
    """BrewAssistant sensor entity."""

    entity_description: BrewAssistantSensorDescription

    def __init__(
        self,
        coordinator: BrewAssistantCoordinator,
        description: BrewAssistantSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        """Return the native sensor value."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional sensor attributes."""
        if self.entity_description.extra_attributes_fn is None:
            return None
        return self.entity_description.extra_attributes_fn(self.coordinator)


class BrewAssistantSmartSensor(BrewAssistantEntity, SensorEntity):
    """Read-only smart recommendation sensor entity."""

    entity_description: BrewAssistantSmartSensorDescription
    _attr_has_entity_name = False

    def __init__(
        self,
        coordinator: BrewAssistantCoordinator,
        description: BrewAssistantSmartSensorDescription,
    ) -> None:
        """Initialize the smart recommendation sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description
        self._attr_name = _display_name_from_key(description.key)
        self._attr_suggested_object_id = f"{DOMAIN}_{description.key}"

    @property
    def native_value(self) -> Any:
        """Return the smart recommendation value."""
        smart = _smart_data(self.coordinator)
        if smart is None:
            return None
        return self.entity_description.value_fn(smart)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return smart recommendation attributes."""
        return _smart_attrs(_smart_data(self.coordinator))


class BrewAssistantSourceSensor(BrewAssistantEntity, SensorEntity):
    """Read-only source health/configuration sensor."""

    _attr_has_entity_name = False

    def __init__(self, coordinator: BrewAssistantCoordinator, key: str) -> None:
        """Initialize the source sensor."""
        super().__init__(coordinator, key)
        self._key = key
        self._attr_name = _display_name_from_key(key)
        self._attr_suggested_object_id = f"{DOMAIN}_{key}"
        if key == "batch_age_hours":
            self._attr_native_unit_of_measurement = "h"
            self._attr_state_class = SensorStateClass.MEASUREMENT
        if key == "batch_age_days":
            self._attr_native_unit_of_measurement = "d"
            self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> Any:
        """Return source sensor value."""
        return SOURCE_SENSORS[self._key](self.coordinator)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return source health attributes."""
        if self._key == "gravity_last_updated":
            return _gravity_last_updated(self.coordinator)
        if self._key in {"batch_started_at", "batch_age_hours", "batch_age_days"}:
            return _parse_batch_started_at(self.coordinator)
        if self._key not in {"source_health_summary", "source_health_level"}:
            return None
        return source_health_attrs(_source_health(self.coordinator))


class BrewAssistantRuntimeSensor(BrewAssistantEntity, SensorEntity):
    """Read-only runtime normalization sensor."""

    _attr_has_entity_name = False

    def __init__(self, coordinator: BrewAssistantCoordinator, key: str) -> None:
        """Initialize the runtime sensor."""
        super().__init__(coordinator, key)
        self._key = key
        self._attr_name = _display_name_from_key(key)
        self._attr_suggested_object_id = f"{DOMAIN}_{key}"
        if key in {"runtime_primary_target_temperature", "runtime_cold_crash_target_temperature"}:
            self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
            self._attr_state_class = SensorStateClass.MEASUREMENT
        if key == "runtime_target_fg":
            self._attr_native_unit_of_measurement = "SG"
            self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> Any:
        """Return runtime sensor value."""
        return RUNTIME_SENSORS[self._key](self.coordinator)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return runtime attributes."""
        if self._key not in {"runtime_source_status", "runtime_recipe_name", "runtime_status"}:
            return None
        return runtime_attrs(_runtime_snapshot(self.coordinator))


class BrewAssistantCarbonationSensor(BrewAssistantEntity, SensorEntity):
    """Read-only carbonation sensor."""

    _attr_has_entity_name = False

    def __init__(self, coordinator: BrewAssistantCoordinator, key: str) -> None:
        """Initialize the carbonation sensor."""
        super().__init__(coordinator, key)
        self._key = key
        self._snapshot_key = CARBONATION_SENSORS[key]
        self._attr_name = _display_name_from_key(key)
        self._attr_suggested_object_id = f"{DOMAIN}_{key}"
        if key == "carbonation_temperature":
            self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
            self._attr_state_class = SensorStateClass.MEASUREMENT
        if key in {"carbonation_recommended_pressure_bar", "carbonation_actual_pressure_bar"}:
            self._attr_native_unit_of_measurement = "bar"
            self._attr_state_class = SensorStateClass.MEASUREMENT
        if key in {"carbonation_recommended_pressure_psi", "carbonation_actual_pressure_psi"}:
            self._attr_native_unit_of_measurement = "psi"
            self._attr_state_class = SensorStateClass.MEASUREMENT
        if key in {
            "carbonation_target_volumes",
            "carbonation_equilibrium_volumes",
            "carbonation_estimated_volumes",
        }:
            self._attr_native_unit_of_measurement = "vol"
            self._attr_state_class = SensorStateClass.MEASUREMENT
        if key == "carbonation_progress_percent":
            self._attr_native_unit_of_measurement = "%"
            self._attr_state_class = SensorStateClass.MEASUREMENT
        if key == "carbonation_age_days":
            self._attr_native_unit_of_measurement = "d"
            self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> Any:
        """Return carbonation sensor value."""
        return build_carbonation_snapshot(self.coordinator.hass).get(self._snapshot_key)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return carbonation diagnostic attributes."""
        return build_carbonation_snapshot(self.coordinator.hass)


class BrewAssistantCoreVersionSensor(BrewAssistantEntity, SensorEntity):
    """BrewAssistant Core version sensor."""

    _attr_has_entity_name = False

    def __init__(self, coordinator: BrewAssistantCoordinator) -> None:
        """Initialize the core version sensor."""
        super().__init__(coordinator, "core_version")
        self._attr_name = "BrewAssistant Core Version"
        self._attr_suggested_object_id = f"{DOMAIN}_core_version"

    @property
    def native_value(self) -> str:
        """Return BrewAssistant Core version."""
        return VERSION

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return core milestone attributes."""
        return {
            "milestone": "Read-only Core Stable",
            "hardware_control": False,
            "safe_mode": "read_only",
            "notes": "No climate, switch, fan or heater control is performed by Python Core.",
        }


class BrewAssistantNextActionSensor(BrewAssistantEntity, SensorEntity):
    """Read-only next recommended action sensor."""

    _attr_has_entity_name = False

    def __init__(self, coordinator: BrewAssistantCoordinator) -> None:
        """Initialize the next action sensor."""
        super().__init__(coordinator, "next_recommended_action")
        self._attr_name = "BrewAssistant Next Recommended Action"
        self._attr_suggested_object_id = f"{DOMAIN}_next_recommended_action"

    @property
    def native_value(self) -> Any:
        """Return next recommended action."""
        return _next_action(self.coordinator)["action"]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return next action attributes."""
        return _next_action(self.coordinator)
