"""BrewZilla learning and heat-utilization suggestion helpers.

This is intentionally advisory only. BrewAssistant observes BrewZilla behavior
and exposes suggested heat utilization plus diagnostics, but does not auto-apply
heat utilization changes.
"""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant, State
from homeassistant.util import dt as dt_util

from .brewday_runtime_core import build_core_snapshot

DATA_KEY = "brewzilla_learning"

BREWZILLA_TEMP_SENSOR = "sensor.brewzilla_temperature"
BREWZILLA_TARGET_NUMBER = "number.brewzilla_target_temperature"
BREWZILLA_POWER_SENSOR = "sensor.brewzilla_power"
BREWZILLA_HEATER_SWITCH = "switch.brewzilla_heater"
BREWZILLA_PUMP_SWITCH = "switch.brewzilla_pump"
BREWZILLA_HEAT_UTILIZATION = "number.brewzilla_heat_utilization"
BREWZILLA_PUMP_UTILIZATION = "number.brewzilla_pump_utilization"

_BAD = {None, "unknown", "unavailable", "none", ""}
_ACTIVE_STATES = {"live", "running", "paused", "awaiting_snapshot"}
_RAMP_WORDS = ("ramp", "heat", "värm", "uppvärm", "strike", "mash in", "mash-in")
_HOLD_WORDS = ("hold", "rest", "rast", "mash", "mäsk", "saccharification", "beta", "alpha")
_BOIL_WORDS = ("boil", "kok")
_COOL_WORDS = ("cool", "chill", "kyl")


def _state_obj(hass: HomeAssistant, entity_id: str) -> State | None:
    state = hass.states.get(entity_id)
    if state is None or state.state in _BAD:
        return None
    return state


def _state(hass: HomeAssistant, entity_id: str, default: str | None = None) -> str | None:
    state = _state_obj(hass, entity_id)
    return state.state if state is not None else default


def _float(hass: HomeAssistant, entity_id: str) -> float | None:
    raw = _state(hass, entity_id)
    try:
        if raw is None or str(raw).lower() in _BAD:
            return None
        return float(raw)
    except (TypeError, ValueError):
        return None


def _bool_state(hass: HomeAssistant, entity_id: str) -> bool:
    return str(_state(hass, entity_id, "off")).lower() in {"on", "true", "yes"}


def _age_seconds(state: State | None) -> int | None:
    if state is None:
        return None
    return max(0, int((dt_util.utcnow() - dt_util.as_utc(state.last_updated)).total_seconds()))


def _learning_store(hass: HomeAssistant) -> dict[str, Any]:
    return hass.data.setdefault("brewassistant", {}).setdefault(DATA_KEY, {})


def _stage_kind(runtime: dict[str, Any]) -> str:
    text = f"{runtime.get('stage') or ''} {runtime.get('step') or ''} {runtime.get('raw_step_name') or ''}".lower()
    if any(word in text for word in _COOL_WORDS):
        return "cooling"
    if any(word in text for word in _BOIL_WORDS):
        return "boil"
    if any(word in text for word in _RAMP_WORDS):
        return "ramp"
    if any(word in text for word in _HOLD_WORDS):
        return "mash_hold"
    return "unknown"


def _update_temperature_observation(hass: HomeAssistant, current_temperature: float | None) -> dict[str, Any]:
    """Update in-memory temperature observations and return trend diagnostics."""
    store = _learning_store(hass)
    temp_state = _state_obj(hass, BREWZILLA_TEMP_SENSOR)
    if temp_state is None or current_temperature is None:
        return {
            "temp_rate_c_per_min": None,
            "temp_rate_c_per_hour": None,
            "temp_observation_age_seconds": None,
            "previous_temperature": store.get("last_temperature"),
            "previous_temperature_at": store.get("last_temperature_at"),
        }

    observed_at = dt_util.as_utc(temp_state.last_updated)
    observed_at_iso = observed_at.isoformat()
    previous_at = store.get("last_temperature_at")
    previous_temp = store.get("last_temperature")
    rate_per_min = store.get("temp_rate_c_per_min")

    if previous_at != observed_at_iso:
        previous_dt = dt_util.parse_datetime(previous_at) if previous_at else None
        if previous_dt is not None and previous_temp is not None:
            seconds = max(1.0, (observed_at - dt_util.as_utc(previous_dt)).total_seconds())
            raw_rate = (current_temperature - float(previous_temp)) / (seconds / 60.0)
            rate_per_min = round(raw_rate, 3)
            store["temp_rate_c_per_min"] = rate_per_min
        store["previous_temperature"] = previous_temp
        store["previous_temperature_at"] = previous_at
        store["last_temperature"] = current_temperature
        store["last_temperature_at"] = observed_at_iso

    return {
        "temp_rate_c_per_min": rate_per_min,
        "temp_rate_c_per_hour": round(float(rate_per_min) * 60.0, 2) if rate_per_min is not None else None,
        "temp_observation_age_seconds": _age_seconds(temp_state),
        "previous_temperature": store.get("previous_temperature"),
        "previous_temperature_at": store.get("previous_temperature_at"),
        "last_temperature": store.get("last_temperature"),
        "last_temperature_at": store.get("last_temperature_at"),
    }


