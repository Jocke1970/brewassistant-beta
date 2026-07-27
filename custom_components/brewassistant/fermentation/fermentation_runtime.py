"""Python-owned fermentation tracking and persisted gravity observations."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from ..const import DOMAIN

DATA_KEY = "fermentation_runtime"
STORE_KEY = "fermentation_runtime_store"
LOADED_KEY = "fermentation_runtime_loaded"
STORAGE_KEY = "brewassistant_fermentation_runtime"
STORAGE_VERSION = 1
MAX_SAMPLES = 500

SERVICE_START = "fermentation_start"
SERVICE_UPDATE = "fermentation_update"
SERVICE_RECORD = "fermentation_record_gravity"
SERVICE_RESET = "fermentation_reset"

REFRACTOMETER = "refractometer_brix"
HYDROMETER = "hydrometer_sg"
MANUAL_SG = "manual_sg"
MEASUREMENT_TYPES = {REFRACTOMETER, HYDROMETER, MANUAL_SG}
ALIASES = {
    "brix": REFRACTOMETER,
    "refractometer": REFRACTOMETER,
    "hydrometer": HYDROMETER,
    "sg": MANUAL_SG,
}
INVALID = {"", "none", "unknown", "unavailable"}

DEFAULT_WCF = 1.04
DEFAULT_STABLE_HOURS = 48.0
DEFAULT_STABILITY_TOLERANCE = 0.001
DEFAULT_FG_TOLERANCE = 0.002


@dataclass(slots=True)
class GravitySample:
    """One persisted gravity observation."""

    measured_at: datetime
    measurement_type: str
    raw_value: float
    corrected_sg: float
    source: str
    note: str | None = None
    wort_correction_factor: float | None = None


@dataclass(slots=True)
class FermentationRuntime:
    """Mutable fermentation tracking state."""

    active: bool = False
    recipe_name: str = ""
    original_gravity: float | None = None
    target_final_gravity: float | None = None
    temp_rise_trigger_sg: float | None = None
    primary_temperature_c: float | None = None
    temp_rise_temperature_c: float | None = None
    stable_hours: float = DEFAULT_STABLE_HOURS
    stability_tolerance_sg: float = DEFAULT_STABILITY_TOLERANCE
    fg_tolerance_sg: float = DEFAULT_FG_TOLERANCE
    wort_correction_factor: float = DEFAULT_WCF
    started_at: datetime | None = None
    updated_at: datetime | None = None
    samples: list[GravitySample] = field(default_factory=list)


def _float(value: Any, fallback: float | None = None) -> float | None:
    try:
        if value is None or str(value).lower() in INVALID:
            return fallback
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return fallback


def _datetime(value: Any, fallback: datetime | None = None) -> datetime | None:
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


def _valid_sg(value: float | None) -> bool:
    return value is not None and 0.900 <= value <= 1.200


def sg_to_brix(sg: float) -> float:
    """Convert true SG to equivalent Brix."""
    return 182.4601 * sg**3 - 775.6821 * sg**2 + 1262.7794 * sg - 669.5622


def corrected_refractometer_sg(og: float, brix: float, wcf: float = DEFAULT_WCF) -> float:
    """Correct fermented-beer Brix to SG using Sean Terrill's cubic fit."""
    if not _valid_sg(og):
        raise ValueError("original_gravity must be a valid SG value")
    if not 0 <= brix <= 40:
        raise ValueError("Brix must be between 0 and 40")
    if not 0.5 <= wcf <= 1.5:
        raise ValueError("wort_correction_factor must be between 0.5 and 1.5")

    ob = sg_to_brix(og)
    fb = brix / wcf
    corrected = (
        1.0000
        - 0.0044993 * ob
        + 0.011774 * fb
        + 0.00027581 * ob**2
        - 0.0012717 * fb**2
        - 0.0000072800 * ob**3
        + 0.000063293 * fb**3
    )
    return round(corrected, 4)


def _sample_to_dict(sample: GravitySample) -> dict[str, Any]:
    return {
        "measured_at": sample.measured_at.isoformat(),
        "measurement_type": sample.measurement_type,
        "raw_value": sample.raw_value,
        "corrected_sg": sample.corrected_sg,
        "source": sample.source,
        "note": sample.note,
        "wort_correction_factor": sample.wort_correction_factor,
    }


