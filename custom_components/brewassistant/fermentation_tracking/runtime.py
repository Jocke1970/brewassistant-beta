"""Runtime lifecycle and Home Assistant services for fermentation tracking."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from homeassistant.core import HomeAssistant, ServiceCall

from ..const import DOMAIN
from .calculations import valid_sg, valid_temperature
from .models import SOURCE_MODE_HYBRID, SOURCE_MODES, FermentationRuntime
from .observations import record_manual_observation
from .recalculation import recalculate_refractometer_observations
from .snapshot import build_fermentation_snapshot
from .storage import (
    LOADED_KEY,
    as_datetime,
    as_float,
    async_load,
    async_save,
    get_runtime,
    set_runtime,
)

SERVICE_START = "fermentation_start"
SERVICE_UPDATE = "fermentation_update"
SERVICE_RECORD_OBSERVATION = "fermentation_record_observation"
SERVICE_RECORD_GRAVITY = "fermentation_record_gravity"
SERVICE_RESET = "fermentation_reset"


def _update(runtime: FermentationRuntime, data: dict[str, Any]) -> None:
    if "recipe_name" in data:
        runtime.recipe_name = str(data.get("recipe_name") or "")

    sg_updates: dict[str, float | None] = {}
    for key in ("original_gravity", "target_final_gravity", "temp_rise_trigger_sg"):
        if key not in data:
            continue
        raw = data.get(key)
        if raw in {None, ""}:
            sg_updates[key] = None
            continue
        value = as_float(raw)
        if not valid_sg(value):
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
        if key not in data:
            continue
        raw = data.get(key)
        if raw in {None, ""}:
            setattr(runtime, key, None)
            continue
        value = as_float(raw)
        if not valid_temperature(value):
            raise ValueError(f"{key} must be between -5 and 50 °C")
        setattr(runtime, key, round(float(value), 1))

    limits = {
        "stable_hours": (1.0, 720.0, 1),
        "stability_tolerance_sg": (0.0001, 0.010, 4),
        "fg_tolerance_sg": (0.0001, 0.020, 4),
        "wort_correction_factor": (0.5, 1.5, 3),
    }
    for key, (low, high, digits) in limits.items():
        if key not in data:
            continue
        value = as_float(data.get(key))
        if value is None or not low <= value <= high:
            raise ValueError(f"{key} must be between {low} and {high}")
        setattr(runtime, key, round(value, digits))

    for key in ("gravity_source_mode", "temperature_source_mode"):
        if key not in data:
            continue
        mode = str(data.get(key) or SOURCE_MODE_HYBRID).lower().strip()
        if mode not in SOURCE_MODES:
            raise ValueError(f"{key} must be one of {sorted(SOURCE_MODES)}")
        setattr(runtime, key, mode)

    if "started_at" in data:
        started_at = as_datetime(data.get("started_at"))
        if started_at is None:
            raise ValueError("started_at must be a valid datetime")
        runtime.started_at = started_at
    runtime.updated_at = datetime.now(timezone.utc)


def get_fermentation_runtime(hass: HomeAssistant) -> FermentationRuntime:
    """Return the current tracking runtime."""
    return get_runtime(hass)


async def async_load_fermentation_runtime(hass: HomeAssistant) -> FermentationRuntime:
    """Load tracking state from Home Assistant Storage."""
    return await async_load(hass)


async def async_save_fermentation_runtime(hass: HomeAssistant) -> None:
    """Persist tracking state."""
    await async_save(hass)


def start_fermentation_runtime(hass: HomeAssistant, data: dict[str, Any]) -> FermentationRuntime:
    """Start a fresh tracking session without requiring recipe metadata."""
    runtime = FermentationRuntime()
    _update(runtime, data)
    runtime.active = True
    runtime.started_at = runtime.started_at or datetime.now(timezone.utc)
    set_runtime(hass, runtime)
    return runtime


def update_fermentation_runtime(hass: HomeAssistant, data: dict[str, Any]) -> FermentationRuntime:
    """Update configuration atomically and recalculate derived readings."""
    candidate = deepcopy(get_runtime(hass))
    _update(candidate, data)
    recalculate_refractometer_observations(candidate)
    set_runtime(hass, candidate)
    return candidate


def reset_fermentation_runtime(hass: HomeAssistant) -> FermentationRuntime:
    """Clear tracking configuration and observations."""
    runtime = FermentationRuntime()
    set_runtime(hass, runtime)
    return runtime


def record_fermentation_observation(hass: HomeAssistant, data: dict[str, Any]):
    """Record one manual SG and/or temperature observation."""
    return record_manual_observation(hass, data)


def record_gravity_observation(hass: HomeAssistant, data: dict[str, Any]):
    """Compatibility alias for the former gravity-only service."""
    translated = dict(data)
    if "measurement_type" in translated and "gravity_method" not in translated:
        translated["gravity_method"] = translated["measurement_type"]
    if "value" in translated and "gravity_value" not in translated:
        translated["gravity_value"] = translated["value"]
    if "measured_at" in translated and "observed_at" not in translated:
        translated["observed_at"] = translated["measured_at"]
    return record_manual_observation(hass, translated)


async def _refresh_coordinators(hass: HomeAssistant) -> None:
    for item in list(hass.data.get(DOMAIN, {}).values()):
        refresh = getattr(item, "async_request_refresh", None)
        if callable(refresh):
            await refresh()


async def async_setup_fermentation_runtime(hass: HomeAssistant) -> None:
    """Load storage and register the independent tracking service surface once."""
    data = hass.data.setdefault(DOMAIN, {})
    if not data.get(LOADED_KEY):
        await async_load(hass)

    async def handle_start(call: ServiceCall) -> None:
        start_fermentation_runtime(hass, dict(call.data))
        await async_save(hass)
        await _refresh_coordinators(hass)

    async def handle_update(call: ServiceCall) -> None:
        update_fermentation_runtime(hass, dict(call.data))
        await async_save(hass)
        await _refresh_coordinators(hass)

    async def handle_record(call: ServiceCall) -> None:
        record_fermentation_observation(hass, dict(call.data))
        await async_save(hass)
        await _refresh_coordinators(hass)

    async def handle_legacy_record(call: ServiceCall) -> None:
        record_gravity_observation(hass, dict(call.data))
        await async_save(hass)
        await _refresh_coordinators(hass)

    async def handle_reset(call: ServiceCall) -> None:
        reset_fermentation_runtime(hass)
        await async_save(hass)
        await _refresh_coordinators(hass)

    services = {
        SERVICE_START: handle_start,
        SERVICE_UPDATE: handle_update,
        SERVICE_RECORD_OBSERVATION: handle_record,
        SERVICE_RECORD_GRAVITY: handle_legacy_record,
        SERVICE_RESET: handle_reset,
    }
    for service_name, handler in services.items():
        if not hass.services.has_service(DOMAIN, service_name):
            hass.services.async_register(DOMAIN, service_name, handler)


__all__ = [
    "async_load_fermentation_runtime",
    "async_save_fermentation_runtime",
    "async_setup_fermentation_runtime",
    "build_fermentation_snapshot",
    "get_fermentation_runtime",
    "record_fermentation_observation",
    "record_gravity_observation",
    "reset_fermentation_runtime",
    "start_fermentation_runtime",
    "update_fermentation_runtime",
]
