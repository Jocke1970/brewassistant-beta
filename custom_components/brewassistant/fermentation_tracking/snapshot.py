"""Normalized downstream snapshot for fermentation tracking."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant

from .calculations import estimated_abv, fermentation_progress
from .models import METRIC_GRAVITY, METRIC_TEMPERATURE
from .observations import automatic_candidate, manual_candidate, resolve_candidate, stability_snapshot
from .storage import STORAGE_KEY, get_runtime, observation_to_dict


def build_fermentation_snapshot(
    hass: HomeAssistant,
    *,
    external_sg: float | None = None,
    external_updated_at: datetime | None = None,
    external_entity: str | None = None,
    external_temperature_c: float | None = None,
    external_temperature_updated_at: datetime | None = None,
    external_temperature_entity: str | None = None,
) -> dict[str, Any]:
    """Return normalized SG and temperature regardless of measurement source."""
    runtime = get_runtime(hass)
    gravity = resolve_candidate(
        runtime.gravity_source_mode,
        manual_candidate(runtime, METRIC_GRAVITY),
        automatic_candidate(
            metric=METRIC_GRAVITY,
            value=external_sg,
            updated_at=external_updated_at,
            entity=external_entity,
        ),
    )
    temperature = resolve_candidate(
        runtime.temperature_source_mode,
        manual_candidate(runtime, METRIC_TEMPERATURE),
        automatic_candidate(
            metric=METRIC_TEMPERATURE,
            value=external_temperature_c,
            updated_at=external_temperature_updated_at,
            entity=external_temperature_entity,
        ),
    )

    current_sg = gravity["value"] if gravity else None
    current_temperature = temperature["value"] if temperature else None
    stability = stability_snapshot(runtime)
    progress = fermentation_progress(
        runtime.original_gravity,
        runtime.target_final_gravity,
        current_sg,
    )
    abv = estimated_abv(runtime.original_gravity, current_sg)
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
        status, next_action = "Waiting for gravity", "Record or connect a gravity observation"
    elif ready_crash:
        status, next_action = "Ready for cold crash", "Confirm and start cold crash"
    elif ready_rise:
        status = "Temperature rise"
        next_action = "Raise fermentation temperature and continue gravity checks"
    else:
        status = "Primary fermentation"
        next_action = "Continue fermentation and record the next gravity observation"

    recommended_temperature = None
    if runtime.active:
        recommended_temperature = (
            runtime.temp_rise_temperature_c if ready_rise else runtime.primary_temperature_c
        )

    summary_parts = [status]
    if current_sg is not None:
        summary_parts.append(f"SG {current_sg:.3f}")
    if current_temperature is not None:
        summary_parts.append(f"{current_temperature:.1f} °C")
    if progress is not None:
        summary_parts.append(f"{progress:.0f}%")
    if abv is not None:
        summary_parts.append(f"ABV {abv:.2f}%")
    summary_parts.append(stability["reason"])

    recent = [observation_to_dict(item) for item in runtime.observations[-20:]]
    gravity_count = sum(item.metric == METRIC_GRAVITY for item in runtime.observations)
    temperature_count = sum(item.metric == METRIC_TEMPERATURE for item in runtime.observations)

    return {
        "active": runtime.active,
        "recipe_name": runtime.recipe_name or None,
        "status": status,
        "next_action": next_action,
        "summary": " · ".join(summary_parts),
        "original_gravity": runtime.original_gravity,
        "target_final_gravity": runtime.target_final_gravity,
        "temp_rise_trigger_sg": runtime.temp_rise_trigger_sg,
        "current_sg": current_sg,
        "corrected_sg": current_sg,
        "gravity_source_mode": runtime.gravity_source_mode,
        "gravity_source_type": gravity["source_type"] if gravity else None,
        "gravity_source": gravity["source"] if gravity else None,
        "gravity_source_entity": gravity["entity"] if gravity else None,
        "gravity_observed_at": gravity["observed_at"].isoformat() if gravity else None,
        "gravity_measurement_method": gravity["measurement_method"] if gravity else None,
        "gravity_raw_value": gravity["raw_value"] if gravity else None,
        "gravity_raw_unit": gravity["raw_unit"] if gravity else None,
        "gravity_calculation_input_brix": gravity["calculation_input_brix"] if gravity else None,
        "current_temperature_c": current_temperature,
        "temperature_source_mode": runtime.temperature_source_mode,
        "temperature_source_type": temperature["source_type"] if temperature else None,
        "temperature_source": temperature["source"] if temperature else None,
        "temperature_source_entity": temperature["entity"] if temperature else None,
        "temperature_observed_at": temperature["observed_at"].isoformat() if temperature else None,
        "temperature_measurement_method": temperature["measurement_method"] if temperature else None,
        "temperature_raw_value": temperature["raw_value"] if temperature else None,
        "temperature_raw_unit": temperature["raw_unit"] if temperature else None,
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
        "recommended_temperature_c": recommended_temperature,
        "wort_correction_factor": runtime.wort_correction_factor,
        "observation_count": len(runtime.observations),
        "sample_count": gravity_count,
        "temperature_observation_count": temperature_count,
        "recent_observations": recent,
        "recent_samples": [item for item in recent if item.get("metric") == METRIC_GRAVITY],
        "started_at": runtime.started_at.isoformat() if runtime.started_at else None,
        "updated_at": runtime.updated_at.isoformat() if runtime.updated_at else None,
        "source_priority": "per-metric policy; hybrid uses newest valid and manual wins timestamp ties",
        "stability_source": "persisted gravity observations",
        "storage_key": STORAGE_KEY,
        "backend": "fermentation_tracking",
    }
