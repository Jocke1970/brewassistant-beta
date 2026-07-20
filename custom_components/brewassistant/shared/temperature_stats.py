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

from ..const import CONF_CHAMBER_TEMP_ENTITY, CONF_KEGERATOR_AIR_TEMP_ENTITY, DOMAIN
from ..coordinator import BrewAssistantCoordinator
from ..entity import BrewAssistantEntity

DATA_KEY = "temperature_stats"
MAX_WINDOW_MINUTES = 30
MIN_SAMPLE_SECONDS = 20
INVALID_STATES = {"unknown", "unavailable", "none", ""}
FALLBACK_LIQUID_SOURCES = {"chamber fallback", "unavailable"}
FERMENTATION_SCOPE_STAGES = {"fermentation", "cold_crash"}
FERMENTATION_SCOPE_STATUSES = {
    "primary fermentation",
    "cold crash",
}



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
    sample_allowed_fn: Callable[[BrewAssistantCoordinator], bool] | None = None
    source_status_fn: Callable[[BrewAssistantCoordinator], str] | None = None


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


def _configured_kegerator_air_entity(coordinator: BrewAssistantCoordinator) -> str | None:
    return coordinator.configured_entities.get(CONF_KEGERATOR_AIR_TEMP_ENTITY)


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


def _clear_samples(coordinator: BrewAssistantCoordinator, key: str) -> None:
    """Clear samples for a sensor when the source becomes semantically invalid."""
    _samples_for(coordinator, key).clear()


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


def _sample_allowed(coordinator: BrewAssistantCoordinator, config: TemperatureStatConfig) -> bool:
    if config.sample_allowed_fn is None:
        return True
    return config.sample_allowed_fn(coordinator)


def _source_status(coordinator: BrewAssistantCoordinator, config: TemperatureStatConfig) -> str:
    if config.source_status_fn is not None:
        return config.source_status_fn(coordinator)
    if config.sample_allowed_fn is None:
        return "sampling"
    return "sampling" if config.sample_allowed_fn(coordinator) else "not_sampled"


def build_temperature_stats(coordinator: BrewAssistantCoordinator, config: TemperatureStatConfig) -> dict[str, Any]:
    """Build rolling stats for one configured temperature source."""
    current = config.value_fn(coordinator)
    allowed = _sample_allowed(coordinator, config)

    if allowed:
        _record_sample(coordinator, config.key, current)
    else:
        _clear_samples(coordinator, config.key)

    samples = _samples_for(coordinator, config.key)
    values_5m = _window_values(samples, 5)
    values_15m = _window_values(samples, 15)
    values_30m = _window_values(samples, 30)
    trend_30m = _trend_per_hour(values_30m)

    avg_5m = _average(values_5m)
    avg_15m = _average(values_15m)
    avg_30m = _average(values_30m)
    source_status = _source_status(coordinator, config)

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
        "source_status": source_status,
        "sample_allowed": allowed,
        "fermentation_scope_active": _fermentation_scope_active(coordinator),
        "real_liquid_source_available": _real_liquid_source_available(coordinator),
        "summary": _summary(config.source_label, current, avg_15m, trend_30m, source_status),
    }


def _summary(
    label: str,
    current: float | None,
    avg_15m: float | None,
    trend: float | None,
    source_status: str,
) -> str:
    current_text = "—" if current is None else f"{current:.1f} °C"
    average_text = "—" if avg_15m is None else f"{avg_15m:.1f} °C"
    trend_text = "collecting" if trend is None else f"{trend:+.2f} °C/h"
    if source_status != "sampling":
        return f"{label} · {source_status} · avg15 — · trend collecting"
    return f"{label} · now {current_text} · avg15 {average_text} · trend {trend_text}"


def _kegerator_air(coordinator: BrewAssistantCoordinator) -> float | None:
    source_entity = _configured_kegerator_air_entity(coordinator)
    return _float_state(coordinator, source_entity) if source_entity else None


def _chamber_air(coordinator: BrewAssistantCoordinator) -> float | None:
    data = coordinator.data
    if data is None:
        return None
    return data.chamber_temperature


def _real_liquid_source_available(coordinator: BrewAssistantCoordinator) -> bool:
    data = coordinator.data
    if data is None:
        return False
    source = (data.liquid_temperature_source or "").lower()
    if source in FALLBACK_LIQUID_SOURCES:
        return False
    if data.liquid_temperature_entity is None:
        return False
    return data.liquid_temperature is not None


def _fermentation_scope_active(coordinator: BrewAssistantCoordinator) -> bool:
    data = coordinator.data
    if data is None:
        return False
    stage = (data.process_current_action_stage or "").lower()
    status = (data.process_status or "").lower()
    return stage in FERMENTATION_SCOPE_STAGES or status in FERMENTATION_SCOPE_STATUSES


def _fermentation_liquid_sample_allowed(coordinator: BrewAssistantCoordinator) -> bool:
    return _real_liquid_source_available(coordinator) and _fermentation_scope_active(coordinator)


def _fermentation_liquid_source_status(coordinator: BrewAssistantCoordinator) -> str:
    if not _real_liquid_source_available(coordinator):
        return "fallback_not_sampled"
    if not _fermentation_scope_active(coordinator):
        return "out_of_scope_not_sampled"
    return "sampling"


def _liquid(coordinator: BrewAssistantCoordinator) -> float | None:
    if not _fermentation_liquid_sample_allowed(coordinator):
        return None
    data = coordinator.data
    return data.liquid_temperature if data is not None else None


def _air_liquid_delta(coordinator: BrewAssistantCoordinator) -> float | None:
    if not _fermentation_liquid_sample_allowed(coordinator):
        return None
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
        source_entity_fn=_configured_kegerator_air_entity,
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
        sample_allowed_fn=_fermentation_liquid_sample_allowed,
        source_status_fn=_fermentation_liquid_source_status,
    ),
    TemperatureStatConfig(
        key="fermentation_air_liquid_delta_average",
        name="BrewAssistant Fermentation Air Liquid Delta Average",
        source_label="Air/liquid delta",
        icon="mdi:delta",
        value_fn=_air_liquid_delta,
        source_entity_fn=lambda coordinator: "calculated: chamber_air - real_liquid",
        sample_allowed_fn=_fermentation_liquid_sample_allowed,
        source_status_fn=_fermentation_liquid_source_status,
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