def _suggest_heat_utilization(
    *,
    runtime_state: str,
    stage_kind: str,
    current_temperature: float | None,
    target_temperature: float | None,
    temp_rate_c_per_min: float | None,
    heat_utilization: float | None,
    heater_on: bool,
) -> tuple[int | None, str, str, str]:
    """Return suggested heat utilization, confidence, phase and reason."""
    if runtime_state not in _ACTIVE_STATES:
        return None, "low", "standby", "Brewday runtime is not active."

    if stage_kind == "cooling":
        return 0, "high", "cooling", "Cooling stage detected; heat should remain unavailable."

    if stage_kind == "boil":
        return 100, "medium", "boil_ramp", "Boil stage detected; full heat is suggested until boil behavior has been profiled."

    if current_temperature is None or target_temperature is None:
        return None, "low", "unknown", "Missing current or target temperature."

    delta_to_target = target_temperature - current_temperature
    rate = temp_rate_c_per_min

    if delta_to_target > 5.0:
        return 100, "medium", "ramp_far", "More than 5°C below target; full heat is suggested for ramp efficiency."

    if delta_to_target > 2.0:
        if rate is not None and rate > 1.2:
            return 75, "medium", "ramp_approach_fast", "Approaching target quickly; reduce heat to limit overshoot risk."
        return 90, "medium", "ramp_approach", "2–5°C below target; keep high heat but prepare to taper."

    if delta_to_target > 0.7:
        if rate is not None and rate > 0.8:
            return 55, "medium", "near_target_fast", "Within 2°C and rising quickly; taper heat early."
        return 70, "medium", "near_target", "Within 2°C below target; moderate heat is suggested."

    if delta_to_target > 0.1:
        if rate is not None and rate > 0.4:
            return 35, "medium", "final_approach_fast", "Very close to target and still rising; use low heat to reduce overshoot."
        return 50, "medium", "final_approach", "Very close to target; low-to-moderate heat is suggested."

    if delta_to_target >= -0.3:
        if stage_kind == "mash_hold":
            return 40, "medium", "mash_hold", "At mash target; conservative heat is suggested for stability."
        return 45, "medium", "hold", "At target; conservative heat is suggested until profiling data improves."

    if delta_to_target < -0.3:
        return 0 if heater_on else min(int(heat_utilization or 0), 30), "medium", "overshoot", "Current temperature is above target; heat should be reduced or stopped."

    return None, "low", "unknown", "No suggestion available."


def build_brewzilla_learning_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    """Build BrewZilla learning/suggestion snapshot."""
    runtime = build_core_snapshot(hass)
    runtime_state = str(runtime.get("runtime_state") or "idle").lower()
    stage_kind = _stage_kind(runtime)

    current_temperature = _float(hass, BREWZILLA_TEMP_SENSOR)
    target_temperature = runtime.get("target_temperature")
    try:
        target_temperature = float(target_temperature) if target_temperature is not None else _float(hass, BREWZILLA_TARGET_NUMBER)
    except (TypeError, ValueError):
        target_temperature = _float(hass, BREWZILLA_TARGET_NUMBER)

    heat_utilization = _float(hass, BREWZILLA_HEAT_UTILIZATION)
    pump_utilization = _float(hass, BREWZILLA_PUMP_UTILIZATION)
    power_w = _float(hass, BREWZILLA_POWER_SENSOR)
    heater_on = _bool_state(hass, BREWZILLA_HEATER_SWITCH)
    pump_on = _bool_state(hass, BREWZILLA_PUMP_SWITCH)
    trend = _update_temperature_observation(hass, current_temperature)
    rate_per_min = trend.get("temp_rate_c_per_min")

    delta_to_target = None
    if current_temperature is not None and target_temperature is not None:
        delta_to_target = round(target_temperature - current_temperature, 2)

    suggestion, confidence, phase, reason = _suggest_heat_utilization(
        runtime_state=runtime_state,
        stage_kind=stage_kind,
        current_temperature=current_temperature,
        target_temperature=target_temperature,
        temp_rate_c_per_min=rate_per_min,
        heat_utilization=heat_utilization,
        heater_on=heater_on,
    )

    overshoot_risk = "unknown"
    if delta_to_target is not None and rate_per_min is not None:
        if delta_to_target < -0.3:
            overshoot_risk = "active_overshoot"
        elif delta_to_target < 1.0 and rate_per_min > 0.4:
            overshoot_risk = "high"
        elif delta_to_target < 2.0 and rate_per_min > 0.8:
            overshoot_risk = "medium"
        else:
            overshoot_risk = "low"

    heat_adjustment = None
    if suggestion is not None and heat_utilization is not None:
        heat_adjustment = int(round(suggestion - heat_utilization))

    return {
        "source": "brewzilla_learning",
        "mode": "observe_and_suggest",
        "runtime_state": runtime_state,
        "runtime_stage": runtime.get("stage"),
        "runtime_step": runtime.get("step"),
        "runtime_raw_step_name": runtime.get("raw_step_name"),
        "stage_kind": stage_kind,
        "phase": phase,
        "confidence": confidence,
        "current_temperature": current_temperature,
        "target_temperature": target_temperature,
        "delta_to_target": delta_to_target,
        "temp_rate_c_per_min": rate_per_min,
        "temp_rate_c_per_hour": trend.get("temp_rate_c_per_hour"),
        "temp_observation_age_seconds": trend.get("temp_observation_age_seconds"),
        "previous_temperature": trend.get("previous_temperature"),
        "previous_temperature_at": trend.get("previous_temperature_at"),
        "last_temperature": trend.get("last_temperature"),
        "last_temperature_at": trend.get("last_temperature_at"),
        "heater_on": heater_on,
        "pump_on": pump_on,
        "power_w": power_w,
        "heat_utilization": heat_utilization,
        "pump_utilization": pump_utilization,
        "suggested_heat_utilization": suggestion,
        "heat_adjustment": heat_adjustment,
        "overshoot_risk": overshoot_risk,
        "strategy_reason": reason,
        "auto_apply_allowed": False,
    }
