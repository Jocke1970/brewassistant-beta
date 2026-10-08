"""Provider-neutral Brewfather Custom Stream telemetry from fermentation tracking.

BrewAssistant owns source selection and semantics only. The Brewfather
integration remains the sole HTTP transport owner.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature

from ..coordinator import BrewAssistantCoordinator
from ..entity import BrewAssistantEntity
from .models import PROVIDER_FERMENTATION_CHAMBER, PROVIDER_GRAINFATHER_GF30
from .sensor import build_tracking_sensor_snapshot

MAX_STREAM_SAMPLE_AGE_SECONDS = 20 * 60
CHAMBER_AUX_ENTITY = "sensor.brewassistant_fermentation_chamber_air_temperature_average"
GF30_AUX_ENTITY = "sensor.brewassistant_gf30_coolant_temperature"
INVALID_STATES = {"unknown", "unavailable", "none", ""}


@dataclass(frozen=True)
class BrewfatherStreamSensorSpec:
    key: str
    field: str
    unit: str | None = None
    device_class: SensorDeviceClass | None = None
    state_class: SensorStateClass | None = None
    observed_at_field: str | None = None


SPECS: tuple[BrewfatherStreamSensorSpec, ...] = (
    BrewfatherStreamSensorSpec(
        key="brewfather_stream_status",
        field="status",
    ),
    BrewfatherStreamSensorSpec(
        key="brewfather_stream_temperature",
        field="temperature_c",
        unit=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        observed_at_field="temperature_observed_at",
    ),
    BrewfatherStreamSensorSpec(
        key="brewfather_stream_gravity",
        field="gravity_sg",
        unit="SG",
        state_class=SensorStateClass.MEASUREMENT,
        observed_at_field="gravity_observed_at",
    ),
    BrewfatherStreamSensorSpec(
        key="brewfather_stream_temp_target",
        field="temp_target_c",
        unit=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    BrewfatherStreamSensorSpec(
        key="brewfather_stream_gravity_target",
        field="gravity_target_sg",
        unit="SG",
    ),
    BrewfatherStreamSensorSpec(
        key="brewfather_stream_aux_temperature",
        field="aux_temperature_c",
        unit=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        observed_at_field="aux_temperature_observed_at",
    ),
)


def _as_utc(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _age_seconds(value: Any, *, now: datetime) -> float | None:
    observed = _as_utc(value)
    if observed is None:
        return None
    return max(0.0, (now - observed).total_seconds())


def _fresh(value: Any, *, now: datetime) -> bool:
    age = _age_seconds(value, now=now)
    return age is not None and age <= MAX_STREAM_SAMPLE_AGE_SECONDS


def _state_numeric(
    coordinator: BrewAssistantCoordinator,
    entity_id: str,
    *,
    now: datetime,
) -> tuple[float | None, str | None, float | None]:
    state = coordinator.hass.states.get(entity_id)
    if state is None or str(state.state).lower() in INVALID_STATES:
        return None, None, None
    try:
        value = float(str(state.state).replace(",", "."))
    except (TypeError, ValueError):
        return None, None, None

    observed = (
        getattr(state, "last_reported", None)
        or getattr(state, "last_updated", None)
        or getattr(state, "last_changed", None)
    )
    observed_utc = _as_utc(observed)
    if observed_utc is None:
        return None, None, None
    age = _age_seconds(observed_utc, now=now)
    if age is None or age > MAX_STREAM_SAMPLE_AGE_SECONDS:
        return None, observed_utc.isoformat(), age
    return value, observed_utc.isoformat(), age


def build_brewfather_stream_snapshot(
    coordinator: BrewAssistantCoordinator,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build side-effect-free provider-neutral telemetry for Brewfather."""
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    tracking = build_tracking_sensor_snapshot(coordinator)
    active = tracking.get("active") is True
    provider = tracking.get("fermentation_provider")

    temperature_observed_at = tracking.get("temperature_observed_at")
    temperature_age = _age_seconds(temperature_observed_at, now=now)
    temperature_fresh = active and _fresh(temperature_observed_at, now=now)
    temperature = (
        tracking.get("current_temperature_c")
        if temperature_fresh
        else None
    )

    gravity_observed_at = tracking.get("gravity_observed_at")
    gravity_age = _age_seconds(gravity_observed_at, now=now)
    gravity_fresh = active and _fresh(gravity_observed_at, now=now)
    gravity = tracking.get("current_sg") if gravity_fresh else None

    aux_entity = None
    aux_semantics = None
    if provider == PROVIDER_FERMENTATION_CHAMBER:
        aux_entity = CHAMBER_AUX_ENTITY
        aux_semantics = "fridge_temp_chamber_air"
    elif provider == PROVIDER_GRAINFATHER_GF30:
        aux_entity = GF30_AUX_ENTITY
        aux_semantics = "fridge_temp_coolant_reservoir"

    aux_temperature = None
    aux_observed_at = None
    aux_age = None
    if active and aux_entity is not None:
        aux_temperature, aux_observed_at, aux_age = _state_numeric(
            coordinator,
            aux_entity,
            now=now,
        )

    eligible = active and temperature is not None
    if not active:
        status = "inactive"
        reason = "fermentation tracking inactive"
    elif temperature is None:
        status = "blocked_stale_temperature"
        reason = "fresh normalized beer temperature required"
    elif gravity is None:
        status = "ready_without_gravity"
        reason = "fresh beer temperature available; gravity omitted"
    else:
        status = "ready"
        reason = "fresh normalized fermentation telemetry available"

    return {
        "status": status,
        "eligible": eligible,
        "reason": reason,
        "provider_id": provider,
        "provider_label": tracking.get("fermentation_provider_label"),
        "temperature_c": temperature,
        "temperature_source": tracking.get("temperature_source"),
        "temperature_source_entity": tracking.get("temperature_source_entity"),
        "temperature_observed_at": temperature_observed_at,
        "temperature_age_seconds": round(temperature_age, 1)
        if temperature_age is not None
        else None,
        "temperature_fresh": temperature_fresh,
        "gravity_sg": gravity,
        "gravity_source": tracking.get("gravity_source"),
        "gravity_source_entity": tracking.get("gravity_source_entity"),
        "gravity_observed_at": gravity_observed_at,
        "gravity_age_seconds": round(gravity_age, 1)
        if gravity_age is not None
        else None,
        "gravity_fresh": gravity_fresh,
        "temp_target_c": tracking.get("recommended_temperature_c")
        if active
        else None,
        "temp_target_source": tracking.get("recommended_temperature_source"),
        "gravity_target_sg": tracking.get("target_final_gravity")
        if active
        else None,
        "aux_temperature_c": aux_temperature,
        "aux_temperature_entity": aux_entity,
        "aux_temperature_semantics": aux_semantics,
        "aux_temperature_observed_at": aux_observed_at,
        "aux_temperature_age_seconds": round(aux_age, 1)
        if aux_age is not None
        else None,
        "ext_temperature_c": None,
        "ext_temperature_semantics": "unmapped_room_temperature",
        "max_sample_age_seconds": MAX_STREAM_SAMPLE_AGE_SECONDS,
        "transport_owner": "brewfather_integration",
        "http_transport_in_brewassistant": False,
        "source": "brewassistant_fermentation_tracking",
    }