def _sample_from_dict(data: Any) -> GravitySample | None:
    if not isinstance(data, dict):
        return None
    measured_at = _datetime(data.get("measured_at"))
    raw_value = _float(data.get("raw_value"))
    corrected_sg = _float(data.get("corrected_sg"))
    measurement_type = str(data.get("measurement_type") or "")
    if (
        measured_at is None
        or raw_value is None
        or not _valid_sg(corrected_sg)
        or measurement_type not in MEASUREMENT_TYPES
    ):
        return None
    return GravitySample(
        measured_at=measured_at,
        measurement_type=measurement_type,
        raw_value=round(raw_value, 4),
        corrected_sg=round(float(corrected_sg), 4),
        source=str(data.get("source") or measurement_type),
        note=str(data["note"]) if data.get("note") not in {None, ""} else None,
        wort_correction_factor=_float(data.get("wort_correction_factor")),
    )


def _runtime_to_dict(runtime: FermentationRuntime) -> dict[str, Any]:
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
        "started_at": runtime.started_at.isoformat() if runtime.started_at else None,
        "updated_at": runtime.updated_at.isoformat() if runtime.updated_at else None,
        "samples": [_sample_to_dict(sample) for sample in runtime.samples[-MAX_SAMPLES:]],
    }


def _runtime_from_dict(data: Any) -> FermentationRuntime:
    if not isinstance(data, dict):
        return FermentationRuntime()
    runtime = FermentationRuntime(
        active=bool(data.get("active", False)),
        recipe_name=str(data.get("recipe_name") or ""),
        started_at=_datetime(data.get("started_at")),
        updated_at=_datetime(data.get("updated_at")),
    )
    for key in ("original_gravity", "target_final_gravity", "temp_rise_trigger_sg"):
        value = _float(data.get(key))
        if _valid_sg(value):
            setattr(runtime, key, round(float(value), 4))
    for key in ("primary_temperature_c", "temp_rise_temperature_c"):
        value = _float(data.get(key))
        if value is not None and -5 <= value <= 40:
            setattr(runtime, key, round(value, 1))
    runtime.stable_hours = max(1.0, _float(data.get("stable_hours"), DEFAULT_STABLE_HOURS) or 48.0)
    runtime.stability_tolerance_sg = max(
        0.0001,
        _float(data.get("stability_tolerance_sg"), DEFAULT_STABILITY_TOLERANCE) or 0.001,
    )
    runtime.fg_tolerance_sg = max(
        0.0001,
        _float(data.get("fg_tolerance_sg"), DEFAULT_FG_TOLERANCE) or 0.002,
    )
    runtime.wort_correction_factor = max(
        0.5,
        _float(data.get("wort_correction_factor"), DEFAULT_WCF) or DEFAULT_WCF,
    )
    samples = [_sample_from_dict(item) for item in data.get("samples", [])]
    runtime.samples = sorted(
        [sample for sample in samples if sample is not None],
        key=lambda sample: sample.measured_at,
    )[-MAX_SAMPLES:]
    return runtime


def _store(hass: HomeAssistant) -> Store:
    data = hass.data.setdefault(DOMAIN, {})
    store = data.get(STORE_KEY)
    if not isinstance(store, Store):
        store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        data[STORE_KEY] = store
    return store


def get_fermentation_runtime(hass: HomeAssistant) -> FermentationRuntime:
    data = hass.data.setdefault(DOMAIN, {})
    runtime = data.get(DATA_KEY)
    if not isinstance(runtime, FermentationRuntime):
        runtime = FermentationRuntime()
        data[DATA_KEY] = runtime
    return runtime


async def async_load_fermentation_runtime(hass: HomeAssistant) -> FermentationRuntime:
    runtime = _runtime_from_dict(await _store(hass).async_load())
    data = hass.data.setdefault(DOMAIN, {})
    data[DATA_KEY] = runtime
    data[LOADED_KEY] = True
    return runtime


async def async_save_fermentation_runtime(hass: HomeAssistant) -> None:
    await _store(hass).async_save(_runtime_to_dict(get_fermentation_runtime(hass)))


