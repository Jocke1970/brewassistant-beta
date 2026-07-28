"""Read-only sensors for the independent fermentation tracking backend."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import PERCENTAGE, UnitOfTemperature

from ..const import CONF_GRAVITY_ENTITY, CONF_LIQUID_TEMP_ENTITY, DOMAIN
from ..coordinator import BrewAssistantCoordinator
from ..entity import BrewAssistantEntity
from .snapshot import build_fermentation_snapshot

INVALID_STATES = {"unknown", "unavailable", "none", ""}


@dataclass(frozen=True, kw_only=True)
class FermentationTrackingSensorConfig:
    """Describe one fermentation tracking sensor."""

    key: str
    name: str
    snapshot_key: str
    icon: str
    unit: str | None = None
    device_class: SensorDeviceClass | None = None
    state_class: SensorStateClass | None = None


def _external_numeric(
    coordinator: BrewAssistantCoordinator,
    config_key: str,
) -> tuple[float | None, Any, str | None]:
    entity_id = coordinator.configured_entities.get(config_key)
    state = coordinator.hass.states.get(entity_id) if entity_id else None
    if state is None or str(state.state).lower() in INVALID_STATES:
        return None, None, entity_id
    try:
        value = float(str(state.state).replace(",", "."))
    except (TypeError, ValueError):
        return None, None, entity_id
    return value, state.last_updated, entity_id


def build_tracking_sensor_snapshot(coordinator: BrewAssistantCoordinator) -> dict[str, Any]:
    """Build tracking with independently resolved automatic SG and temperature."""
    external_sg, gravity_updated_at, gravity_entity = _external_numeric(
        coordinator,
        CONF_GRAVITY_ENTITY,
    )
    external_temperature, temperature_updated_at, temperature_entity = _external_numeric(
        coordinator,
        CONF_LIQUID_TEMP_ENTITY,
    )
    return build_fermentation_snapshot(
        coordinator.hass,
        external_sg=external_sg,
        external_updated_at=gravity_updated_at,
        external_entity=gravity_entity,
        external_temperature_c=external_temperature,
        external_temperature_updated_at=temperature_updated_at,
        external_temperature_entity=temperature_entity,
    )


SENSORS: tuple[FermentationTrackingSensorConfig, ...] = (
    FermentationTrackingSensorConfig(
        key="fermentation_tracking_status",
        name="BrewAssistant Fermentation Tracking Status",
        snapshot_key="status",
        icon="mdi:progress-check",
    ),
    FermentationTrackingSensorConfig(
        key="fermentation_current_sg",
        name="BrewAssistant Fermentation Current SG",
        snapshot_key="current_sg",
        icon="mdi:hydrometer",
        unit="SG",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FermentationTrackingSensorConfig(
        key="fermentation_gravity_source",
        name="BrewAssistant Fermentation Gravity Source",
        snapshot_key="gravity_source",
        icon="mdi:source-branch",
    ),
    FermentationTrackingSensorConfig(
        key="fermentation_gravity_source_type",
        name="BrewAssistant Fermentation Gravity Source Type",
        snapshot_key="gravity_source_type",
        icon="mdi:account-switch-outline",
    ),
    FermentationTrackingSensorConfig(
        key="fermentation_gravity_source_mode",
        name="BrewAssistant Fermentation Gravity Source Mode",
        snapshot_key="gravity_source_mode",
        icon="mdi:tune-variant",
    ),
    FermentationTrackingSensorConfig(
        key="fermentation_current_temperature",
        name="BrewAssistant Fermentation Current Temperature",
        snapshot_key="current_temperature_c",
        icon="mdi:thermometer",
        unit=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FermentationTrackingSensorConfig(
        key="fermentation_temperature_source",
        name="BrewAssistant Fermentation Temperature Source",
        snapshot_key="temperature_source",
        icon="mdi:source-branch",
    ),
    FermentationTrackingSensorConfig(
        key="fermentation_temperature_source_type",
        name="BrewAssistant Fermentation Temperature Source Type",
        snapshot_key="temperature_source_type",
        icon="mdi:account-switch-outline",
    ),
    FermentationTrackingSensorConfig(
        key="fermentation_temperature_source_mode",
        name="BrewAssistant Fermentation Temperature Source Mode",
        snapshot_key="temperature_source_mode",
        icon="mdi:tune-variant",
    ),
    FermentationTrackingSensorConfig(
        key="fermentation_progress_percent",
        name="BrewAssistant Fermentation Progress",
        snapshot_key="progress_percent",
        icon="mdi:progress-clock",
        unit=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FermentationTrackingSensorConfig(
        key="fermentation_estimated_abv",
        name="BrewAssistant Fermentation Estimated ABV",
        snapshot_key="estimated_abv",
        icon="mdi:percent-outline",
        unit=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FermentationTrackingSensorConfig(
        key="fermentation_gravity_stability",
        name="BrewAssistant Fermentation Gravity Stability",
        snapshot_key="gravity_stability_state",
        icon="mdi:chart-bell-curve-cumulative",
    ),
    FermentationTrackingSensorConfig(
        key="fermentation_ready_for_temp_rise",
        name="BrewAssistant Fermentation Ready For Temp Rise",
        snapshot_key="temp_rise_readiness_state",
        icon="mdi:thermometer-chevron-up",
    ),
    FermentationTrackingSensorConfig(
        key="fermentation_ready_for_cold_crash",
        name="BrewAssistant Fermentation Ready For Cold Crash",
        snapshot_key="cold_crash_readiness_state",
        icon="mdi:snowflake-check",
    ),
    FermentationTrackingSensorConfig(
        key="fermentation_sample_count",
        name="BrewAssistant Fermentation Gravity Observation Count",
        snapshot_key="sample_count",
        icon="mdi:counter",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FermentationTrackingSensorConfig(
        key="fermentation_temperature_observation_count",
        name="BrewAssistant Fermentation Temperature Observation Count",
        snapshot_key="temperature_observation_count",
        icon="mdi:counter",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FermentationTrackingSensorConfig(
        key="fermentation_last_observation",
        name="BrewAssistant Fermentation Last Gravity Observation",
        snapshot_key="gravity_observed_at",
        icon="mdi:clock-check-outline",
    ),
    FermentationTrackingSensorConfig(
        key="fermentation_recommended_temperature",
        name="BrewAssistant Fermentation Recommended Temperature",
        snapshot_key="recommended_temperature_c",
        icon="mdi:thermometer-auto",
        unit=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FermentationTrackingSensorConfig(
        key="fermentation_tracking_summary",
        name="BrewAssistant Fermentation Tracking Summary",
        snapshot_key="summary",
        icon="mdi:text-box-check-outline",
    ),
)


class BrewAssistantFermentationTrackingSensor(BrewAssistantEntity, SensorEntity):
    """Read-only fermentation tracking sensor."""

    _attr_has_entity_name = False

    def __init__(
        self,
        coordinator: BrewAssistantCoordinator,
        config: FermentationTrackingSensorConfig,
    ) -> None:
        super().__init__(coordinator, config.key)
        self._config = config
        self._attr_name = config.name
        self._attr_suggested_object_id = f"{DOMAIN}_{config.key}"
        self._attr_icon = config.icon
        self._attr_native_unit_of_measurement = config.unit
        self._attr_device_class = config.device_class
        self._attr_state_class = config.state_class

    @property
    def native_value(self) -> Any:
        return build_tracking_sensor_snapshot(self.coordinator).get(self._config.snapshot_key)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return build_tracking_sensor_snapshot(self.coordinator)


def create_fermentation_tracking_sensors(
    coordinator: BrewAssistantCoordinator,
) -> list[BrewAssistantFermentationTrackingSensor]:
    """Create independent fermentation tracking sensors."""
    return [BrewAssistantFermentationTrackingSensor(coordinator, config) for config in SENSORS]
