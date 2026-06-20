"""BrewZilla learning and operator-confirmed recommendations.

This module is intentionally advisory. BrewAssistant observes BrewZilla behavior,
creates one pending recommendation at a time, and only executes changes after
explicit operator APPLY. DENY marks the recommendation as skipped and snoozes the
same recommendation for a short period.
"""

from __future__ import annotations

import re
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant, State
from homeassistant.util import dt as dt_util

from ..brewday.brewday_runtime import build_brewday_runtime_snapshot
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
BREWFATHER_BREW_TRACKER_RAW = "sensor.brewfather_brew_tracker_raw"

MANUAL_GRAIN_AMOUNT_KG = "number.brewassistant_batch_context_grain_amount_kg"
MANUAL_MASH_WATER_L = "number.brewassistant_batch_context_mash_water_l"
MANUAL_STRIKE_WATER_L = "number.brewassistant_batch_context_strike_water_l"
MANUAL_SPARGE_WATER_L = "number.brewassistant_batch_context_sparge_water_l"
MANUAL_PRE_BOIL_VOLUME_L = "number.brewassistant_batch_context_pre_boil_volume_l"
MANUAL_GRAIN_TEMPERATURE_C = "number.brewassistant_batch_context_grain_temperature_c"

LEGACY_MANUAL_GRAIN_AMOUNT_KG = "input_number.brewassistant_batch_context_grain_amount_kg"
LEGACY_MANUAL_MASH_WATER_L = "input_number.brewassistant_batch_context_mash_water_l"
LEGACY_MANUAL_STRIKE_WATER_L = "input_number.brewassistant_batch_context_strike_water_l"
LEGACY_MANUAL_SPARGE_WATER_L = "input_number.brewassistant_batch_context_sparge_water_l"
LEGACY_MANUAL_PRE_BOIL_VOLUME_L = "input_number.brewassistant_batch_context_pre_boil_volume_l"
LEGACY_MANUAL_GRAIN_TEMPERATURE_C = "input_number.brewassistant_batch_context_grain_temperature_c"

_BAD = {None, "unknown", "unavailable", "none", ""}
_ACTIVE_STATES = {
    "live",
    "running",
    "paused",
    "prepared",
    "awaiting_snapshot",
    "awaiting_confirm",
}
_RAMP_WORDS = ("ramp", "heat", "värm", "uppvärm", "strike", "mash in", "mash-in")
_HOLD_WORDS = ("hold", "rest", "rast", "mash", "mäsk", "saccharification", "beta", "alpha")
_BOIL_WORDS = ("boil", "kok", "boiling", "heating to boil", "värm till kok", "kokning", "kokgiva")
_COOL_WORDS = ("cool", "chill", "kyl")
_STRIKE_MASH_IN_CONTEXT_WORDS = (
    "strike",
    "strike water",
    "mash in",
    "mash-in",
    "inmäsk",
    "inmask",
    "värm mäsk",
    "värmning till mäsk",
)
_CONTEXT_OPTIONS = {"Unknown", "Water only", "Real mash"}
DEFAULT_GRAIN_TEMPERATURE_C = 20.0
MIN_RECOMMENDATION_DIFF = 5
DENY_SNOOZE_SECONDS = 15 * 60
ADVICE_NOTIFICATION_ID = "brewassistant_brewday_advice_pending"


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


def _clean_display(value: Any, fallback: str = "—") -> str:
    """Return a dashboard/notification friendly value."""
    if value is None:
        return fallback
    text = str(value)
    if text.lower() in _BAD:
        return fallback
    return text


def _format_recommendation_notification_message(
    snapshot: dict[str, Any],
    pending: dict[str, Any],
) -> str:
    """Build persistent notification text for a pending Brewday Advice recommendation."""
    action = _clean_display(pending.get("action_label"), "Kontrollera Brewday Advice-kortet")
    kind = _clean_display(pending.get("kind"))
    current = _clean_display(pending.get("current_value"))
    recommended = _clean_display(pending.get("recommended_value"))
    reason = _clean_display(pending.get("reason"), "Ingen orsak angiven.")
    stage = _clean_display(snapshot.get("stage_kind"))
    phase = _clean_display(snapshot.get("phase"))
    confidence = _clean_display(pending.get("confidence") or snapshot.get("confidence"))
    risk = _clean_display(snapshot.get("overshoot_risk"))
    temp = _clean_display(snapshot.get("learning_temperature"))
    delta = _clean_display(snapshot.get("delta_to_target"))

    return (
        "**Ny Brewday Advice-rekommendation**\n\n"
        f"**Åtgärd:** {action}\n\n"
        f"**Typ:** {kind}  \n"
        f"**Värde:** {current} → {recommended}  \n"
        f"**Stage/phase:** {stage} / {phase}  \n"
        f"**Confidence:** {confidence}  \n"
        f"**Overshoot-risk:** {risk}  \n"
        f"**Temp / Δ target:** {temp} °C / {delta} °C\n\n"
        f"**Orsak:** {reason}\n\n"
        "Gå till **Brewday Advice**-kortet för **APPLY** eller **DENY**."
    )