def _update(runtime: FermentationRuntime, data: dict[str, Any]) -> None:
    if "recipe_name" in data:
        runtime.recipe_name = str(data.get("recipe_name") or "")
    sg_updates: dict[str, float] = {}
    for key in ("original_gravity", "target_final_gravity", "temp_rise_trigger_sg"):
        if key in data:
            value = _float(data.get(key))
            if not _valid_sg(value):
                raise ValueError(f"{key} must be a valid SG value")
            sg_updates[key] = round(float(value), 4)
    prospective_og = sg_updates.get("original_gravity", runtime.original_gravity)
    prospective_fg = sg_updates.get("target_final_gravity", runtime.target_final_gravity)
    prospective_trigger = sg_updates.get("temp_rise_trigger_sg", runtime.temp_rise_trigger_sg)
    if prospective_og is not None and prospective_fg is not None and prospective_og <= prospective_fg:
        raise ValueError("original_gravity must be greater than target_final_gravity")
    if (
        prospective_trigger is not None
        and prospective_og is not None
        and prospective_fg is not None
        and not prospective_fg <= prospective_trigger <= prospective_og
    ):
        raise ValueError("temp_rise_trigger_sg must be between target FG and OG")
    for key, value in sg_updates.items():
        setattr(runtime, key, value)
    for key in ("primary_temperature_c", "temp_rise_temperature_c"):
        if key in data:
            value = _float(data.get(key))
            if value is None or not -5 <= value <= 40:
                raise ValueError(f"{key} must be between -5 and 40 °C")
            setattr(runtime, key, round(value, 1))
    limits = {
        "stable_hours": (1.0, 720.0, 1),
        "stability_tolerance_sg": (0.0001, 0.010, 4),
        "fg_tolerance_sg": (0.0001, 0.020, 4),
        "wort_correction_factor": (0.5, 1.5, 3),
    }
    for key, (low, high, digits) in limits.items():
        if key in data:
            value = _float(data.get(key))
            if value is None or not low <= value <= high:
                raise ValueError(f"{key} must be between {low} and {high}")
            setattr(runtime, key, round(value, digits))
    if "started_at" in data:
        started_at = _datetime(data.get("started_at"))
        if started_at is None:
            raise ValueError("started_at must be a valid datetime")
        runtime.started_at = started_at
    runtime.updated_at = datetime.now(timezone.utc)


def start_fermentation_runtime(hass: HomeAssistant, data: dict[str, Any]) -> FermentationRuntime:
    runtime = FermentationRuntime()
    _update(runtime, data)
    if runtime.original_gravity is None or runtime.target_final_gravity is None:
        raise ValueError("original_gravity and target_final_gravity are required")
    runtime.active = True
    runtime.started_at = runtime.started_at or datetime.now(timezone.utc)
    hass.data.setdefault(DOMAIN, {})[DATA_KEY] = runtime
    return runtime


def update_fermentation_runtime(hass: HomeAssistant, data: dict[str, Any]) -> FermentationRuntime:
    runtime = get_fermentation_runtime(hass)
    _update(runtime, data)
    return runtime


def reset_fermentation_runtime(hass: HomeAssistant) -> FermentationRuntime:
    runtime = FermentationRuntime()
    hass.data.setdefault(DOMAIN, {})[DATA_KEY] = runtime
    return runtime


def record_gravity_observation(hass: HomeAssistant, data: dict[str, Any]) -> GravitySample:
    runtime = get_fermentation_runtime(hass)
    measurement_type = str(data.get("measurement_type") or "").lower().strip()
    measurement_type = ALIASES.get(measurement_type, measurement_type)
    if measurement_type not in MEASUREMENT_TYPES:
        raise ValueError(f"measurement_type must be one of {sorted(MEASUREMENT_TYPES)}")
    raw_value = _float(data.get("value"))
    if raw_value is None:
        raise ValueError("value is required")

    if measurement_type == REFRACTOMETER:
        if runtime.original_gravity is None:
            raise ValueError("original_gravity is required for refractometer correction")
        corrected_sg = corrected_refractometer_sg(
            runtime.original_gravity,
            raw_value,
            runtime.wort_correction_factor,
        )
        source = "manual_refractometer"
        wcf: float | None = runtime.wort_correction_factor
    else:
        if not _valid_sg(raw_value):
            raise ValueError("SG value must be between 0.900 and 1.200")
        corrected_sg = round(raw_value, 4)
        source = "manual_hydrometer" if measurement_type == HYDROMETER else "manual_sg"
        wcf = None

    measured_at = _datetime(data.get("measured_at"), datetime.now(timezone.utc))
    if measured_at is None:
        raise ValueError("measured_at must be a valid datetime")
    sample = GravitySample(
        measured_at=measured_at,
        measurement_type=measurement_type,
        raw_value=round(raw_value, 4),
        corrected_sg=corrected_sg,
        source=source,
        note=str(data.get("note") or "").strip() or None,
        wort_correction_factor=wcf,
    )
    runtime.samples = sorted([*runtime.samples, sample], key=lambda item: item.measured_at)[
        -MAX_SAMPLES:
    ]
    runtime.updated_at = datetime.now(timezone.utc)
    return sample