class BrewAssistantBrewfatherStreamSensor(BrewAssistantEntity, SensorEntity):
    """One stable Brewfather Custom Stream source entity."""

    _attr_has_entity_name = False

    def __init__(
        self,
        coordinator: BrewAssistantCoordinator,
        spec: BrewfatherStreamSensorSpec,
    ) -> None:
        super().__init__(coordinator, spec.key)
        self._spec = spec
        self._attr_name = f"BrewAssistant {spec.key.replace('_', ' ').title()}"
        self._attr_suggested_object_id = f"brewassistant_{spec.key}"
        self._attr_native_unit_of_measurement = spec.unit
        self._attr_device_class = spec.device_class
        self._attr_state_class = spec.state_class

    @property
    def native_value(self) -> Any:
        return build_brewfather_stream_snapshot(self.coordinator).get(self._spec.field)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        snapshot = build_brewfather_stream_snapshot(self.coordinator)
        attrs = dict(snapshot)
        if self._spec.observed_at_field is not None:
            attrs["brewfather_sample_observed_at"] = snapshot.get(
                self._spec.observed_at_field
            )
        return attrs


def create_brewfather_stream_sensors(
    coordinator: BrewAssistantCoordinator,
) -> list[SensorEntity]:
    """Create provider-neutral Brewfather telemetry sensors."""
    return [
        BrewAssistantBrewfatherStreamSensor(coordinator, spec)
        for spec in SPECS
    ]
