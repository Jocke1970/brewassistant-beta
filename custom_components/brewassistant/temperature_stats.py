"""Rolling temperature statistics for BrewAssistant.

These sensors provide smoothed/rolling temperature context for the kegerator,
fermentation chamber air and fermentation liquid. The first version keeps data
in memory only and is intended for dashboard/UI context and later supervisor
logic damping.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import UnitOfTemperature
from homeassistant.util import dt as dt_util

from .const import CONF_CHAMBER_TEMP_ENTITY, DOMAIN
from .coordinator import BrewAssistantCoordinator
from .entity import BrewAssistantEntity

DATA_KEY = "temperature_stats"
MAX_WINDOW_MINUTES = 30
MIN_SAMPLE_SECONDS = 20
INVALID_STATES = {"unknown", "unavailable", "none", ""}

KEGERATOR_AIR_SOURCE_ENTITY = "sensor.kyl_temperatur_4"


@dataclass(slots=True)
class TemperatureSample:
    """One temperature sample."""

    timestamp: Any
    value: float


@dataclass(frozen=True, kw_only=True)
class TemperatureStatConfig:
    """Configuration for one rolling temperature stats sensor."""

    key: str
    name: str
    source_label: str
    icon: str
    value_fn: Callable[[BrewAssistantCoordinator], float | None]
    source_entity_fn: Callable[[BrewAssistantCoordinator], str | None]


def _as_float(value: Any) -> float | None:
    try:
        if value is None or str(value).lower() in INVALID_STATES:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _float_state(coordinator: BrewAssistantCoordinator, entity_id: str) -> float | None:
    state = coordinator.hass.states.get(entity_id)
    if state is None or state.state in INVALID_STATES:
        return None
    return _as_float(state.state)


def _configured_chamber_entity(coordinator: BrewAssistantCoordinator) -> str | None:
    return coordinator.configured_entities.get(CONF_CHAMBER_TEMP_ENTITY)


def _liquid_source_entity(coordinator: BrewAssistantCoordinator) -> str | None:
    data = coordinator.data
    return data.liquid_temperature_entity if data is not None else None


def _temperature_stats_bucket(coordinator: BrewAssistantCoordinator) -> dict[str, Any]:
    domain_data = coordinator.hass.data.setdefault(DOMAIN, {})
    return domain_data.setdefault(DATA_KEY, {})


def _samples_for(coordinator: BrewAssistantCoordinator, key: str) -> deque[TemperatureSample]:
    bucket = _temperature_stats_bucket(coordinator)
    samples = bucket.get(key)
    if not isinstance(samples, deque):
        samples = deque()
        bucket[key] = samples
    return samples


def _record_sample(coordinator: BrewAssistantCoordinator, key: str, value: float | None) -> None:
    """Record one sample with simple de-dup/throttle."""
    if value is None:
        return

    now = dt_util.utcnow()
    samples = _samples_for(coordinator, key)

    if samples:
        age = (now - samples[-1].timestamp).total_seconds()
        if age < MIN_SAMPLE_SECONDS:
            return

    samples.append(TemperatureSample(timestamp=now, value=round(float(value), 3)))

    cutoff = now.timestamp() - (MAX_WINDOW_MINUTES * 60)
    while samples and samples[0].timestamp.timestamp() < cutoff:
        samples.popleft()


def _window_values(samples: deque[TemperatureSample], minutes: int) -> list[TemperatureSample]:
    now = dt_util.utcnow()
    cutoff = now.timestamp() - (minutes * 60)
    return [sample for sample in samples if sample.timestamp.timestamp() >= cutoff]


def _average(values: list[TemperatureSample]) -> float | None:
    if not values:
        return None
    return round(sum(sample.value for sample in values) / len(values), 2)


def _minimum(values: list[TemperatureSample]) -> float | None:
    if not values:
        return None
    return round(min(sample.value for sample in values), 2)


def _maximum(values: list[TemperatureSample]) -> float | None:
    if not values:
        return None
    return round(max(sample.value for sample in values), 2)


def _trend_per_hour(values: list[TemperatureSample]) -> float | None:
    """Return simple first-to-last trend in °C/h."""
    if len(values) < 2:
        return None
    first = values[0]
    last = values[-1]
    seconds = (last.timestamp - first.timestamp).total_seconds()
    if seconds < 120:
        return None
    return round(((last.value - first.value) / seconds) * 3600, 2)


def _trend_label(trend: float | None) -> str:
    if trend is None:
        return "collecting"
    if trend <= -0.1:
        return "cooling"
    if trend >= 0.1:
        return "warming"
    return "stable"


def build_temperature_stats(coordinator: BrewAssistantCoordinator, config: TemperatureStatConfig) -> dict[str, Any]:
    """Build rolling stats for one configured temperature source."""
    current = config.value_fn(coordinator)
    _record_sample(coordinator, config.key, current)

    samples = _samples_for(coordinator, config.key)
    values_5m = _window_values(samples, 5)
    values_15m = _window_values(samples, 15)
    values_30m = _window_values(samples, 30)
    trend_30m = _trend_per_hour(values_30m)

    avg_5m = _average(values_5m)
    avg_15m = _average(values_15m)
    avg_30m = _average(values_30m)

    return {
        "current": round(current, 2) if current is not None else None,
        "average_5m": avg_5m,
        "average_15m": avg_15m,
        "average_30m": avg_30m,
        "minimum_30m": _minimum(values_30m),
        "maximum_30m": _maximum(values_30m),
        "trend_c_per_hour": trend_30m,
        "trend_label": _trend_label(trend_30m),
        "sample_count": len(values_30m),
        "oldest_sample": values_30m[0].timestamp.isoformat() if values_30m else None,
        "newest_sample": values_30m[-1].timestamp.isoformat() if values_30m else None,
        "window_minutes": MAX_WINDOW_MINUTES,
        "primary_window_minutes": 15,
        "source": "python_temperature_stats",
        "source_label": config.source_label,
        "source_entity": config.source_entity_fn(coordinator),
        "summary": _summary(config.source_label, current, avg_15m, trend_30m),
    }


def _summary(label: str, current: float | None, avg_15m: float | None, trend: float | None) -> str:
    current_text = "—" if current is None else f"{current:.1f} °C"
    average_text = "—" if avg_15m is None else f"{avg_15m:.1f} °C"
    trend_text = "collecting" if trend is None else f"{trend:+.2f} °C/h"
    return f"{label} · now {current_text} · avg15 {average_text} · trend {trend_text}"


def _kegerator_air(coordinator: BrewAssistantCoordinator) -> float | None:
    return _float_state(coordinator, KEGERATOR_AIR_SOURCE_ENTITY)


def _chamber_air(coordinator: BrewAssistantCoordinator) -> float | None:
    data = coordinator.data
    if data is None:
        return None
    return data.chamber_temperature


def _liquid(coordinator: BrewAssistantCoordinator) -> float | None:
    data = coordinator.data
    if data is None:
        return None
    return data.liquid_temperature


def _air_liquid_delta(coordinator: BrewAssistantCoordinator) -> float | None:
    data = coordinator.data
    if data is None or data.chamber_temperature is None or data.liquid_temperature is None:
        return None
    return round(data.chamber_temperature - data.liquid_temperature, 2)


TEMPERATURE_STAT_CONFIGS: tuple[TemperatureStatConfig, ...] = (
    TemperatureStatConfig(
        key="kegerator_air_temperature_average",
        name="BrewAssistant Kegerator Air Temperature Average",
        source_label="Kegerator air",
        icon="mdi:fridge-thermometer",
        value_fn=_kegerator_air,
        source_entity_fn=lambda coordinator: KEGERATOR_AIR_SOURCE_ENTITY,
    ),
    TemperatureStatConfig(
        key="fermentation_chamber_air_temperature_average",
        name="BrewAssistant Fermentation Chamber Air Temperature Average",
        source_label="Fermentation chamber air",
        icon="mdi:thermometer-lines",
        value_fn=_chamber_air,
        source_entity_fn=_configured_chamber_entity,
    ),
    TemperatureStatConfig(
        key="fermentation_liquid_temperature_average",
        name="BrewAssistant Fermentation Liquid Temperature Average",
        source_label="Fermentation liquid",
        icon="mdi:beer-outline",
        value_fn=_liquid,
        source_entity_fn=_liquid_source_entity,
    ),
    TemperatureStatConfig(
        key="fermentation_air_liquid_delta_average",
        name="BrewAssistant Fermentation Air Liquid Delta Average",
        source_label="Air/liquid delta",
        icon="mdi:delta",
        value_fn=_air_liquid_delta,
        source_entity_fn=lambda coordinator: "calculated: chamber_air - liquid",
    ),
)


class BrewAssistantTemperatureStatsSensor(BrewAssistantEntity, SensorEntity):
    """Rolling average/trend temperature stats sensor."""

    _attr_has_entity_name = False

    def __init__(self, coordinator: BrewAssistantCoordinator, config: TemperatureStatConfig) -> None:
        super().__init__(coordinator, config.key)
        self._config = config
        self._attr_name = config.name
        self._attr_suggested_object_id = f"{DOMAIN}_{config.key}"
        self._attr_icon = config.icon
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> float | None:
        """Return primary rolling average value."""
        stats = build_temperature_stats(self.coordinator, self._config)
        return stats["average_15m"] or stats["current"]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return rolling stats as attributes."""
        return build_temperature_stats(self.coordinator, self._config)


def create_temperature_stat_sensors(
    coordinator: BrewAssistantCoordinator,
) -> list[BrewAssistantTemperatureStatsSensor]:
    """Create BrewAssistant rolling temperature stat sensors."""
    return [
        BrewAssistantTemperatureStatsSensor(coordinator, config)
        for config in TEMPERATURE_STAT_CONFIGS
    ]
