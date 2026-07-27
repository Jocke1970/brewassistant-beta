"""Read-only sensor entities for Python-owned fermentation tracking."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import PERCENTAGE, UnitOfTemperature

from ..const import CONF_GRAVITY_ENTITY, DOMAIN
from ..coordinator import BrewAssistantCoordinator
from ..entity import BrewAssistantEntity
from .fermentation_runtime import build_fermentation_snapshot

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


def _external_gravity(coordinator: BrewAssistantCoordinator) -> tuple[float | None, Any, str | None]:
    entity_id = coordinator.configured_entities.get(CONF_GRAVITY_ENTITY)
    state = coordinator.hass.states.get(entity_id) if entity_id else None
    if state is None or str(state.state).lower() in INVALID_STATES:
        return None, None, entity_id
    try:
        value = float(str(state.state).replace(",", "."))
    except (TypeError, ValueError):
        return None, None, entity_id
    return value, state.last_updated, entity_id


def build_tracking_sensor_snapshot(coordinator: BrewAssistantCoordinator) -> dict[str, Any]:
    """Build fermentation tracking with the configured external SG source as fallback."""
    external_sg, external_updated_at, external_entity = _external_gravity(coordinator)
    return build_fermentation_snapshot(
        coordinator.hass,
        external_sg=external_sg,
        external_updated_at=external_updated_at,
        external_entity=external_entity,
    )


SENSORS: tuple[FermentationTrackingSensorConfig, ...] = (
    FermentationTrackingSensorConfig(
        key="fermentation_tracking_status",
        name="BrewAssistant Fermentation Tracking Status",
        snapshot_key="status",
        icon="mdi:progress-check",
    ),
    FermentationTrackingSensorConfig(
        key="fermentation_gravity_source",
        name="BrewAssistant Fermentation Gravity Source",
        snapshot_key="gravity_source",
        icon="mdi:source-branch",
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
        name="BrewAssistant Fermentation Sample Count",
        snapshot_key="sample_count",
        icon="mdi:counter",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FermentationTrackingSensorConfig(
        key="fermentation_last_observation",
        name="BrewAssistant Fermentation Last Observation",
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
    """Create the narrow MVP fermentation tracking sensors."""
    return [BrewAssistantFermentationTrackingSensor(coordinator, config) for config in SENSORS]
