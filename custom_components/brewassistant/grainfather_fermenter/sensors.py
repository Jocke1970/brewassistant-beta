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

from ..entity import BrewAssistantEntity
from .adapter import build_grainfather_fermenter_snapshot
from .preflight_runtime import build_gf30_preflight_runtime_snapshot

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
)


def _nested(snapshot: dict[str, Any], field: str) -> Any:
    """Resolve a dotted field path from a snapshot."""
    value: Any = snapshot
    for part in field.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


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
        return snapshot


def create_grainfather_fermenter_sensors(
    coordinator: BrewAssistantCoordinator,
) -> list[SensorEntity]:
    """Create the read-only GF30 backend sensors."""
    return [BrewAssistantGF30Sensor(coordinator, spec) for spec in SPECS]
