"""Cooling Runtime v2 state and method helpers."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

DOMAIN_DATA_KEY = "cooling_runtime_v2"

METHOD_COUNTERFLOW = "Counterflow chiller"
METHOD_IMMERSION = "Immersion chiller"
METHOD_MANUAL = "Manual cooling"
METHOD_OPTIONS = [METHOD_COUNTERFLOW, METHOD_IMMERSION, METHOD_MANUAL]

DEFAULT_METHOD = METHOD_COUNTERFLOW
DEFAULT_TARGET_C = 18.0
DEFAULT_MANUAL_TEMP_C = 20.0
DEFAULT_SANITIZE_MINUTES = 15.0
READY_TOLERANCE_C = 1.0

STAGE_ENTITY = "sensor.brewassistant_brewday_runtime_stage"
STAGE_FALLBACK_ENTITY = "sensor.brewassistant_brewday_stage"
REMAINING_MINUTES_ENTITY = "sensor.brewassistant_brewday_live_time_remaining_minutes"
BREWZILLA_TEMP_ENTITY = "sensor.brewassistant_brewzilla_wort_temperature"
PUMP_ENTITY = "switch.brewzilla_pump"

CFC_OUTPUT_TEMP_ENTITIES = (
    "sensor.rapt_ble_thermometer_temperature",
    "sensor.rapt_ble_thermometer_temp",
    "sensor.counterflow_output_temperature",
    "sensor.wort_output_temperature",
)

BAD_STATES = {"unknown", "unavailable", "none", ""}


def _store(hass: HomeAssistant) -> dict[str, Any]:
    return hass.data.setdefault("brewassistant", {}).setdefault(
        DOMAIN_DATA_KEY,
        {
            "method": DEFAULT_METHOD,
            "target_temperature": DEFAULT_TARGET_C,
            "manual_temperature": DEFAULT_MANUAL_TEMP_C,
            "sanitize_minutes": DEFAULT_SANITIZE_MINUTES,
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
    target = float(settings.get("target_temperature", DEFAULT_TARGET_C))
    manual_temp = float(settings.get("manual_temperature", DEFAULT_MANUAL_TEMP_C))
    sanitize_minutes = float(settings.get("sanitize_minutes", DEFAULT_SANITIZE_MINUTES))
    stage = _stage(hass)
    remaining = _float(hass, REMAINING_MINUTES_ENTITY)
    runtime_state = _runtime_state(method, stage, remaining, sanitize_minutes)

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

    pump_state = _state(hass, PUMP_ENTITY) or "unknown"
    wort_pump_required = method == METHOD_COUNTERFLOW and runtime_state in {"SANITIZE", "CHILLING", "TRANSFER"}
    sanitize_required = method in {METHOD_COUNTERFLOW, METHOD_IMMERSION}

    return {
        "method": method,
        "state": runtime_state,
        "stage": stage,
        "boil_remaining_minutes": remaining,
        "sanitize_minutes": sanitize_minutes,
        "sanitize_required": sanitize_required,
        "target_temperature": target,
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
        "cooling_water_control": "manual_or_optional_switch",
        "cooling_water_automatic_control_active": False,
        "target_ready_tolerance_c": READY_TOLERANCE_C,
    }