def _stability(runtime: FermentationRuntime) -> dict[str, Any]:
    samples = sorted(runtime.samples, key=lambda sample: sample.measured_at)
    if len(samples) < 2:
        return {
            "stable": False,
            "span_hours": 0.0,
            "count": len(samples),
            "min_sg": None,
            "max_sg": None,
            "delta_sg": None,
            "stable_since": None,
            "reason": "at least two manual observations are required",
        }
    latest = samples[-1].measured_at
    cutoff = latest.timestamp() - runtime.stable_hours * 3600
    window = [sample for sample in samples if sample.measured_at.timestamp() >= cutoff]
    before = [sample for sample in samples if sample.measured_at.timestamp() < cutoff]
    if before:
        window.insert(0, before[-1])
    span = (window[-1].measured_at - window[0].measured_at).total_seconds() / 3600
    values = [sample.corrected_sg for sample in window]
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
        "stable_since": window[0].measured_at.isoformat() if stable else None,
        "reason": reason,
    }


def _manual_candidate(runtime: FermentationRuntime) -> dict[str, Any] | None:
    if not runtime.samples:
        return None
    sample = runtime.samples[-1]
    return {
        "sg": sample.corrected_sg,
        "source": sample.source,
        "entity": None,
        "observed_at": sample.measured_at,
        "measurement_type": sample.measurement_type,
        "raw_value": sample.raw_value,
        "raw_unit": "°Bx" if sample.measurement_type == REFRACTOMETER else "SG",
    }


def _external_candidate(
    sg: float | None,
    updated_at: datetime | None,
    entity: str | None,
) -> dict[str, Any] | None:
    if not _valid_sg(sg) or updated_at is None:
        return None
    return {
        "sg": round(float(sg), 4),
        "source": "external_sensor",
        "entity": entity,
        "observed_at": dt_util.as_utc(updated_at),
        "measurement_type": "external_sg",
        "raw_value": round(float(sg), 4),
        "raw_unit": "SG",
    }


