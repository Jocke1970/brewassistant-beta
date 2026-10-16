"""Cooling Runtime v2 state and method helpers."""

from __future__ import annotations

from typing import Any
from collections.abc import Mapping
import math

from homeassistant.core import HomeAssistant

DOMAIN_DATA_KEY = "cooling_runtime_v2"

METHOD_COUNTERFLOW = "Counterflow chiller"
METHOD_IMMERSION = "Immersion chiller"
METHOD_MANUAL = "Manual cooling"
METHOD_OPTIONS = [METHOD_COUNTERFLOW, METHOD_IMMERSION, METHOD_MANUAL]

DEFAULT_METHOD = METHOD_COUNTERFLOW
DEFAULT_TARGET_C = 20.0
DEFAULT_MANUAL_TEMP_C = 20.0
DEFAULT_SANITIZE_MINUTES = 15.0
READY_TOLERANCE_C = 1.0

STAGE_ENTITY = "sensor.brewassistant_brewday_runtime_stage"
STAGE_FALLBACK_ENTITY = "sensor.brewassistant_brewday_stage"
REMAINING_MINUTES_ENTITY = "sensor.brewassistant_brewday_live_time_remaining_minutes"
BREWZILLA_TEMP_ENTITY = "sensor.brewassistant_brewzilla_wort_temperature"
PUMP_ENTITY = "switch.brewzilla_pump"

CFC_OUTPUT_TEMP_ENTITIES = ("sensor.rapt_temp_a7ba_temperature",)

BF_BATCHES_ENTITY = "sensor.brewfather_all_batches_data"


def _brewfather_pitch_target(hass: HomeAssistant) -> tuple[float | None, str | None]:
    """Resolve first fermentation temperature from an unambiguous BF batch.

    BrewTracker is brewday-only and must never supply fermentation targets.
    With multiple batches, fail closed until explicit batch selection exists.
    """
    state = hass.states.get(BF_BATCHES_ENTITY)
    if state is None or str(state.state).lower() in {"unknown", "unavailable", "none", ""}:
        return None, None
    batches = state.attributes.get("data")
    if not isinstance(batches, list) or len(batches) != 1:
        return None, None

    batch = batches[0]
    if not isinstance(batch, Mapping):
        return None, None
    recipe = batch.get("recipe")
    fermentation = recipe.get("fermentation") if isinstance(recipe, Mapping) else None
    steps = fermentation.get("steps") if isinstance(fermentation, Mapping) else None
    if not isinstance(steps, list) or not steps or not isinstance(steps[0], Mapping):
        return None, None

    try:
        temperature = float(steps[0]["stepTemp"])
    except (KeyError, TypeError, ValueError):
        return None, None
    if not math.isfinite(temperature) or not 8 <= temperature <= 30:
        return None, None
    return temperature, BF_BATCHES_ENTITY

BAD_STATES = {"unknown", "unavailable", "none", ""}


def _store(hass: HomeAssistant) -> dict[str, Any]:
    return hass.data.setdefault("brewassistant", {}).setdefault(
        DOMAIN_DATA_KEY,
        {
            "method": DEFAULT_METHOD,
            "target_temperature": DEFAULT_TARGET_C,
            "manual_temperature": DEFAULT_MANUAL_TEMP_C,
            "sanitize_minutes": DEFAULT_SANITIZE_MINUTES,
            "manual_override_confirmed": False,
            "brewfather_target_temperature": None,
        },
    )


def get_cooling_runtime_settings(hass: HomeAssistant) -> dict[str, Any]:
    return dict(_store(hass))


def update_cooling_runtime_settings(hass: HomeAssistant, values: dict[str, Any]) -> dict[str, Any]:
    store = _store(hass)
    if "method" in values and values["method"] in METHOD_OPTIONS:
        store["method"] = values["method"]
    if "target_temperature" in values:
        store["target_temperature"] = max(8.0, min(30.0, round(float(values["target_temperature"]))))
    if "manual_temperature" in values:
        store["manual_temperature"] = max(-5.0, min(110.0, float(values["manual_temperature"])))
    if "sanitize_minutes" in values:
        store["sanitize_minutes"] = max(10.0, min(25.0, round(float(values["sanitize_minutes"]))))
    if "brewfather_target_temperature" in values:
        raw = values["brewfather_target_temperature"]
        store["brewfather_target_temperature"] = float(raw) if raw is not None and 8 <= float(raw) <= 30 else None
    # Only explicit acknowledgement may set override.
    return dict(store)


def _state(hass: HomeAssistant, entity_id: str) -> str | None:
    state = hass.states.get(entity_id)
    if state is None or str(state.state).lower() in BAD_STATES:
        return None
    return str(state.state)


def _float(hass: HomeAssistant, entity_id: str) -> float | None:
    raw = _state(hass, entity_id)
    if raw is None:
        return None
    try:
        return float(raw.replace(",", "."))
    except (TypeError, ValueError):
        return None


def _first_float(hass: HomeAssistant, entity_ids: tuple[str, ...]) -> tuple[float | None, str | None]:
    for entity_id in entity_ids:
        value = _float(hass, entity_id)
        if value is not None:
            return value, entity_id
    return None, None


