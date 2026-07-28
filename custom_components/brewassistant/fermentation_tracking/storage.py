"""Home Assistant Storage persistence for fermentation tracking."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from ..const import DOMAIN
from .calculations import valid_sg, valid_temperature
from .models import (
    DEFAULT_FG_TOLERANCE,
    DEFAULT_STABILITY_TOLERANCE,
    DEFAULT_STABLE_HOURS,
    DEFAULT_WCF,
    INSTRUMENT_MANUAL,
    INSTRUMENT_REFRACTOMETER,
    MAX_OBSERVATIONS,
    METRIC_GRAVITY,
    METRIC_TEMPERATURE,
    SOURCE_AUTOMATIC,
    SOURCE_MANUAL,
    SOURCE_MODE_HYBRID,
    SOURCE_MODES,
    UNIT_BRIX,
    UNIT_SG,
    FermentationObservation,
    FermentationRuntime,
)

DATA_KEY = "fermentation_runtime"
STORE_KEY = "fermentation_runtime_store"
LOADED_KEY = "fermentation_runtime_loaded"
STORAGE_KEY = "brewassistant_fermentation_runtime"
STORAGE_VERSION = 1
INVALID = {"", "none", "unknown", "unavailable"}


def as_float(value: Any, fallback: float | None = None) -> float | None:
    try:
        if value is None or str(value).lower() in INVALID:
            return fallback
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return fallback


def as_datetime(value: Any, fallback: datetime | None = None) -> datetime | None:
    if isinstance(value, datetime):
        return dt_util.as_utc(value)
    if value is None or str(value).lower() in INVALID:
        return fallback
    parsed = dt_util.parse_datetime(str(value))
    if parsed is not None:
        return dt_util.as_utc(parsed)
    parsed_date = dt_util.parse_date(str(value))
    if parsed_date is not None:
        return dt_util.as_utc(dt_util.start_of_local_day(parsed_date))
    return fallback


def observation_to_dict(observation: FermentationObservation) -> dict[str, Any]:
    return {
        "metric": observation.metric,
        "observed_at": observation.observed_at.isoformat(),
        "source_type": observation.source_type,
        "source": observation.source,
        "source_entity": observation.source_entity,
        "raw_value": observation.raw_value,
        "raw_unit": observation.raw_unit,
        "normalized_value": observation.normalized_value,
        "normalized_unit": observation.normalized_unit,
        "measurement_method": observation.measurement_method,
        "note": observation.note,
        "wort_correction_factor": observation.wort_correction_factor,
        "calculation_input_brix": observation.calculation_input_brix,
    }


def _observation_from_dict(data: Any) -> FermentationObservation | None:
    if not isinstance(data, dict):
        return None
    metric = str(data.get("metric") or "").lower()
    observed_at = as_datetime(data.get("observed_at"))
    source_type = str(data.get("source_type") or SOURCE_MANUAL).lower()
    raw_value = as_float(data.get("raw_value"))
    normalized_value = as_float(data.get("normalized_value"))
    if (
        metric not in {METRIC_GRAVITY, METRIC_TEMPERATURE}
        or observed_at is None
        or source_type not in {SOURCE_MANUAL, SOURCE_AUTOMATIC}
        or raw_value is None
        or normalized_value is None
    ):
        return None
    if metric == METRIC_GRAVITY and not valid_sg(normalized_value):
        return None
    if metric == METRIC_TEMPERATURE and not valid_temperature(normalized_value):
        return None
    return FermentationObservation(
        metric=metric,
        observed_at=observed_at,
        source_type=source_type,
        source=str(data.get("source") or source_type),
        source_entity=str(data["source_entity"]) if data.get("source_entity") else None,
        raw_value=round(raw_value, 4),
        raw_unit=str(data.get("raw_unit") or (UNIT_SG if metric == METRIC_GRAVITY else "°C")),
        normalized_value=round(normalized_value, 4 if metric == METRIC_GRAVITY else 2),
        normalized_unit=str(data.get("normalized_unit") or (UNIT_SG if metric == METRIC_GRAVITY else "°C")),
        measurement_method=str(data.get("measurement_method") or "manual"),
        note=str(data["note"]) if data.get("note") not in {None, ""} else None,
        wort_correction_factor=as_float(data.get("wort_correction_factor")),
        calculation_input_brix=as_float(data.get("calculation_input_brix")),
    )


def _legacy_sample(data: Any) -> FermentationObservation | None:
    if not isinstance(data, dict):
        return None
    observed_at = as_datetime(data.get("measured_at"))
    raw_value = as_float(data.get("raw_value"))
    corrected_sg = as_float(data.get("corrected_sg"))
    measurement_type = str(data.get("measurement_type") or "").lower()
    if observed_at is None or raw_value is None or not valid_sg(corrected_sg):
        return None
    refractometer = measurement_type == "refractometer_brix"
    instrument = INSTRUMENT_REFRACTOMETER if refractometer else INSTRUMENT_MANUAL
    unit = UNIT_BRIX if refractometer else UNIT_SG
    return FermentationObservation(
        metric=METRIC_GRAVITY,
        observed_at=observed_at,
        source_type=SOURCE_MANUAL,
        source=str(data.get("source") or f"manual_{instrument}"),
        source_entity=None,
        raw_value=round(raw_value, 4),
        raw_unit=unit,
        normalized_value=round(float(corrected_sg), 4),
        normalized_unit=UNIT_SG,
        measurement_method=f"{instrument}_{unit}",
        note=str(data["note"]) if data.get("note") not in {None, ""} else None,
        wort_correction_factor=as_float(data.get("wort_correction_factor")),
        calculation_input_brix=raw_value if refractometer else None,
    )


def runtime_to_dict(runtime: FermentationRuntime) -> dict[str, Any]:
    return {
        "active": runtime.active,
        "recipe_name": runtime.recipe_name,
        "original_gravity": runtime.original_gravity,
        "target_final_gravity": runtime.target_final_gravity,
        "temp_rise_trigger_sg": runtime.temp_rise_trigger_sg,
        "primary_temperature_c": runtime.primary_temperature_c,
        "temp_rise_temperature_c": runtime.temp_rise_temperature_c,
        "stable_hours": runtime.stable_hours,
        "stability_tolerance_sg": runtime.stability_tolerance_sg,
        "fg_tolerance_sg": runtime.fg_tolerance_sg,
        "wort_correction_factor": runtime.wort_correction_factor,
        "gravity_source_mode": runtime.gravity_source_mode,
        "temperature_source_mode": runtime.temperature_source_mode,
        "started_at": runtime.started_at.isoformat() if runtime.started_at else None,
        "updated_at": runtime.updated_at.isoformat() if runtime.updated_at else None,
        "observations": [observation_to_dict(item) for item in runtime.observations[-MAX_OBSERVATIONS:]],
    }


def runtime_from_dict(data: Any) -> FermentationRuntime:
    if not isinstance(data, dict):
        return FermentationRuntime()
    runtime = FermentationRuntime(
        active=bool(data.get("active", False)),
        recipe_name=str(data.get("recipe_name") or ""),
        started_at=as_datetime(data.get("started_at")),
        updated_at=as_datetime(data.get("updated_at")),
    )
    for key in ("original_gravity", "target_final_gravity", "temp_rise_trigger_sg"):
        value = as_float(data.get(key))
        if valid_sg(value):
            setattr(runtime, key, round(float(value), 4))
    for key in ("primary_temperature_c", "temp_rise_temperature_c"):
        value = as_float(data.get(key))
        if valid_temperature(value):
            setattr(runtime, key, round(float(value), 1))
    runtime.stable_hours = max(1.0, as_float(data.get("stable_hours"), DEFAULT_STABLE_HOURS) or DEFAULT_STABLE_HOURS)
    runtime.stability_tolerance_sg = max(0.0001, as_float(data.get("stability_tolerance_sg"), DEFAULT_STABILITY_TOLERANCE) or DEFAULT_STABILITY_TOLERANCE)
    runtime.fg_tolerance_sg = max(0.0001, as_float(data.get("fg_tolerance_sg"), DEFAULT_FG_TOLERANCE) or DEFAULT_FG_TOLERANCE)
    runtime.wort_correction_factor = max(0.5, as_float(data.get("wort_correction_factor"), DEFAULT_WCF) or DEFAULT_WCF)
    for key in ("gravity_source_mode", "temperature_source_mode"):
        mode = str(data.get(key) or SOURCE_MODE_HYBRID).lower()
        setattr(runtime, key, mode if mode in SOURCE_MODES else SOURCE_MODE_HYBRID)
    observations = [_observation_from_dict(item) for item in data.get("observations", [])]
    if not any(item is not None for item in observations):
        observations.extend(_legacy_sample(item) for item in data.get("samples", []))
    runtime.observations = sorted(
        [item for item in observations if item is not None],
        key=lambda item: item.observed_at,
    )[-MAX_OBSERVATIONS:]
    return runtime


def _store(hass: HomeAssistant) -> Store:
    data = hass.data.setdefault(DOMAIN, {})
    store = data.get(STORE_KEY)
    if not isinstance(store, Store):
        store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        data[STORE_KEY] = store
    return store


def get_runtime(hass: HomeAssistant) -> FermentationRuntime:
    data = hass.data.setdefault(DOMAIN, {})
    runtime = data.get(DATA_KEY)
    if not isinstance(runtime, FermentationRuntime):
        runtime = FermentationRuntime()
        data[DATA_KEY] = runtime
    return runtime


def set_runtime(hass: HomeAssistant, runtime: FermentationRuntime) -> None:
    hass.data.setdefault(DOMAIN, {})[DATA_KEY] = runtime


async def async_load(hass: HomeAssistant) -> FermentationRuntime:
    runtime = runtime_from_dict(await _store(hass).async_load())
    set_runtime(hass, runtime)
    hass.data.setdefault(DOMAIN, {})[LOADED_KEY] = True
    return runtime


async def async_save(hass: HomeAssistant) -> None:
    await _store(hass).async_save(runtime_to_dict(get_runtime(hass)))
