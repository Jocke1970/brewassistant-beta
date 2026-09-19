"""Read-only sensors for the independent fermentation tracking backend."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import PERCENTAGE, UnitOfTemperature

from ..const import CONF_GRAVITY_ENTITY, CONF_LIQUID_TEMP_ENTITY, DOMAIN
from ..coordinator import BrewAssistantCoordinator
from ..entity import BrewAssistantEntity
from .recipe_schedule import build_recipe_temperature_schedule
from .snapshot import build_fermentation_snapshot

INVALID_STATES = {"unknown", "unavailable", "none", ""}
BREWFATHER_RECIPE_CANDIDATES = (
    "sensor.brewfather_brew_tracker_raw",
    "sensor.brewfather_brewtracker_raw",
)
BREWFATHER_FERMENTATION_START_CANDIDATES = (
    "sensor.brewfather_fermentation_start",
    "sensor.brewfather_fermentation_start_date",
    "sensor.brewfather_brewfather_fermentation_start",
)


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


def _timestamp_from_state(state: Any) -> datetime | None:
    if state is None or str(state.state).lower() in INVALID_STATES:
        return None
    try:
        value = datetime.fromisoformat(str(state.state).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _brewfather_recipe_schedule(
    coordinator: BrewAssistantCoordinator,
) -> tuple[float | None, str | None, str | None, dict[str, Any] | None]:
    """Interpret Brewfather's read-only recipe inside BrewAssistant.

    The Brewfather fork is intentionally only a data adapter: it exposes the full
    recipe on the BrewTracker raw sensor.  Temperature-step and ramp semantics are
    owned here by the BrewAssistant fermentation tracking backend.
    """
    recipe_state = None
    recipe_entity = None
    recipe: Mapping[str, Any] | None = None
    for entity_id in BREWFATHER_RECIPE_CANDIDATES:
        state = coordinator.hass.states.get(entity_id)
        candidate = state.attributes.get("recipe") if state is not None else None
        if isinstance(candidate, Mapping):
            recipe_state = state
            recipe_entity = entity_id
            recipe = candidate
            break

    if recipe_state is None or recipe is None:
        return None, None, None, None

    fermentation_started_at = None
    for entity_id in BREWFATHER_FERMENTATION_START_CANDIDATES:
        state = coordinator.hass.states.get(entity_id)
        fermentation_started_at = _timestamp_from_state(state)
        if fermentation_started_at is not None:
            break

    schedule = build_recipe_temperature_schedule(
        recipe,
        fermentation_started_at=fermentation_started_at,
        now=datetime.now(timezone.utc),
    )
    if schedule is None:
        return None, recipe_entity, None, None

    target = schedule.get("target_temperature_c")
    if target is None:
        return None, recipe_entity, None, schedule
    return float(target), recipe_entity, "brewfather_recipe_schedule", schedule


def build_tracking_sensor_snapshot(coordinator: BrewAssistantCoordinator) -> dict[str, Any]:
    """Build tracking with independently resolved SG, temperature, and recipe target."""
    external_sg, gravity_updated_at, gravity_entity = _external_numeric(
        coordinator,
        CONF_GRAVITY_ENTITY,
    )
    external_temperature, temperature_updated_at, temperature_entity = _external_numeric(
        coordinator,
        CONF_LIQUID_TEMP_ENTITY,
    )
    external_target, target_entity, target_source, target_schedule = _brewfather_recipe_schedule(
        coordinator
    )
    return build_fermentation_snapshot(
        coordinator.hass,
        external_sg=external_sg,
        external_updated_at=gravity_updated_at,
        external_entity=gravity_entity,
        external_temperature_c=external_temperature,
        external_temperature_updated_at=temperature_updated_at,
        external_temperature_entity=temperature_entity,
        external_target_temperature_c=external_target,
        external_target_temperature_entity=target_entity,
        external_target_source=target_source,
        external_target_metadata=target_schedule,
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