def _stage(hass: HomeAssistant) -> str:
    return _state(hass, STAGE_ENTITY) or _state(hass, STAGE_FALLBACK_ENTITY) or "Idle"


def _runtime_state(method: str, stage: str, remaining_minutes: float | None, sanitize_minutes: float) -> str:
    text = stage.lower()
    if "transfer" in text:
        return "TRANSFER"
    if any(token in text for token in ("chill", "cool")):
        return "CHILLING"
    if "boil" in text:
        if method in {METHOD_COUNTERFLOW, METHOD_IMMERSION}:
            if remaining_minutes is not None and remaining_minutes <= sanitize_minutes:
                return "SANITIZE"
            return "PREPARE"
        return "PREPARE"
    if any(token in text for token in ("complete", "cleanup", "finished")):
        return "COMPLETE"
    return "IDLE"


def build_cooling_runtime_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    settings = _store(hass)
    method = str(settings.get("method", DEFAULT_METHOD))
    manual_target = float(settings.get("target_temperature", DEFAULT_TARGET_C))
    bf_target, bf_source = _brewfather_pitch_target(hass)
    override = bool(settings.get("manual_override_confirmed", False))
    target = manual_target if override or bf_target is None else float(bf_target)
    target_source = "manual_override" if override else ("brewfather" if bf_target is not None else "manual")
    manual_temp = float(settings.get("manual_temperature", DEFAULT_MANUAL_TEMP_C))
    sanitize_minutes = float(settings.get("sanitize_minutes", DEFAULT_SANITIZE_MINUTES))
    stage = _stage(hass)
    remaining = _float(hass, REMAINING_MINUTES_ENTITY)
    runtime_state = _runtime_state(method, stage, remaining, sanitize_minutes)
    previous_state = settings.get("last_cooling_state", "IDLE")
    if runtime_state in {"IDLE", "PREPARE", "SANITIZE"} and previous_state in {"CHILLING", "TRANSFER", "COMPLETE"}:
        settings["manual_override_confirmed"] = False
        override = False
    settings["last_cooling_state"] = runtime_state
    target = manual_target if override or bf_target is None else float(bf_target)
    target_source = "manual_override" if override else ("brewfather" if bf_target is not None else "manual")

    cfc_temp, cfc_source = _first_float(hass, CFC_OUTPUT_TEMP_ENTITIES)
    brewzilla_temp = _float(hass, BREWZILLA_TEMP_ENTITY)

    if method == METHOD_COUNTERFLOW:
        process_temp = cfc_temp
        process_source = cfc_source
        source_kind = "cfc_outlet"
    elif method == METHOD_IMMERSION:
        if brewzilla_temp is not None:
            process_temp = brewzilla_temp
            process_source = BREWZILLA_TEMP_ENTITY
            source_kind = "brewzilla_internal"
        else:
            process_temp = manual_temp
            process_source = "number.brewassistant_cooling_manual_temperature"
            source_kind = "manual_input"
    else:
        process_temp = manual_temp
        process_source = "number.brewassistant_cooling_manual_temperature"
        source_kind = "manual_input"

    pump_state = "not_configured"
    wort_pump_required = False  # Cooling never requires a HA pump entity.
    sanitize_required = method in {METHOD_COUNTERFLOW, METHOD_IMMERSION}

    return {
        "method": method,
        "state": runtime_state,
        "stage": stage,
        "boil_remaining_minutes": remaining,
        "sanitize_minutes": sanitize_minutes,
        "sanitize_required": sanitize_required,
        "target_temperature": target,
        "target_temperature_source": target_source,
        "manual_target_temperature": manual_target,
        "brewfather_target_temperature": bf_target,
        "brewfather_target_source": bf_source,
        "manual_override_confirmed": override,
        "manual_temperature": manual_temp,
        "process_temperature": process_temp,
        "process_temperature_source": process_source,
        "process_temperature_source_kind": source_kind,
        "cfc_outlet_temperature": cfc_temp,
        "cfc_outlet_source": cfc_source,
        "brewzilla_temperature": brewzilla_temp,
        "wort_pump_state": pump_state,
        "wort_pump_required": wort_pump_required,
        "wort_pump_operator_owned": True,
        "cooling_water_control": "manual_tap",
        "cooling_water_automatic_control_active": False,
        "target_ready_tolerance_c": READY_TOLERANCE_C,
    }


def confirm_cooling_manual_override(hass: HomeAssistant, *, confirmed: bool, target_temperature: float) -> dict[str, Any]:
    """Operator-confirmed override during active cooling only."""
    if confirmed is not True:
        raise ValueError("Explicit operator confirmation required")
    snapshot = build_cooling_runtime_snapshot(hass)
    if snapshot["state"] not in {"CHILLING", "TRANSFER"}:
        raise ValueError("Cooling is not active")
    if not math.isfinite(target_temperature) or not 8 <= target_temperature <= 30:
        raise ValueError("Cooling target must be 8–30 °C")
    store = _store(hass)
    store["target_temperature"] = round(target_temperature)
    store["manual_override_confirmed"] = True
    return build_cooling_runtime_snapshot(hass)


def clear_cooling_manual_override(hass: HomeAssistant) -> dict[str, Any]:
    """Restore Brewfather priority."""
    _store(hass)["manual_override_confirmed"] = False
    return build_cooling_runtime_snapshot(hass)
