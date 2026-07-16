"""Persistent BrewZilla equipment learning model.

This layer turns Brewday/BrewZilla observations into an equipment-specific
profile model.  It does not change active control values automatically; it
records evidence, aggregates it into phase/volume/grain buckets, and surfaces
profile suggestions that can be reviewed before any future apply step.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from ..brewday.brewday_runtime import build_brewday_runtime_snapshot
from ..const import DOMAIN
from .brewzilla_learning import build_brewzilla_learning_snapshot

DATA_KEY = "brewzilla_equipment_learning"
STORAGE_KEY = f"{DOMAIN}_{DATA_KEY}"
STORAGE_VERSION = 1
AUTO_SAMPLE_INTERVAL = timedelta(seconds=30)
MAX_RECENT_OBSERVATIONS = 120
ACTIVE_STATES = {"live", "running", "paused", "prepared", "awaiting_snapshot", "awaiting_confirm"}
LEARNING_STAGES = {"ramp", "mash_hold", "boil"}


def _new_model() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "enabled": True,
        "mode": "observe_profile_suggest_apply_later",
        "equipment_id": "brewzilla_gen4_35l",
        "observations_total": 0,
        "segment_models": {},
        "recent_observations": [],
        "last_observation": None,
        "last_suggestion": None,
        "last_record_result": None,
        "last_saved_at": None,
        "updated_at": None,
    }


def _store_data(hass: HomeAssistant) -> dict[str, Any]:
    domain = hass.data.setdefault(DOMAIN, {})
    runtime = domain.setdefault(DATA_KEY, {})
    model = runtime.setdefault("model", _new_model())
    model.setdefault("schema_version", 1)
    model.setdefault("enabled", True)
    model.setdefault("mode", "observe_profile_suggest_apply_later")
    model.setdefault("equipment_id", "brewzilla_gen4_35l")
    model.setdefault("observations_total", 0)
    model.setdefault("segment_models", {})
    model.setdefault("recent_observations", [])
    return model


def _storage(hass: HomeAssistant) -> Store[dict[str, Any]]:
    domain = hass.data.setdefault(DOMAIN, {})
    runtime = domain.setdefault(DATA_KEY, {})
    store = runtime.get("store")
    if store is None:
        store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        runtime["store"] = store
    return store


async def async_setup_equipment_learning(hass: HomeAssistant) -> None:
    """Load the persistent model and start passive observation."""
    domain = hass.data.setdefault(DOMAIN, {})
    runtime = domain.setdefault(DATA_KEY, {})
    if runtime.get("setup_complete"):
        return

    stored = await _storage(hass).async_load()
    runtime["model"] = stored if isinstance(stored, dict) else _new_model()
    runtime["setup_complete"] = True

    async def _auto_tick(_now) -> None:
        await async_record_equipment_learning_observation(hass, reason="auto")

    runtime["unsub_auto_observer"] = async_track_time_interval(hass, _auto_tick, AUTO_SAMPLE_INTERVAL)


async def async_save_equipment_learning_model(hass: HomeAssistant) -> None:
    """Persist the current learning model."""
    model = _store_data(hass)
    model["last_saved_at"] = dt_util.utcnow().isoformat()
    await _storage(hass).async_save(model)


async def async_reset_equipment_learning_model(hass: HomeAssistant) -> dict[str, Any]:
    """Reset the persistent equipment model."""
    domain = hass.data.setdefault(DOMAIN, {})
    runtime = domain.setdefault(DATA_KEY, {})
    runtime["model"] = _new_model()
    await async_save_equipment_learning_model(hass)
    return {"reset": True, "source": DATA_KEY, "observations_total": 0}


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _bucket(value: float | None, *, cuts: tuple[float, ...], prefix: str, unit: str) -> str:
    if value is None:
        return f"{prefix}:unknown"
    low = 0.0
    for cut in cuts:
        if value < cut:
            return f"{prefix}:{low:g}-{cut:g}{unit}"
        low = cut
    return f"{prefix}:{low:g}+{unit}"


def _stage_kind(runtime: dict[str, Any], advice: dict[str, Any]) -> str:
    stage_kind = str(advice.get("stage_kind") or "unknown")
    if stage_kind != "unknown":
        return stage_kind
    text = f"{runtime.get('stage') or ''} {runtime.get('step') or ''} {runtime.get('raw_step_name') or ''}".lower()
    if any(word in text for word in ("boil", "kok")):
        return "boil"
    if any(word in text for word in ("ramp", "heat", "värm", "strike")):
        return "ramp"
    if any(word in text for word in ("hold", "mash", "mäsk", "rest", "rast")):
        return "mash_hold"
    return "unknown"


def _profile_key(model: dict[str, Any], advice: dict[str, Any], stage_kind: str) -> str:
    context = str(advice.get("learning_context") or "Unknown")
    mash_water = _num(advice.get("mash_water_l") or advice.get("pre_boil_volume_l"))
    grain = _num(advice.get("grain_amount_kg"))
    volume_bucket = _bucket(mash_water, cuts=(8.0, 10.0, 13.0, 16.0, 20.0), prefix="vol", unit="L")
    grain_bucket = _bucket(grain, cuts=(2.0, 3.0, 5.0, 7.0), prefix="grain", unit="kg")
    return "|".join((str(model.get("equipment_id") or "brewzilla"), context, volume_bucket, grain_bucket, stage_kind))


def _observation_signature(obs: dict[str, Any]) -> str:
    return "|".join(
        str(obs.get(key))
        for key in (
            "runtime_state",
            "stage",
            "step",
            "target_temperature",
            "mash_temperature",
            "wort_temperature",
            "heat_utilization",
            "pump_utilization",
        )
    )


def _build_observation(hass: HomeAssistant, *, reason: str) -> dict[str, Any] | None:
    runtime = build_brewday_runtime_snapshot(hass)
    runtime_state = str(runtime.get("runtime_state") or runtime.get("status") or "idle").lower()
    advice = build_brewzilla_learning_snapshot(hass)
    stage_kind = _stage_kind(runtime, advice)
    if runtime_state not in ACTIVE_STATES or stage_kind not in LEARNING_STAGES:
        return None

    target = _num(advice.get("target_temperature") or runtime.get("target_temperature"))
    mash = _num(advice.get("mash_temperature"))
    wort = _num(advice.get("wort_temperature"))
    heat = _num(advice.get("heat_utilization"))
    pump = _num(advice.get("pump_utilization"))
    rate = _num(advice.get("temp_rate_c_per_min"))
    if target is None or (mash is None and wort is None):
        return None

    now = dt_util.utcnow().isoformat()
    mash_gap = round(target - mash, 2) if mash is not None else None
    wort_over = round(wort - target, 2) if wort is not None else None
    mash_wort_lag = round(wort - mash, 2) if mash is not None and wort is not None else None
    return {
        "observed_at": now,
        "reason": reason,
        "runtime_state": runtime_state,
        "status": runtime.get("status"),
        "stage": runtime.get("stage"),
        "step": runtime.get("step"),
        "next_step": runtime.get("next_step"),
        "stage_kind": stage_kind,
        "learning_context": advice.get("learning_context"),
        "batch_context_source": advice.get("batch_context_source"),
        "grain_amount_kg": advice.get("grain_amount_kg"),
        "mash_water_l": advice.get("mash_water_l"),
        "pre_boil_volume_l": advice.get("pre_boil_volume_l"),
        "target_temperature": target,
        "mash_temperature": mash,
        "wort_temperature": wort,
        "mash_gap_to_target": mash_gap,
        "wort_over_target": wort_over,
        "mash_wort_lag": mash_wort_lag,
        "heat_utilization": heat,
        "pump_utilization": pump,
        "heater_on": advice.get("heater_on"),
        "pump_on": advice.get("pump_on"),
        "temp_rate_c_per_min": rate,
        "overshoot_risk": advice.get("overshoot_risk"),
        "advice_phase": advice.get("phase"),
        "suggested_heat_utilization": advice.get("suggested_heat_utilization"),
        "advice_local_profile_heat_utilization": advice.get("advice_local_profile_heat_utilization"),
        "advice_thermal_mix_active": advice.get("advice_thermal_mix_active"),
        "advice_thermal_mix_heat_cap": advice.get("advice_thermal_mix_heat_cap"),
        "advice_thermal_mix_reason": advice.get("advice_thermal_mix_reason"),
        "signature": "",
    }


def _avg_metric(segment: dict[str, Any], key: str, value: float | None) -> None:
    if value is None:
        return
    counts = segment.setdefault("metric_counts", {})
    n = int(counts.get(key) or 0)
    previous = _num(segment.get(key)) or 0.0
    segment[key] = round(((previous * n) + float(value)) / (n + 1), 3)
    counts[key] = n + 1


def _heat_bucket(value: float | None) -> str | None:
    if value is None:
        return None
    return f"{int(round(float(value) / 10.0) * 10):03d}%"


def _update_segment(segment: dict[str, Any], obs: dict[str, Any]) -> None:
    count = int(segment.get("count") or 0) + 1
    segment["count"] = count
    segment.setdefault("first_seen_at", obs.get("observed_at"))
    segment["last_seen_at"] = obs.get("observed_at")
    segment["last_stage"] = obs.get("stage")
    segment["last_step"] = obs.get("step")
    segment["stage_kind"] = obs.get("stage_kind")
    segment["learning_context"] = obs.get("learning_context")

    _avg_metric(segment, "avg_mash_wort_lag_c", _num(obs.get("mash_wort_lag")))
    _avg_metric(segment, "avg_temp_rate_c_per_min", _num(obs.get("temp_rate_c_per_min")))
    _avg_metric(segment, "avg_mash_gap_to_target_c", _num(obs.get("mash_gap_to_target")))
    _avg_metric(segment, "avg_wort_over_target_c", _num(obs.get("wort_over_target")))

    mash_gap = _num(obs.get("mash_gap_to_target"))
    wort_over = _num(obs.get("wort_over_target"))
    if mash_gap is not None and mash_gap < 0:
        segment["max_mash_overshoot_c"] = max(float(segment.get("max_mash_overshoot_c") or 0.0), abs(mash_gap))
    if wort_over is not None and wort_over > 0:
        segment["max_wort_over_target_c"] = max(float(segment.get("max_wort_over_target_c") or 0.0), wort_over)

    heat_bucket = _heat_bucket(_num(obs.get("heat_utilization")))
    rate = _num(obs.get("temp_rate_c_per_min"))
    if heat_bucket and rate is not None:
        by_heat = segment.setdefault("rate_by_heat_utilization", {})
        entry = by_heat.setdefault(heat_bucket, {"count": 0, "avg_temp_rate_c_per_min": 0.0})
        n = int(entry.get("count") or 0)
        previous = _num(entry.get("avg_temp_rate_c_per_min")) or 0.0
        entry["avg_temp_rate_c_per_min"] = round(((previous * n) + rate) / (n + 1), 3)
        entry["count"] = n + 1

    if bool(obs.get("advice_thermal_mix_active")) and (_num(obs.get("advice_local_profile_heat_utilization")) or 0.0) <= 10.0:
        segment["thermal_mix_low_cap_cases"] = int(segment.get("thermal_mix_low_cap_cases") or 0) + 1


def _suggestion(model: dict[str, Any], segment: dict[str, Any], obs: dict[str, Any], profile_key: str) -> dict[str, Any] | None:
    context = str(obs.get("learning_context") or "Unknown")
    stage_kind = str(obs.get("stage_kind") or "unknown")
    mash_gap = _num(obs.get("mash_gap_to_target"))
    wort_over = _num(obs.get("wort_over_target"))
    profile_heat = _num(obs.get("advice_local_profile_heat_utilization"))
    suggested_heat = _num(obs.get("suggested_heat_utilization"))
    thermal_mix_active = bool(obs.get("advice_thermal_mix_active"))

    if (
        context == "Real mash"
        and stage_kind in {"ramp", "mash_hold"}
        and thermal_mix_active
        and mash_gap is not None
        and mash_gap >= 2.0
        and wort_over is not None
        and wort_over < 5.0
        and profile_heat is not None
        and profile_heat <= 10.0
        and (suggested_heat is None or suggested_heat >= 70.0)
    ):
        floor = 45.0 if stage_kind == "ramp" else 30.0
        confidence = "high" if int(segment.get("thermal_mix_low_cap_cases") or 0) >= 5 else "medium"
        return {
            "suggestion_id": f"thermal_mix_floor:{profile_key}:{stage_kind}",
            "type": "profile_adjustment",
            "status": "candidate_requires_operator_apply",
            "confidence": confidence,
            "profile_key": profile_key,
            "phase": stage_kind,
            "parameter": f"thermal_mix.{stage_kind}_mash_priority_floor",
            "current_observed_cap": profile_heat,
            "suggested_floor": floor,
            "evidence_count": segment.get("thermal_mix_low_cap_cases"),
            "reason": (
                "Mash temperature is still at least 2°C below target while the wort/internal sensor is only moderately above target. "
                "Keep wort/internal as a safety limiter, but do not let it collapse real-mash ramp/hold heat to a 5–10% cap."
            ),
            "last_observation": {
                "target_temperature": obs.get("target_temperature"),
                "mash_temperature": obs.get("mash_temperature"),
                "wort_temperature": obs.get("wort_temperature"),
                "mash_gap_to_target": obs.get("mash_gap_to_target"),
                "wort_over_target": obs.get("wort_over_target"),
            },
        }

    return None


async def async_record_equipment_learning_observation(hass: HomeAssistant, *, reason: str = "manual") -> dict[str, Any]:
    """Record one equipment-learning observation and update profile evidence."""
    model = _store_data(hass)
    if not bool(model.get("enabled", True)):
        return {"recorded": False, "reason": "disabled", "source": DATA_KEY}

    obs = _build_observation(hass, reason=reason)
    if obs is None:
        result = {"recorded": False, "reason": "no_active_learning_context", "source": DATA_KEY}
        model["last_record_result"] = result
        return result

    obs["signature"] = _observation_signature(obs)
    if reason == "auto" and model.get("last_observation", {}).get("signature") == obs["signature"]:
        result = {"recorded": False, "reason": "duplicate_snapshot", "source": DATA_KEY}
        model["last_record_result"] = result
        return result

    profile_key = _profile_key(model, obs, str(obs.get("stage_kind") or "unknown"))
    segment = model.setdefault("segment_models", {}).setdefault(profile_key, {"profile_key": profile_key})
    _update_segment(segment, obs)

    model["observations_total"] = int(model.get("observations_total") or 0) + 1
    model["last_observation"] = obs
    model["updated_at"] = obs.get("observed_at")
    recent = model.setdefault("recent_observations", [])
    recent.append(obs)
    del recent[:-MAX_RECENT_OBSERVATIONS]

    suggestion = _suggestion(model, segment, obs, profile_key)
    if suggestion is not None:
        suggestion["created_at"] = obs.get("observed_at")
        model["last_suggestion"] = suggestion

    result = {
        "recorded": True,
        "source": DATA_KEY,
        "reason": reason,
        "profile_key": profile_key,
        "observations_total": model["observations_total"],
        "segment_count": segment.get("count"),
        "suggestion": suggestion,
    }
    model["last_record_result"] = result

    if reason != "auto" or suggestion is not None or model["observations_total"] % 5 == 0:
        await async_save_equipment_learning_model(hass)

    return result


def build_equipment_learning_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    """Return current equipment-learning state for sensors/debug cards."""
    model = _store_data(hass)
    segments = model.get("segment_models") if isinstance(model.get("segment_models"), dict) else {}
    last_suggestion = model.get("last_suggestion") if isinstance(model.get("last_suggestion"), dict) else None
    last_observation = model.get("last_observation") if isinstance(model.get("last_observation"), dict) else None
    current_key = None
    current_segment = None
    try:
        obs = _build_observation(hass, reason="snapshot")
        if obs is not None:
            current_key = _profile_key(model, obs, str(obs.get("stage_kind") or "unknown"))
            current_segment = segments.get(current_key)
    except Exception:  # pragma: no cover - diagnostics must never break sensors
        current_key = None
        current_segment = None

    summary = f"{int(model.get('observations_total') or 0)} observations · {len(segments)} profile segments"
    if last_suggestion:
        summary = f"{summary} · suggestion: {last_suggestion.get('parameter')} → {last_suggestion.get('suggested_floor')}"

    return {
        "source": DATA_KEY,
        "mode": model.get("mode"),
        "enabled": bool(model.get("enabled", True)),
        "summary": summary,
        "equipment_id": model.get("equipment_id"),
        "observations_total": int(model.get("observations_total") or 0),
        "segment_count": len(segments),
        "current_profile_key": current_key,
        "current_segment_count": current_segment.get("count") if isinstance(current_segment, dict) else None,
        "last_observation_at": last_observation.get("observed_at") if last_observation else None,
        "last_observation": deepcopy(last_observation),
        "last_suggestion": deepcopy(last_suggestion),
        "last_record_result": deepcopy(model.get("last_record_result")),
        "updated_at": model.get("updated_at"),
        "last_saved_at": model.get("last_saved_at"),
        "segments": deepcopy(segments),
    }
