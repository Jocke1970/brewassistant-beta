"""Observation normalization and source resolution for fermentation tracking."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .calculations import corrected_refractometer_sg, sg_to_brix, valid_brix, valid_sg, valid_temperature
from .models import (
    GRAVITY_INSTRUMENTS,
    GRAVITY_UNITS,
    INSTRUMENT_HYDROMETER,
    INSTRUMENT_MANUAL,
    INSTRUMENT_REFRACTOMETER,
    INSTRUMENT_SENSOR,
    MAX_OBSERVATIONS,
    METRIC_GRAVITY,
    METRIC_TEMPERATURE,
    SOURCE_AUTOMATIC,
    SOURCE_MANUAL,
    SOURCE_MODE_AUTOMATIC,
    SOURCE_MODE_MANUAL,
    UNIT_BRIX,
    UNIT_SG,
    FermentationObservation,
    FermentationRuntime,
)
from .storage import INVALID, as_datetime, as_float, get_runtime

METHOD_ALIASES: dict[str, tuple[str, str]] = {
    "refractometer_brix": (INSTRUMENT_REFRACTOMETER, UNIT_BRIX),
    "refractometer_sg": (INSTRUMENT_REFRACTOMETER, UNIT_SG),
    "brix": (INSTRUMENT_REFRACTOMETER, UNIT_BRIX),
    "refractometer": (INSTRUMENT_REFRACTOMETER, UNIT_BRIX),
    "hydrometer_sg": (INSTRUMENT_HYDROMETER, UNIT_SG),
    "hydrometer": (INSTRUMENT_HYDROMETER, UNIT_SG),
    "manual_sg": (INSTRUMENT_MANUAL, UNIT_SG),
    "sg": (INSTRUMENT_MANUAL, UNIT_SG),
}


def _resolve_gravity_input(data: dict[str, Any]) -> tuple[str, str, float] | None:
    raw_value = data.get("gravity_value", data.get("value"))
    if raw_value is None or str(raw_value).lower() in INVALID:
        return None
    value = as_float(raw_value)
    if value is None:
        raise ValueError("gravity_value must be numeric")
    method = str(data.get("gravity_method") or data.get("measurement_type") or "").lower().strip()
    if method in METHOD_ALIASES:
        instrument, unit = METHOD_ALIASES[method]
    else:
        instrument = str(data.get("gravity_instrument") or "").lower().strip()
        unit = str(data.get("gravity_unit") or "").lower().strip()
    if instrument not in GRAVITY_INSTRUMENTS - {INSTRUMENT_SENSOR}:
        raise ValueError("gravity_instrument must be refractometer, hydrometer, or manual")
    if unit not in GRAVITY_UNITS:
        raise ValueError("gravity_unit must be brix or sg")
    if instrument in {INSTRUMENT_HYDROMETER, INSTRUMENT_MANUAL} and unit != UNIT_SG:
        raise ValueError(f"{instrument} observations must use SG")
    return instrument, unit, value


def _gravity_observation(
    runtime: FermentationRuntime,
    *,
    instrument: str,
    unit: str,
    value: float,
    observed_at: datetime,
    note: str | None,
) -> FermentationObservation:
    calculation_brix: float | None = None
    correction_factor: float | None = None
    if instrument == INSTRUMENT_REFRACTOMETER:
        if runtime.original_gravity is None:
            raise ValueError("original_gravity is required to correct a refractometer reading")
        if unit == UNIT_BRIX:
            if not valid_brix(value):
                raise ValueError("refractometer Brix must be between 0 and 40")
            calculation_brix = value
        else:
            if not valid_sg(value):
                raise ValueError("refractometer SG scale must be between 0.900 and 1.200")
            calculation_brix = sg_to_brix(value)
        normalized = corrected_refractometer_sg(
            runtime.original_gravity,
            calculation_brix,
            runtime.wort_correction_factor,
        )
        source = "manual_refractometer"
        correction_factor = runtime.wort_correction_factor
    else:
        if not valid_sg(value):
            raise ValueError("SG must be between 0.900 and 1.200")
        normalized = round(value, 4)
        source = "manual_hydrometer" if instrument == INSTRUMENT_HYDROMETER else "manual_sg"
    return FermentationObservation(
        metric=METRIC_GRAVITY,
        observed_at=observed_at,
        source_type=SOURCE_MANUAL,
        source=source,
        source_entity=None,
        raw_value=round(value, 4),
        raw_unit=unit,
        normalized_value=normalized,
        normalized_unit=UNIT_SG,
        measurement_method=f"{instrument}_{unit}",
        note=note,
        wort_correction_factor=correction_factor,
        calculation_input_brix=round(calculation_brix, 4) if calculation_brix is not None else None,
    )


def record_manual_observation(
    hass: HomeAssistant,
    data: dict[str, Any],
) -> list[FermentationObservation]:
    """Store optional gravity and temperature values with one shared timestamp."""
    runtime = get_runtime(hass)
    observed_at = as_datetime(
        data.get("observed_at", data.get("measured_at")),
        datetime.now(timezone.utc),
    )
    if observed_at is None:
        raise ValueError("observed_at must be a valid datetime")
    note = str(data.get("note") or "").strip() or None
    observations: list[FermentationObservation] = []
    gravity_input = _resolve_gravity_input(data)
    if gravity_input is not None:
        instrument, unit, value = gravity_input
        observations.append(
            _gravity_observation(
                runtime,
                instrument=instrument,
                unit=unit,
                value=value,
                observed_at=observed_at,
                note=note,
            )
        )
    raw_temperature = data.get("temperature_c")
    if raw_temperature is not None and str(raw_temperature).lower() not in INVALID:
        temperature = as_float(raw_temperature)
        if not valid_temperature(temperature):
            raise ValueError("temperature_c must be between -5 and 50 °C")
        observations.append(
            FermentationObservation(
                metric=METRIC_TEMPERATURE,
                observed_at=observed_at,
                source_type=SOURCE_MANUAL,
                source="manual_temperature",
                source_entity=None,
                raw_value=round(float(temperature), 2),
                raw_unit="°C",
                normalized_value=round(float(temperature), 2),
                normalized_unit="°C",
                measurement_method="manual_temperature",
                note=note,
            )
        )
    if not observations:
        raise ValueError("provide gravity_value and/or temperature_c")
    runtime.observations = sorted(
        [*runtime.observations, *observations],
        key=lambda item: item.observed_at,
    )[-MAX_OBSERVATIONS:]
    runtime.updated_at = datetime.now(timezone.utc)
    return observations


def manual_candidate(runtime: FermentationRuntime, metric: str) -> dict[str, Any] | None:
    candidates = [
        item for item in runtime.observations
        if item.metric == metric and item.source_type == SOURCE_MANUAL
    ]
    if not candidates:
        return None
    item = max(candidates, key=lambda candidate: candidate.observed_at)
    return {
        "value": item.normalized_value,
        "source_type": item.source_type,
        "source": item.source,
        "entity": item.source_entity,
        "observed_at": item.observed_at,
        "measurement_method": item.measurement_method,
        "raw_value": item.raw_value,
        "raw_unit": item.raw_unit,
        "normalized_unit": item.normalized_unit,
        "calculation_input_brix": item.calculation_input_brix,
    }


def automatic_candidate(
    *,
    metric: str,
    value: float | None,
    updated_at: datetime | None,
    entity: str | None,
) -> dict[str, Any] | None:
    valid = valid_sg(value) if metric == METRIC_GRAVITY else valid_temperature(value)
    if not valid or updated_at is None:
        return None
    digits = 4 if metric == METRIC_GRAVITY else 2
    return {
        "value": round(float(value), digits),
        "source_type": SOURCE_AUTOMATIC,
        "source": "automatic_sensor",
        "entity": entity,
        "observed_at": dt_util.as_utc(updated_at),
        "measurement_method": "sensor_sg" if metric == METRIC_GRAVITY else "sensor_temperature",
        "raw_value": round(float(value), digits),
        "raw_unit": UNIT_SG if metric == METRIC_GRAVITY else "°C",
        "normalized_unit": UNIT_SG if metric == METRIC_GRAVITY else "°C",
        "calculation_input_brix": None,
    }


def resolve_candidate(
    mode: str,
    manual: dict[str, Any] | None,
    automatic: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if mode == SOURCE_MODE_MANUAL:
        return manual
    if mode == SOURCE_MODE_AUTOMATIC:
        return automatic
    candidates = [item for item in (manual, automatic) if item is not None]
    return max(
        candidates,
        key=lambda item: (item["observed_at"], 1 if item["source_type"] == SOURCE_MANUAL else 0),
        default=None,
    )


def stability_snapshot(runtime: FermentationRuntime) -> dict[str, Any]:
    observations = sorted(
        [item for item in runtime.observations if item.metric == METRIC_GRAVITY],
        key=lambda item: item.observed_at,
    )
    if len(observations) < 2:
        return {
            "stable": False,
            "span_hours": 0.0,
            "count": len(observations),
            "min_sg": None,
            "max_sg": None,
            "delta_sg": None,
            "stable_since": None,
            "reason": "at least two persisted gravity observations are required",
        }
    latest = observations[-1].observed_at
    cutoff = latest.timestamp() - runtime.stable_hours * 3600
    window = [item for item in observations if item.observed_at.timestamp() >= cutoff]
    before = [item for item in observations if item.observed_at.timestamp() < cutoff]
    if before:
        window.insert(0, before[-1])
    span = (window[-1].observed_at - window[0].observed_at).total_seconds() / 3600
    values = [item.normalized_value for item in window]
    low, high = min(values), max(values)
    delta = high - low
    stable = span >= runtime.stable_hours and delta <= runtime.stability_tolerance_sg
    if span < runtime.stable_hours:
        reason = f"only {span:.1f} of {runtime.stable_hours:.1f} required hours observed"
    elif delta > runtime.stability_tolerance_sg:
        reason = f"SG range {delta:.4f} exceeds tolerance {runtime.stability_tolerance_sg:.4f}"
    else:
        reason = f"SG stable within {delta:.4f} for {span:.1f} hours"
    return {
        "stable": stable,
        "span_hours": round(span, 1),
        "count": len(window),
        "min_sg": round(low, 4),
        "max_sg": round(high, 4),
        "delta_sg": round(delta, 4),
        "stable_since": window[0].observed_at.isoformat() if stable else None,
        "reason": reason,
    }