async def _dismiss_advice_notification(
    hass: HomeAssistant,
    store: dict[str, Any],
    *,
    reason: str,
) -> dict[str, Any]:
    """Dismiss the Brewday Advice persistent notification."""
    await hass.services.async_call(
        "persistent_notification",
        "dismiss",
        {"notification_id": ADVICE_NOTIFICATION_ID},
        blocking=False,
    )
    store["last_notified_recommendation_id"] = None
    store["last_notification_result"] = reason
    store["last_notification_updated_at"] = dt_util.utcnow().isoformat()
    return {
        "source": "brewzilla_learning",
        "notification_result": reason,
        "notification_id": ADVICE_NOTIFICATION_ID,
    }


async def async_update_brewday_advice_notification(hass: HomeAssistant) -> dict[str, Any]:
    """Create/dismiss Brewday Advice persistent notifications from backend state.

    This keeps notification logic in Python instead of Home Assistant automation YAML.
    A notification is created only when a new recommendation becomes pending.
    """
    store = _learning_store(hass)
    snapshot = build_brewzilla_learning_snapshot(hass)
    pending = snapshot.get("pending_recommendation")

    if pending and snapshot.get("recommendation_state") == "pending":
        recommendation_id = str(pending.get("recommendation_id") or "")
        if recommendation_id and store.get("last_notified_recommendation_id") == recommendation_id:
            return {
                "source": "brewzilla_learning",
                "notification_result": "already_notified",
                "notification_id": ADVICE_NOTIFICATION_ID,
                "recommendation_id": recommendation_id,
            }

        await hass.services.async_call(
            "persistent_notification",
            "create",
            {
                "notification_id": ADVICE_NOTIFICATION_ID,
                "title": "🍺 BrewAssistant Advice väntar",
                "message": _format_recommendation_notification_message(snapshot, pending),
            },
            blocking=False,
        )
        store["last_notified_recommendation_id"] = recommendation_id
        store["last_notification_result"] = "created"
        store["last_notification_updated_at"] = dt_util.utcnow().isoformat()
        return {
            "source": "brewzilla_learning",
            "notification_result": "created",
            "notification_id": ADVICE_NOTIFICATION_ID,
            "recommendation_id": recommendation_id,
        }

    if store.get("last_notified_recommendation_id"):
        return await _dismiss_advice_notification(hass, store, reason="dismissed_no_pending")

    return {
        "source": "brewzilla_learning",
        "notification_result": "no_pending",
        "notification_id": ADVICE_NOTIFICATION_ID,
    }


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


def _decimal(value: str) -> float | None:
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _html_text(value: Any) -> str:
    return re.sub(r"<[^>]+>", " ", str(value or "")).replace("&nbsp;", " ")


def _extract_liters(value: Any) -> list[float]:
    return [
        float(match.group(1).replace(",", "."))
        for match in re.finditer(r"<b>\s*([0-9]+(?:[.,][0-9]+)?)\s*L\s*</b>", str(value or ""), re.I)
    ]


def _extract_grams(value: Any) -> list[float]:
    return [
        float(match.group(1).replace(",", "."))
        for match in re.finditer(r"<b>\s*([0-9]+(?:[.,][0-9]+)?)\s*g\s*</b>", str(value or ""), re.I)
    ]


