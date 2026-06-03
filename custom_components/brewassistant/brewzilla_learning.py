"""BrewZilla learning and operator-confirmed recommendations.

This module is intentionally advisory. BrewAssistant observes BrewZilla behavior,
creates one pending recommendation at a time, and only executes changes after
explicit operator APPLY. DENY marks the recommendation as skipped and snoozes the
same recommendation for a short period.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant, State
from homeassistant.util import dt as dt_util

from .brewday_runtime_core import build_core_snapshot
from .brewzilla_temperature import brewzilla_temperature_snapshot

DATA_KEY = "brewzilla_learning"

BREWZILLA_INTERNAL_TEMP_SENSOR = "sensor.brewzilla_temperature"
BREWZILLA_MASH_TEMP_SENSOR = "sensor.brewzilla_ble_thermometer_temperature"
BREWZILLA_CONTROL_DEVICE_TEMP_SENSOR = "sensor.brewzilla_control_device_temperature"

# Backwards compatibility name. This now means internal/wort/kettle temperature.
BREWZILLA_TEMP_SENSOR = BREWZILLA_INTERNAL_TEMP_SENSOR
BREWZILLA_TARGET_NUMBER = "number.brewzilla_target_temperature"
BREWZILLA_POWER_SENSOR = "sensor.brewzilla_power"
BREWZILLA_HEATER_SWITCH = "switch.brewzilla_heater"
BREWZILLA_PUMP_SWITCH = "switch.brewzilla_pump"
BREWZILLA_HEAT_UTILIZATION = "number.brewzilla_heat_utilization"
BREWZILLA_PUMP_UTILIZATION = "number.brewzilla_pump_utilization"
BREWZILLA_LEARNING_CONTEXT_SELECT = "select.brewassistant_brewzilla_learning_context"

_BAD = {None, "unknown", "unavailable", "none", ""}
_ACTIVE_STATES = {"live", "running", "paused", "awaiting_snapshot"}
_RAMP_WORDS = ("ramp", "heat", "värm", "uppvärm", "strike", "mash in", "mash-in")
_HOLD_WORDS = ("hold", "rest", "rast", "mash", "mäsk", "saccharification", "beta", "alpha")
_BOIL_WORDS = ("boil", "kok", "boiling", "heating to boil", "värm till kok", "kokning", "kokgiva")
_COOL_WORDS = ("cool", "chill", "kyl")
_CONTEXT_OPTIONS = {"Unknown", "Water only", "Real mash"}
MIN_RECOMMENDATION_DIFF = 5
DENY_SNOOZE_SECONDS = 15 * 60


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
    return hass.data.setdefault("brewassistant", {}).setdefault(
        DATA_KEY,
        {
            "enabled": True,
            "pending": None,
            "last_applied": None,
            "last_denied": None,
            "denied_until": {},
            "observation_count": 0,
        },
    )


def learning_context(hass: HomeAssistant) -> str:
    """Return selected BrewZilla learning context."""
    selected = _state(hass, BREWZILLA_LEARNING_CONTEXT_SELECT, "Unknown")
    if selected not in _CONTEXT_OPTIONS:
        return "Unknown"
    return str(selected)


def _context_bias(context: str) -> dict[str, Any]:
    """Return learning modifiers for the selected context."""
    if context == "Water only":
        return {
            "profile_weight": 0.25,
            "confidence_cap": "medium",
            "suggestion_bias": -5,
            "note": " Water-only run: observations are useful for plumbing/poll/sensor sanity, but heat learning is optimistic versus a real mash.",
        }
    if context == "Real mash":
        return {
            "profile_weight": 1.0,
            "confidence_cap": "high",
            "suggestion_bias": 0,
            "note": " Real mash context: observations may be used as higher-value profile data.",
        }
    return {
        "profile_weight": 0.5,
        "confidence_cap": "medium",
        "suggestion_bias": 0,
        "note": " Learning context is unknown; suggestions stay conservative until context is set.",
    }


def _cap_confidence(confidence: str, cap: str) -> str:
    order = {"low": 0, "medium": 1, "high": 2}
    reverse = {0: "low", 1: "medium", 2: "high"}
    return reverse[min(order.get(confidence, 0), order.get(cap, 1))]


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


def _pump_mixing_state(stage_kind: str, pump_on: bool, pump_utilization: float | None) -> str:
    """Return how trustworthy thermal mixing likely is for learning."""
    if stage_kind not in {"ramp", "mash_hold"}:
        return "not_relevant"
    if not pump_on:
        return "off"
    if pump_utilization is None:
        return "unknown"
    if pump_utilization < 20:
        return "very_low"
    if pump_utilization < 40:
        return "low"
    if pump_utilization > 85:
        return "high"
    return "normal"


def _pump_heat_bias(stage_kind: str, pump_on: bool, pump_utilization: float | None) -> int:
    """Return a conservative heat bias based on pump/mixing condition."""
    mixing = _pump_mixing_state(stage_kind, pump_on, pump_utilization)
    if mixing == "off":
        return -25
    if mixing == "very_low":
        return -20
    if mixing == "low":
        return -10
    return 0


def _apply_heat_biases(suggestion: int, pump_bias: int, context_bias: int) -> int:
    return max(0, min(100, int(round(suggestion + pump_bias + context_bias))))


def _round5(value: float) -> int:
    return max(0, min(100, int(round(value / 5.0) * 5)))



def _temperature_source_snapshot(hass: HomeAssistant, stage_kind: str) -> dict[str, Any]:
    """Resolve mash, wort and effective learning temperatures."""
    snapshot = brewzilla_temperature_snapshot(hass)
    learning_temperature = snapshot.get("mash_temperature")
    learning_entity = snapshot.get("mash_temperature_entity")
    learning_source = snapshot.get("mash_temperature_source")
    learning_role = "mash_temperature"

    if stage_kind not in {"ramp", "mash_hold"}:
        learning_temperature = snapshot.get("wort_temperature")
        learning_entity = snapshot.get("wort_temperature_entity")
        learning_source = snapshot.get("wort_temperature_source")
        learning_role = "wort_or_kettle_temperature"

    if learning_temperature is None:
        learning_temperature = snapshot.get("mash_temperature") or snapshot.get("wort_temperature")
        learning_entity = snapshot.get("mash_temperature_entity") or snapshot.get("wort_temperature_entity")
        learning_source = snapshot.get("mash_temperature_source") or snapshot.get("wort_temperature_source")
        learning_role = "fallback_temperature"

    return {
        "mash_temperature": snapshot.get("mash_temperature"),
        "mash_temperature_entity": snapshot.get("mash_temperature_entity"),
        "mash_temperature_source": snapshot.get("mash_temperature_source"),
        "wort_temperature": snapshot.get("wort_temperature"),
        "wort_temperature_entity": snapshot.get("wort_temperature_entity"),
        "wort_temperature_source": snapshot.get("wort_temperature_source"),
        "temperature_delta_mash_wort": snapshot.get("temperature_delta_mash_wort"),
        "learning_temperature": learning_temperature,
        "learning_temperature_entity": learning_entity,
        "learning_temperature_source": learning_source,
        "learning_temperature_role": learning_role,
        "use_internal_sensor": None,
        "control_device_type": None,
        "control_device_mac_address": None,
    }


def _update_temperature_observation(
    hass: HomeAssistant,
    current_temperature: float | None,
    source_entity: str | None = None,
) -> dict[str, Any]:
    """Update in-memory temperature observations and return trend diagnostics."""
    store = _learning_store(hass)
    effective_source = source_entity or BREWZILLA_TEMP_SENSOR
    temp_state = _state_obj(hass, effective_source)
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

    if store.get("last_temperature_source_entity") != effective_source:
        store["previous_temperature"] = None
        store["previous_temperature_at"] = None
        store["last_temperature"] = current_temperature
        store["last_temperature_at"] = observed_at_iso
        store["last_temperature_source_entity"] = effective_source
        store["temp_rate_c_per_min"] = None
        return {
            "temp_rate_c_per_min": None,
            "temp_rate_c_per_hour": None,
            "temp_observation_age_seconds": _age_seconds(temp_state),
            "previous_temperature": None,
            "previous_temperature_at": None,
            "last_temperature": current_temperature,
            "last_temperature_at": observed_at_iso,
            "last_temperature_source_entity": effective_source,
        }

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
        "last_temperature_source_entity": store.get("last_temperature_source_entity"),
    }


def _suggest_heat_utilization(
    *,
    runtime_state: str,
    stage_kind: str,
    context: str,
    current_temperature: float | None,
    target_temperature: float | None,
    temp_rate_c_per_min: float | None,
    heat_utilization: float | None,
    heater_on: bool,
    pump_on: bool,
    pump_utilization: float | None,
) -> tuple[int | None, str, str, str]:
    """Return suggested heat utilization, confidence, phase and reason."""
    if runtime_state not in _ACTIVE_STATES:
        return None, "low", "standby", "Brewday runtime is not active."

    context_mod = _context_bias(context)
    context_note = str(context_mod["note"])
    context_heat_bias = int(context_mod["suggestion_bias"])
    mixing = _pump_mixing_state(stage_kind, pump_on, pump_utilization)
    pump_bias = _pump_heat_bias(stage_kind, pump_on, pump_utilization)
    pump_note = ""
    if mixing in {"off", "very_low", "low"}:
        pump_note = f" Pump mixing is {mixing}; heat suggestion is reduced for safer mash/kettle temperature interpretation."

    def result(suggestion: int, confidence: str, phase: str, reason: str) -> tuple[int, str, str, str]:
        biased = _apply_heat_biases(suggestion, pump_bias, context_heat_bias)
        capped_confidence = _cap_confidence(confidence, str(context_mod["confidence_cap"]))
        return biased, capped_confidence, phase, f"{reason}{pump_note}{context_note}"

    if stage_kind == "cooling":
        return 0, "high", "cooling", f"Cooling stage detected; heat should remain unavailable.{context_note}"

    if stage_kind == "boil":
        return result(100, "medium", "boil_ramp", "Boil stage detected; full heat is suggested until boil behavior has been profiled.")

    if current_temperature is None or target_temperature is None:
        return None, "low", "unknown", f"Missing current or target temperature.{context_note}"

    delta_to_target = target_temperature - current_temperature
    rate = temp_rate_c_per_min

    if delta_to_target > 5.0:
        return result(100, "medium", "ramp_far", "More than 5°C below target; high heat is suggested for ramp efficiency.")

    if delta_to_target > 2.0:
        if rate is not None and rate > 1.2:
            return result(75, "medium", "ramp_approach_fast", "Approaching target quickly; reduce heat to limit overshoot risk.")
        return result(90, "medium", "ramp_approach", "2–5°C below target; keep high heat but prepare to taper.")

    if delta_to_target > 0.7:
        if rate is not None and rate > 0.8:
            return result(55, "medium", "near_target_fast", "Within 2°C and rising quickly; taper heat early.")
        return result(70, "medium", "near_target", "Within 2°C below target; moderate heat is suggested.")

    if delta_to_target > 0.1:
        if rate is not None and rate > 0.4:
            return result(35, "medium", "final_approach_fast", "Very close to target and still rising; use low heat to reduce overshoot.")
        return result(50, "medium", "final_approach", "Very close to target; low-to-moderate heat is suggested.")

    if delta_to_target >= -0.3:
        if stage_kind == "mash_hold":
            return result(40, "medium", "mash_hold", "At mash target; conservative heat is suggested for stability.")
        return result(45, "medium", "hold", "At target; conservative heat is suggested until profiling data improves.")

    if delta_to_target < -0.3:
        base = 0 if heater_on else min(int(heat_utilization or 0), 30)
        return result(base, "medium", "overshoot", "Current temperature is above target; heat should be reduced or stopped.")

    return None, "low", "unknown", f"No suggestion available.{context_note}"


def _denied_snoozed(hass: HomeAssistant, recommendation_id: str) -> bool:
    raw = _learning_store(hass).get("denied_until", {}).get(recommendation_id)
    if not raw:
        return False
    parsed = dt_util.parse_datetime(str(raw))
    if parsed is None:
        return False
    return dt_util.utcnow() < dt_util.as_utc(parsed)


def _make_pending_recommendation(snapshot: dict[str, Any]) -> dict[str, Any] | None:
    """Create a pending APPLY/DENY recommendation from the observation snapshot."""
    suggestion = snapshot.get("suggested_heat_utilization")
    heat = snapshot.get("heat_utilization")
    pump = snapshot.get("pump_utilization")
    stage_kind = snapshot.get("stage_kind")
    confidence = str(snapshot.get("confidence") or "low")
    reason = str(snapshot.get("strategy_reason") or "")

    if stage_kind == "boil" and pump is not None and float(pump) > 0:
        return {
            "recommendation_id": "pump_utilization:boil:to_0",
            "kind": "pump_utilization",
            "entity_id": BREWZILLA_PUMP_UTILIZATION,
            "current_value": round(float(pump), 1),
            "recommended_value": 0,
            "confidence": "high",
            "severity": "actionable",
            "context": stage_kind,
            "reason": "Boil stage detected. Pump utilization should normally be 0 during boil unless an explicit operator flow, such as CFC Ready, starts it.",
            "action_label": "Set pump utilization to 0%",
            "apply_service": "number.set_value",
            "apply_entity": BREWZILLA_PUMP_UTILIZATION,
            "apply_value": 0,
        }

    if suggestion is None or heat is None:
        return None
    suggested = _round5(float(suggestion))
    current = float(heat)
    if abs(suggested - current) < MIN_RECOMMENDATION_DIFF:
        return None
    if confidence not in {"medium", "high"}:
        return None
    direction = "increase" if suggested > current else "reduce"
    return {
        "recommendation_id": f"heat_utilization:{stage_kind}:{_round5(current)}_to_{suggested}",
        "kind": "heat_utilization",
        "entity_id": BREWZILLA_HEAT_UTILIZATION,
        "current_value": round(current, 1),
        "recommended_value": suggested,
        "confidence": confidence,
        "severity": "suggestion",
        "context": stage_kind,
        "reason": reason,
        "action_label": f"{direction.title()} heat utilization to {suggested}%",
        "apply_service": "number.set_value",
        "apply_entity": BREWZILLA_HEAT_UTILIZATION,
        "apply_value": suggested,
    }


def build_brewzilla_learning_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    """Build BrewZilla learning/suggestion snapshot."""
    store = _learning_store(hass)
    runtime = build_core_snapshot(hass)
    runtime_state = str(runtime.get("runtime_state") or "idle").lower()
    stage_kind = _stage_kind(runtime)
    context = learning_context(hass)
    context_mod = _context_bias(context)

    store["observation_count"] = int(store.get("observation_count") or 0) + 1
    store["last_observed_at"] = dt_util.utcnow().isoformat()

    temperature_sources = _temperature_source_snapshot(hass, stage_kind)
    current_temperature = temperature_sources["learning_temperature"]
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
    trend = _update_temperature_observation(
        hass,
        current_temperature,
        temperature_sources.get("learning_temperature_entity"),
    )
    rate_per_min = trend.get("temp_rate_c_per_min")
    pump_mixing_state = _pump_mixing_state(stage_kind, pump_on, pump_utilization)
    pump_heat_bias = _pump_heat_bias(stage_kind, pump_on, pump_utilization)

    delta_to_target = None
    if current_temperature is not None and target_temperature is not None:
        delta_to_target = round(target_temperature - current_temperature, 2)

    suggestion, confidence, phase, reason = _suggest_heat_utilization(
        runtime_state=runtime_state,
        stage_kind=stage_kind,
        context=context,
        current_temperature=current_temperature,
        target_temperature=target_temperature,
        temp_rate_c_per_min=rate_per_min,
        heat_utilization=heat_utilization,
        heater_on=heater_on,
        pump_on=pump_on,
        pump_utilization=pump_utilization,
    )

    overshoot_risk = "unknown"
    if delta_to_target is not None and rate_per_min is not None:
        if delta_to_target < -0.3:
            overshoot_risk = "active_overshoot"
        elif pump_mixing_state in {"off", "very_low", "low"} and delta_to_target < 2.0 and rate_per_min > 0.25:
            overshoot_risk = "high"
        elif delta_to_target < 1.0 and rate_per_min > 0.4:
            overshoot_risk = "high"
        elif delta_to_target < 2.0 and rate_per_min > 0.8:
            overshoot_risk = "medium"
        else:
            overshoot_risk = "low"

    if context == "Water only" and overshoot_risk == "low" and delta_to_target is not None and delta_to_target < 2.0:
        overshoot_risk = "medium"

    heat_adjustment = None
    if suggestion is not None and heat_utilization is not None:
        heat_adjustment = int(round(suggestion - heat_utilization))

    base_snapshot = {
        "source": "brewzilla_learning",
        "mode": "observe_recommend_apply_deny",
        "runtime_state": runtime_state,
        "runtime_stage": runtime.get("stage"),
        "runtime_step": runtime.get("step"),
        "runtime_raw_step_name": runtime.get("raw_step_name"),
        "learning_context": context,
        "profile_weight": context_mod["profile_weight"],
        "context_confidence_cap": context_mod["confidence_cap"],
        "context_heat_bias": context_mod["suggestion_bias"],
        "water_only_bias_active": context == "Water only",
        "stage_kind": stage_kind,
        "phase": phase,
        "confidence": confidence,
        "current_temperature": current_temperature,
        "mash_temperature": temperature_sources["mash_temperature"],
        "mash_temperature_entity": temperature_sources["mash_temperature_entity"],
        "mash_temperature_source": temperature_sources["mash_temperature_source"],
        "wort_temperature": temperature_sources["wort_temperature"],
        "wort_temperature_entity": temperature_sources["wort_temperature_entity"],
        "wort_temperature_source": temperature_sources["wort_temperature_source"],
        "temperature_delta_mash_wort": temperature_sources["temperature_delta_mash_wort"],
        "learning_temperature": temperature_sources["learning_temperature"],
        "learning_temperature_entity": temperature_sources["learning_temperature_entity"],
        "learning_temperature_source": temperature_sources["learning_temperature_source"],
        "learning_temperature_role": temperature_sources["learning_temperature_role"],
        "use_internal_sensor": temperature_sources["use_internal_sensor"],
        "control_device_type": temperature_sources["control_device_type"],
        "control_device_mac_address": temperature_sources["control_device_mac_address"],
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
        "pump_mixing_state": pump_mixing_state,
        "pump_heat_bias": pump_heat_bias,
        "suggested_heat_utilization": suggestion,
        "heat_adjustment": heat_adjustment,
        "overshoot_risk": overshoot_risk,
        "strategy_reason": reason,
        "auto_apply_allowed": False,
        "last_observed_at": store.get("last_observed_at"),
        "observation_count": store.get("observation_count"),
    }

    pending = store.get("pending")
    candidate = _make_pending_recommendation(base_snapshot)
    if candidate is not None and not _denied_snoozed(hass, str(candidate["recommendation_id"])):
        if not pending or pending.get("recommendation_id") != candidate.get("recommendation_id"):
            candidate["state"] = "pending"
            candidate["created_at"] = dt_util.utcnow().isoformat()
            store["pending"] = candidate
            pending = candidate
    elif pending is not None:
        store["pending"] = None
        pending = None

    return {
        **base_snapshot,
        "status": "pending" if pending else "observing",
        "recommendation_state": pending.get("state") if pending else "none",
        "recommendation_id": pending.get("recommendation_id") if pending else None,
        "recommendation_kind": pending.get("kind") if pending else None,
        "recommendation_entity_id": pending.get("entity_id") if pending else None,
        "recommendation_current_value": pending.get("current_value") if pending else None,
        "recommendation_recommended_value": pending.get("recommended_value") if pending else None,
        "recommendation_reason": pending.get("reason") if pending else "No actionable learning recommendation right now.",
        "recommendation_action_label": pending.get("action_label") if pending else None,
        "pending_recommendation": pending,
        "last_applied": store.get("last_applied"),
        "last_denied": store.get("last_denied"),
        "deny_snooze_seconds": DENY_SNOOZE_SECONDS,
    }


async def async_apply_brewzilla_learning_recommendation(hass: HomeAssistant) -> dict[str, Any]:
    """Apply the current pending BrewZilla learning recommendation."""
    store = _learning_store(hass)
    snapshot = build_brewzilla_learning_snapshot(hass)
    pending = snapshot.get("pending_recommendation")
    if not pending:
        return {**snapshot, "applied": False, "apply_result": "no_pending_recommendation"}

    entity_id = pending.get("apply_entity") or pending.get("entity_id")
    value = pending.get("apply_value") or pending.get("recommended_value")
    if entity_id is None or value is None or hass.states.get(str(entity_id)) is None:
        return {**snapshot, "applied": False, "apply_result": "missing_entity_or_value"}

    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": str(entity_id), "value": float(value)},
        blocking=True,
    )
    result = {
        **snapshot,
        "applied": True,
        "apply_result": "applied",
        "applied_at": dt_util.utcnow().isoformat(),
        "applied_entity": entity_id,
        "applied_value": float(value),
    }
    store["last_applied"] = result
    store["pending"] = None
    return result


async def async_deny_brewzilla_learning_recommendation(hass: HomeAssistant) -> dict[str, Any]:
    """Deny the current pending BrewZilla learning recommendation."""
    store = _learning_store(hass)
    snapshot = build_brewzilla_learning_snapshot(hass)
    pending = snapshot.get("pending_recommendation")
    if not pending:
        return {**snapshot, "denied": False, "deny_result": "no_pending_recommendation"}

    denied_at = dt_util.utcnow()
    denied_until = denied_at + timedelta(seconds=DENY_SNOOZE_SECONDS)
    recommendation_id = str(pending.get("recommendation_id"))
    store.setdefault("denied_until", {})[recommendation_id] = denied_until.isoformat()
    result = {
        **snapshot,
        "denied": True,
        "deny_result": "denied",
        "denied_at": denied_at.isoformat(),
        "denied_until": denied_until.isoformat(),
    }
    store["last_denied"] = result
    store["pending"] = None
    return result
