"""Read-only Home Assistant sensors for the GF30 fermenter backend."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.util import dt as dt_util

from ..const import (
    CONF_GF30_COOLANT_TEMP_ENTITY,
    CONF_GF30_COOLANT_THERMOSTAT_ENTITY,
    CONF_GF30_FREEZER_AIR_TEMP_ENTITY,
    CONF_LIQUID_TEMP_ENTITY,
)
from ..entity import BrewAssistantEntity
from .adapter import build_grainfather_fermenter_snapshot
from .coolant import build_coolant_monitor_snapshot
from .preflight_runtime import build_gf30_preflight_runtime_snapshot
from .thermal import build_dual_sensor_snapshot

if TYPE_CHECKING:
    from ..coordinator import BrewAssistantCoordinator


@dataclass(frozen=True)
class GF30SensorSpec:
    """Describe one GF30 diagnostic sensor."""

    key: str
    snapshot: str
    field: str
    unit: str | None = None
    device_class: SensorDeviceClass | None = None
    state_class: SensorStateClass | None = None


SPECS: tuple[GF30SensorSpec, ...] = (
    GF30SensorSpec(
        key="gf30_backend_status",
        snapshot="cloud",
        field="status",
    ),
    GF30SensorSpec(
        key="gf30_controller_temperature",
        snapshot="cloud",
        field="temperature",
        unit=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GF30SensorSpec(
        key="gf30_controller_gravity",
        snapshot="cloud",
        field="gravity",
        unit="SG",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GF30SensorSpec(
        key="gf30_preflight_status",
        snapshot="preflight",
        field="status",
    ),
    GF30SensorSpec(
        key="gf30_preflight_pill_temperature",
        snapshot="preflight",
        field="pill.temperature_c",
        unit=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GF30SensorSpec(
        key="gf30_preflight_manual_temperature",
        snapshot="preflight",
        field="manual_reference.temperature_c",
        unit=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GF30SensorSpec(
        key="gf30_preflight_temperature_delta",
        snapshot="preflight",
        field="temperature_delta_c",
        unit=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GF30SensorSpec(
        key="gf30_preflight_observation_count",
        snapshot="preflight",
        field="observation_count",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GF30SensorSpec(
        key="gf30_preflight_eligible_sample_count",
        snapshot="preflight",
        field="eligible_sample_count",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GF30SensorSpec(
        key="gf30_preflight_mean_absolute_delta",
        snapshot="preflight",
        field="mean_absolute_temperature_delta_c",
        unit=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GF30SensorSpec(
        key="gf30_preflight_learning_confidence",
        snapshot="preflight",
        field="learning_confidence",
    ),
    GF30SensorSpec(
        key="gf30_preflight_pill_rate",
        snapshot="preflight",
        field="latest_pill_rate_c_per_hour",
        unit="°C/h",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GF30SensorSpec(
        key="gf30_preflight_mean_cooling_rate",
        snapshot="preflight",
        field="mean_cooling_rate_c_per_hour",
        unit="°C/h",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GF30SensorSpec(
        key="gf30_dual_sensor_status",
        snapshot="dual",
        field="status",
    ),
    GF30SensorSpec(
        key="gf30_dual_sensor_temperature_delta",
        snapshot="dual",
        field="temperature_delta_c",
        unit=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GF30SensorSpec(
        key="gf30_safe_point",
        snapshot="dual",
        field="safe_point",
    ),
    GF30SensorSpec(
        key="gf30_coolant_status",
        snapshot="coolant",
        field="status",
    ),
    GF30SensorSpec(
        key="gf30_coolant_temperature",
        snapshot="coolant",
        field="coolant.temperature_c",
        unit=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GF30SensorSpec(
        key="gf30_freezer_air_temperature",
        snapshot="coolant",
        field="freezer_air.temperature_c",
        unit=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GF30SensorSpec(
        key="gf30_freezer_air_minus_coolant",
        snapshot="coolant",
        field="freezer_air_minus_coolant_c",
        unit=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GF30SensorSpec(
        key="gf30_coolant_thermostat_target",
        snapshot="coolant",
        field="thermostat.target_temperature_c",
        unit=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


def _nested(snapshot: dict[str, Any], field: str) -> Any:
    """Resolve a dotted field path from a snapshot."""
    value: Any = snapshot
    for part in field.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def _dual_snapshot(coordinator: BrewAssistantCoordinator) -> dict[str, Any]:
    """Build current Pill + Grainfather-controller comparison diagnostics."""
    cloud = build_grainfather_fermenter_snapshot(coordinator.hass)
    pill_entity = coordinator.configured_entities.get(CONF_LIQUID_TEMP_ENTITY)
    pill_state = coordinator.hass.states.get(pill_entity) if pill_entity else None
    internal_entity = cloud.get("temperature_entity")
    internal_state = (
        coordinator.hass.states.get(internal_entity) if internal_entity else None
    )
    selected_device = cloud.get("selected_device") or {}
    internal_observed_at = None
    last_heard = selected_device.get("last_heard") if isinstance(selected_device, dict) else None
    if last_heard:
        parsed_last_heard = dt_util.parse_datetime(str(last_heard))
        if parsed_last_heard is not None:
            internal_observed_at = dt_util.as_utc(parsed_last_heard)
    if internal_observed_at is None and internal_state is not None:
        internal_observed_at = internal_state.last_updated

    def _float_state(state) -> float | None:
        if state is None or str(state.state).strip().lower() in {
            "unknown",
            "unavailable",
            "none",
            "",
        }:
            return None
        try:
            return float(str(state.state).replace(",", "."))
        except (TypeError, ValueError):
            return None

    snapshot = build_dual_sensor_snapshot(
        pill_temperature_c=_float_state(pill_state),
        internal_temperature_c=_float_state(internal_state),
        pill_observed_at=pill_state.last_updated if pill_state is not None else None,
        internal_observed_at=internal_observed_at,
    )
    snapshot.update(
        {
            "pill_entity": pill_entity,
            "internal_entity": internal_entity,
            "grainfather_model_verified": cloud.get("model_verified"),
            "grainfather_selection_reason": cloud.get("selection_reason"),
            "grainfather_controller_linked": cloud.get("controller_linked"),
        }
    )
    return snapshot


def _coolant_snapshot(coordinator: BrewAssistantCoordinator) -> dict[str, Any]:
    """Build current configured coolant/freezer monitoring diagnostics."""
    hass = coordinator.hass
    coolant_entity = coordinator.configured_entities.get(CONF_GF30_COOLANT_TEMP_ENTITY)
    freezer_air_entity = coordinator.configured_entities.get(
        CONF_GF30_FREEZER_AIR_TEMP_ENTITY
    )
    thermostat_entity = coordinator.configured_entities.get(
        CONF_GF30_COOLANT_THERMOSTAT_ENTITY
    )

    coolant_state = hass.states.get(coolant_entity) if coolant_entity else None
    freezer_air_state = (
        hass.states.get(freezer_air_entity) if freezer_air_entity else None
    )
    thermostat_state = (
        hass.states.get(thermostat_entity) if thermostat_entity else None
    )

    snapshot = build_coolant_monitor_snapshot(
        coolant_temperature_c=coolant_state.state if coolant_state is not None else None,
        coolant_observed_at=(
            coolant_state.last_updated if coolant_state is not None else None
        ),
        freezer_air_temperature_c=(
            freezer_air_state.state if freezer_air_state is not None else None
        ),
        freezer_air_observed_at=(
            freezer_air_state.last_updated if freezer_air_state is not None else None
        ),
        thermostat_state=thermostat_state.state if thermostat_state is not None else None,
        thermostat_target_c=(
            thermostat_state.attributes.get("temperature")
            if thermostat_state is not None
            else None
        ),
        thermostat_hvac_action=(
            thermostat_state.attributes.get("hvac_action")
            if thermostat_state is not None
            else None
        ),
    )
    snapshot.update(
        {
            "coolant_entity": coolant_entity or None,
            "freezer_air_entity": freezer_air_entity or None,
            "thermostat_entity": thermostat_entity or None,
        }
    )
    return snapshot


class BrewAssistantGF30Sensor(BrewAssistantEntity, SensorEntity):
    """One read-only GF30 backend diagnostic sensor."""

    _attr_has_entity_name = False

    def __init__(
        self,
        coordinator: BrewAssistantCoordinator,
        spec: GF30SensorSpec,
    ) -> None:
        super().__init__(coordinator, spec.key)
        self._spec = spec
        self._attr_name = f"BrewAssistant {spec.key.replace('_', ' ').title()}"
        self._attr_suggested_object_id = f"brewassistant_{spec.key}"
        self._attr_native_unit_of_measurement = spec.unit
        self._attr_device_class = spec.device_class
        self._attr_state_class = spec.state_class

    def _snapshot(self) -> dict[str, Any]:
        if self._spec.snapshot == "cloud":
            return build_grainfather_fermenter_snapshot(self.coordinator.hass)
        if self._spec.snapshot == "dual":
            return _dual_snapshot(self.coordinator)
        if self._spec.snapshot == "coolant":
            return _coolant_snapshot(self.coordinator)
        return build_gf30_preflight_runtime_snapshot(self.coordinator.hass)

    @property
    def native_value(self) -> Any:
        """Return one field from the current GF30 snapshot."""
        return _nested(self._snapshot(), self._spec.field)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the complete diagnostic snapshot for troubleshooting."""
        snapshot = self._snapshot()
        if self._spec.snapshot == "cloud":
            return {
                "source": snapshot.get("source"),
                "reason": snapshot.get("reason"),
                "control_mode": snapshot.get("control_mode"),
                "model_verified": snapshot.get("model_verified"),
                "selection_reason": snapshot.get("selection_reason"),
                "temperature_entity": snapshot.get("temperature_entity"),
                "gravity_entity": snapshot.get("gravity_entity"),
                "controller_linked": snapshot.get("controller_linked"),
                "profile_target_service_available": snapshot.get(
                    "profile_target_service_available"
                ),
                "future_supervised_target_ready": snapshot.get(
                    "future_supervised_target_ready"
                ),
                "selected_device": snapshot.get("selected_device"),
                "linked_session": snapshot.get("linked_session"),
            }
        if self._spec.snapshot == "dual":
            return snapshot
        return snapshot


def create_grainfather_fermenter_sensors(
    coordinator: BrewAssistantCoordinator,
) -> list[SensorEntity]:
    """Create the read-only GF30 backend sensors."""
    return [BrewAssistantGF30Sensor(coordinator, spec) for spec in SPECS]