def _tracker_steps(stage: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(stage, dict):
        return []
    steps = stage.get("steps")
    return [step for step in steps if isinstance(step, dict)] if isinstance(steps, list) else []


def _brewfather_tracker_data(hass: HomeAssistant) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    raw = _state_obj(hass, BREWFATHER_BREW_TRACKER_RAW)
    if raw is None:
        return None, None
    data = raw.attributes.get("data")
    data = data if isinstance(data, dict) else None
    current_stage = raw.attributes.get("current_stage")
    current_stage = current_stage if isinstance(current_stage, dict) else None
    return data, current_stage


def _brewfather_batch_context(hass: HomeAssistant) -> dict[str, Any]:
    data, current_stage = _brewfather_tracker_data(hass)
    stages = []
    if data and isinstance(data.get("stages"), list):
        stages = [stage for stage in data["stages"] if isinstance(stage, dict)]
    if current_stage:
        stages.insert(0, current_stage)

    grain_g = 0.0
    mash_water_l = None
    sparge_water_l = None
    pre_boil_volume_l = None

    for stage in stages:
        stage_name = str(stage.get("name") or "").lower()
        for step in _tracker_steps(stage):
            description = str(step.get("description") or "")
            tooltip = str(step.get("tooltip") or "")
            text = _html_text(f"{description} {tooltip}").lower()

            if mash_water_l is None and (
                "mäskvatten" in text
                or "mash water" in text
                or "strike water" in text
            ):
                liters = _extract_liters(description)
                if liters:
                    mash_water_l = liters[0]

            if "mäsktillsatser" in text or "mash additions" in text:
                grain_g += sum(_extract_grams(description))

            if sparge_water_l is None and ("sparge" in stage_name or "laka" in text or "lakning" in text):
                liters = _extract_liters(description)
                if liters:
                    sparge_water_l = liters[0]
                    if len(liters) > 1:
                        pre_boil_volume_l = liters[-1]

            if pre_boil_volume_l is None and ("kokvolym" in text or "pre boil" in text or "pre-boil" in text):
                liters = _extract_liters(description)
                if liters:
                    pre_boil_volume_l = liters[-1]

    grain_amount_kg = round(grain_g / 1000.0, 3) if grain_g > 0 else None
    return {
        "source": "brewfather_brew_tracker_raw" if any(
            value is not None for value in (grain_amount_kg, mash_water_l, sparge_water_l, pre_boil_volume_l)
        ) else None,
        "grain_amount_kg": grain_amount_kg,
        "mash_water_l": mash_water_l,
        "sparge_water_l": sparge_water_l,
        "pre_boil_volume_l": pre_boil_volume_l,
    }



def _manual_float(hass: HomeAssistant, primary_entity: str, legacy_entity: str) -> float | None:
    value = _float(hass, primary_entity)
    if value is not None:
        return value
    return _float(hass, legacy_entity)


def _manual_batch_context(hass: HomeAssistant) -> dict[str, Any]:
    mash_water_l = _manual_float(hass, MANUAL_MASH_WATER_L, LEGACY_MANUAL_MASH_WATER_L)
    strike_water_l = _manual_float(hass, MANUAL_STRIKE_WATER_L, LEGACY_MANUAL_STRIKE_WATER_L)
    return {
        "source": "manual",
        "grain_amount_kg": _manual_float(hass, MANUAL_GRAIN_AMOUNT_KG, LEGACY_MANUAL_GRAIN_AMOUNT_KG),
        "mash_water_l": mash_water_l if mash_water_l is not None else strike_water_l,
        "sparge_water_l": _manual_float(hass, MANUAL_SPARGE_WATER_L, LEGACY_MANUAL_SPARGE_WATER_L),
        "pre_boil_volume_l": _manual_float(hass, MANUAL_PRE_BOIL_VOLUME_L, LEGACY_MANUAL_PRE_BOIL_VOLUME_L),
        "grain_temperature_c": _manual_float(
            hass,
            MANUAL_GRAIN_TEMPERATURE_C,
            LEGACY_MANUAL_GRAIN_TEMPERATURE_C,
        ),
    }


def _batch_context_snapshot(hass: HomeAssistant, runtime: dict[str, Any], stage_kind: str) -> dict[str, Any]:
    """Return batch-context guard diagnostics for strike/mash-in advice."""
    text = f"{runtime.get('stage') or ''} {runtime.get('step') or ''} {runtime.get('raw_step_name') or ''}".lower()
    context_required = bool(
        stage_kind == "ramp"
        and any(word in text for word in _STRIKE_MASH_IN_CONTEXT_WORDS)
    )

    manual = _manual_batch_context(hass)
    brewfather = _brewfather_batch_context(hass)

    grain_amount_kg = manual["grain_amount_kg"] if manual["grain_amount_kg"] is not None else brewfather["grain_amount_kg"]
    mash_water_l = manual["mash_water_l"] if manual["mash_water_l"] is not None else brewfather["mash_water_l"]
    sparge_water_l = manual["sparge_water_l"] if manual["sparge_water_l"] is not None else brewfather["sparge_water_l"]
    pre_boil_volume_l = (
        manual["pre_boil_volume_l"] if manual["pre_boil_volume_l"] is not None else brewfather["pre_boil_volume_l"]
    )
    manual_grain_temp = manual["grain_temperature_c"]
    grain_temperature_c = manual_grain_temp if manual_grain_temp is not None else DEFAULT_GRAIN_TEMPERATURE_C

    source_parts = []
    if any(manual.get(key) is not None for key in ("grain_amount_kg", "mash_water_l", "sparge_water_l", "pre_boil_volume_l", "grain_temperature_c")):
        source_parts.append("manual")
    if brewfather.get("source"):
        source_parts.append(str(brewfather["source"]))
    source = "+".join(source_parts) if source_parts else None

    missing = []
    if grain_amount_kg is None:
        missing.append("grain_amount_kg")
    if mash_water_l is None:
        missing.append("mash_water_l")
    if grain_temperature_c is None:
        missing.append("grain_temperature_c")

    available = not missing
    needs_context = bool(context_required and not available)
    return {
        "batch_context_source": source,
        "batch_context_available": available,
        "needs_batch_context": needs_context,
        "batch_context_missing": missing if context_required else [],
        "batch_context_reason": (
            "Strike/mash-in heat advice requires grain amount, mash water volume and grain temperature context."
            if needs_context
            else None
        ),
        "grain_amount_kg": grain_amount_kg,
        "mash_water_l": mash_water_l,
        "sparge_water_l": sparge_water_l,
        "pre_boil_volume_l": pre_boil_volume_l,
        "grain_temperature_c": grain_temperature_c,
        "grain_temperature_assumed": manual_grain_temp is None and grain_temperature_c is not None,
    }


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
    runtime = build_brewday_runtime_snapshot(hass)
    runtime_state = str(runtime.get("runtime_state") or "idle").lower()
    stage_kind = _stage_kind(runtime)
    context = learning_context(hass)
    context_mod = _context_bias(context)
    batch_context = _batch_context_snapshot(hass, runtime, stage_kind)

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

    if batch_context["needs_batch_context"]:
        suggestion = None
        confidence = "low"
        phase = "needs_batch_context"
        reason = str(batch_context["batch_context_reason"])

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
        "needs_batch_context": batch_context["needs_batch_context"],
        "batch_context_available": batch_context["batch_context_available"],
        "batch_context_source": batch_context["batch_context_source"],
        "batch_context_missing": batch_context["batch_context_missing"],
        "batch_context_reason": batch_context["batch_context_reason"],
        "grain_amount_kg": batch_context["grain_amount_kg"],
        "mash_water_l": batch_context["mash_water_l"],
        "sparge_water_l": batch_context["sparge_water_l"],
        "pre_boil_volume_l": batch_context["pre_boil_volume_l"],
        "grain_temperature_c": batch_context["grain_temperature_c"],
        "grain_temperature_assumed": batch_context["grain_temperature_assumed"],
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
    candidate = None if base_snapshot.get("needs_batch_context") else _make_pending_recommendation(base_snapshot)
    if candidate is not None and not _denied_snoozed(hass, str(candidate["recommendation_id"])):
        if not pending or pending.get("recommendation_id") != candidate.get("recommendation_id"):
            candidate["state"] = "pending"
            candidate["created_at"] = dt_util.utcnow().isoformat()
            store["pending"] = candidate
            pending = candidate
    elif pending is not None:
        store["pending"] = None
        pending = None

    needs_batch_context = bool(base_snapshot.get("needs_batch_context"))
    no_pending_reason = (
        str(base_snapshot.get("batch_context_reason"))
        if needs_batch_context
        else "No actionable learning recommendation right now."
    )

    return {
        **base_snapshot,
        "status": "pending" if pending else "needs_batch_context" if needs_batch_context else "observing",
        "recommendation_state": pending.get("state") if pending else "needs_batch_context" if needs_batch_context else "none",
        "recommendation_id": pending.get("recommendation_id") if pending else None,
        "recommendation_kind": pending.get("kind") if pending else None,
        "recommendation_entity_id": pending.get("entity_id") if pending else None,
        "recommendation_current_value": pending.get("current_value") if pending else None,
        "recommendation_recommended_value": pending.get("recommended_value") if pending else None,
        "recommendation_reason": pending.get("reason") if pending else no_pending_reason,
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
    await _dismiss_advice_notification(hass, store, reason="dismissed_after_apply")
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
    await _dismiss_advice_notification(hass, store, reason="dismissed_after_deny")
    return result