def build_fermentation_snapshot(
    hass: HomeAssistant,
    *,
    external_sg: float | None = None,
    external_updated_at: datetime | None = None,
    external_entity: str | None = None,
) -> dict[str, Any]:
    """Return one normalized downstream snapshot regardless of gravity source."""
    runtime = get_fermentation_runtime(hass)
    candidates = [
        candidate
        for candidate in (
            _manual_candidate(runtime),
            _external_candidate(external_sg, external_updated_at, external_entity),
        )
        if candidate is not None
    ]
    current = max(
        candidates,
        key=lambda item: (
            item["observed_at"],
            1 if str(item["source"]).startswith("manual_") else 0,
        ),
        default=None,
    )
    current_sg = current["sg"] if current else None
    stability = _stability(runtime)

    progress = None
    if (
        current_sg is not None
        and runtime.original_gravity is not None
        and runtime.target_final_gravity is not None
        and runtime.original_gravity > runtime.target_final_gravity
    ):
        value = (runtime.original_gravity - current_sg) / (
            runtime.original_gravity - runtime.target_final_gravity
        )
        progress = round(max(0.0, min(100.0, value * 100)), 1)
    abv = (
        round(max(0.0, (runtime.original_gravity - current_sg) * 131.25), 2)
        if current_sg is not None and runtime.original_gravity is not None
        else None
    )
    ready_rise = bool(
        runtime.active
        and current_sg is not None
        and runtime.temp_rise_trigger_sg is not None
        and current_sg <= runtime.temp_rise_trigger_sg
    )
    near_fg = bool(
        current_sg is not None
        and runtime.target_final_gravity is not None
        and current_sg <= runtime.target_final_gravity + runtime.fg_tolerance_sg
    )
    ready_crash = bool(runtime.active and stability["stable"] and near_fg)

    if not runtime.active:
        status, next_action = "Inactive", "Start fermentation tracking"
    elif current_sg is None:
        status, next_action = "Waiting for gravity", "Record a gravity observation"
    elif ready_crash:
        status, next_action = "Ready for cold crash", "Confirm and start cold crash"
    elif ready_rise:
        status = "Temperature rise"
        next_action = "Raise fermentation temperature and continue daily gravity checks"
    else:
        status = "Primary fermentation"
        next_action = "Continue fermentation and record the next gravity observation"

    recommended_temp = None
    if runtime.active:
        recommended_temp = (
            runtime.temp_rise_temperature_c if ready_rise else runtime.primary_temperature_c
        )
    summary = f"{status} · no gravity observation"
    if current_sg is not None:
        parts = [status, f"SG {current_sg:.3f}"]
        if progress is not None:
            parts.append(f"{progress:.0f}%")
        if abv is not None:
            parts.append(f"ABV {abv:.2f}%")
        parts.append(stability["reason"])
        summary = " · ".join(parts)

    recent = [_sample_to_dict(sample) for sample in runtime.samples[-10:]]
    return {
        "active": runtime.active,
        "recipe_name": runtime.recipe_name or None,
        "status": status,
        "next_action": next_action,
        "summary": summary,
        "original_gravity": runtime.original_gravity,
        "target_final_gravity": runtime.target_final_gravity,
        "temp_rise_trigger_sg": runtime.temp_rise_trigger_sg,
        "current_sg": current_sg,
        "corrected_sg": current_sg,
        "gravity_source": current["source"] if current else None,
        "gravity_source_entity": current["entity"] if current else None,
        "gravity_observed_at": current["observed_at"].isoformat() if current else None,
        "measurement_type": current["measurement_type"] if current else None,
        "raw_value": current["raw_value"] if current else None,
        "raw_unit": current["raw_unit"] if current else None,
        "progress_percent": progress,
        "estimated_abv": abv,
        "gravity_stable": stability["stable"],
        "gravity_stability_state": "stable" if stability["stable"] else "not_stable",
        "stability_reason": stability["reason"],
        "stable_hours_required": runtime.stable_hours,
        "stability_tolerance_sg": runtime.stability_tolerance_sg,
        "stable_span_hours": stability["span_hours"],
        "stable_sample_count": stability["count"],
        "stable_min_sg": stability["min_sg"],
        "stable_max_sg": stability["max_sg"],
        "stable_delta_sg": stability["delta_sg"],
        "stable_since": stability["stable_since"],
        "near_target_fg": near_fg,
        "fg_tolerance_sg": runtime.fg_tolerance_sg,
        "ready_for_temp_rise": ready_rise,
        "temp_rise_readiness_state": "ready" if ready_rise else "not_ready",
        "ready_for_cold_crash": ready_crash,
        "cold_crash_readiness_state": "ready" if ready_crash else "not_ready",
        "primary_temperature_c": runtime.primary_temperature_c,
        "temp_rise_temperature_c": runtime.temp_rise_temperature_c,
        "recommended_temperature_c": recommended_temp,
        "wort_correction_factor": runtime.wort_correction_factor,
        "sample_count": len(runtime.samples),
        "recent_samples": recent,
        "started_at": runtime.started_at.isoformat() if runtime.started_at else None,
        "updated_at": runtime.updated_at.isoformat() if runtime.updated_at else None,
        "source_priority": "newest valid observation; manual wins timestamp ties",
        "storage_key": STORAGE_KEY,
    }


async def _refresh_coordinators(hass: HomeAssistant) -> None:
    for item in list(hass.data.get(DOMAIN, {}).values()):
        refresh = getattr(item, "async_request_refresh", None)
        if callable(refresh):
            await refresh()


async def async_setup_fermentation_runtime(hass: HomeAssistant) -> None:
    """Load storage and register the narrow fermentation service surface once."""
    data = hass.data.setdefault(DOMAIN, {})
    if not data.get(LOADED_KEY):
        await async_load_fermentation_runtime(hass)
    if hass.services.has_service(DOMAIN, SERVICE_START):
        return

    async def handle_start(call: ServiceCall) -> None:
        start_fermentation_runtime(hass, dict(call.data))
        await async_save_fermentation_runtime(hass)
        await _refresh_coordinators(hass)

    async def handle_update(call: ServiceCall) -> None:
        update_fermentation_runtime(hass, dict(call.data))
        await async_save_fermentation_runtime(hass)
        await _refresh_coordinators(hass)

    async def handle_record(call: ServiceCall) -> None:
        record_gravity_observation(hass, dict(call.data))
        await async_save_fermentation_runtime(hass)
        await _refresh_coordinators(hass)

    async def handle_reset(call: ServiceCall) -> None:
        reset_fermentation_runtime(hass)
        await async_save_fermentation_runtime(hass)
        await _refresh_coordinators(hass)

    hass.services.async_register(DOMAIN, SERVICE_START, handle_start)
    hass.services.async_register(DOMAIN, SERVICE_UPDATE, handle_update)
    hass.services.async_register(DOMAIN, SERVICE_RECORD, handle_record)
    hass.services.async_register(DOMAIN, SERVICE_RESET, handle_reset)
