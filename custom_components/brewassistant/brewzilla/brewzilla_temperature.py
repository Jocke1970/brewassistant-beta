"""BrewZilla mash/wort temperature resolver."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from homeassistant.core import HomeAssistant

MASH_SOURCE_SELECT = "select.brewassistant_brewzilla_mash_temperature_source"

MASH_SOURCE_OPTIONS = [
    "Auto",
    "RAPT BLE Thermometer",
    "BrewZilla Control Device",
    "BrewZilla Internal",
]

BREWZILLA_INTERNAL_TEMP_SENSOR = "sensor.brewzilla_temperature"
BREWZILLA_BLE_TEMP_SENSOR = "sensor.brewzilla_ble_thermometer_temperature"
BREWZILLA_CONTROL_DEVICE_TEMP_SENSOR = "sensor.brewzilla_control_device_temperature"

MAX_EXTERNAL_MASH_TEMPERATURE_AGE_SECONDS = 180

_BAD = {None, "unknown", "unavailable", "none", ""}


def _state_obj(hass: HomeAssistant, entity_id: str | None):
    if not entity_id:
        return None
    return hass.states.get(entity_id)


def _state_value(hass: HomeAssistant, entity_id: str | None) -> str | None:
    state = _state_obj(hass, entity_id)
    if state is None or state.state in _BAD:
        return None
    return state.state


def _float_state(hass: HomeAssistant, entity_id: str | None) -> float | None:
    raw = _state_value(hass, entity_id)
    try:
        if raw is None or str(raw).lower() in _BAD:
            return None
        return round(float(raw), 2)
    except (TypeError, ValueError):
        return None


def _state_age_seconds(hass: HomeAssistant, entity_id: str | None) -> int | None:
    state = _state_obj(hass, entity_id)
    if state is None or state.last_updated is None:
        return None
    updated = state.last_updated
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=UTC)
    return max(0, int(round((datetime.now(UTC) - updated).total_seconds())))


def _attrs(hass: HomeAssistant, entity_id: str | None) -> dict[str, Any]:
    state = _state_obj(hass, entity_id)
    return dict(state.attributes) if state is not None else {}


def selected_mash_source(hass: HomeAssistant) -> str:
    """Return operator-selected mash temperature source."""
    selected = _state_value(hass, MASH_SOURCE_SELECT)
    if selected in MASH_SOURCE_OPTIONS:
        return str(selected)
    return "Auto"


def _looks_like_control_telemetry(candidate: dict[str, Any]) -> bool:
    return bool(
        candidate.get("source_payload_key") == "controlDeviceTemperature"
        or candidate.get("selected_control_device_temperature_source") == "telemetry"
    )


def _candidate(hass: HomeAssistant, entity_id: str, label: str) -> dict[str, Any]:
    value = _float_state(hass, entity_id)
    attrs = _attrs(hass, entity_id)
    age_seconds = _state_age_seconds(hass, entity_id)
    external = label != "BrewZilla Internal"
    raw_rejected = bool(attrs.get("ba_value_rejected"))
    raw_reject_reason = attrs.get("ba_reject_reason")

    freshness_ok = True
    if external and age_seconds is not None:
        freshness_ok = age_seconds <= MAX_EXTERNAL_MASH_TEMPERATURE_AGE_SECONDS

    return {
        "value": value,
        "entity_id": entity_id,
        "source": label,
        "available": value is not None,
        "attrs": attrs,
        "age_seconds": age_seconds,
        "freshness_ok": freshness_ok,
        "max_age_seconds": MAX_EXTERNAL_MASH_TEMPERATURE_AGE_SECONDS if external else None,
        "external_mash_candidate": external,
        "source_payload_key": attrs.get("source_payload_key"),
        "selected_control_device_temperature_source": attrs.get("selected_control_device_temperature_source"),
        "ba_value_rejected": raw_rejected,
        "ba_reject_reason": raw_reject_reason,
    }


def _candidate_reject_reason(candidate: dict[str, Any], *, selected: str) -> str | None:
    if not candidate["available"]:
        return "unavailable"
    if candidate.get("ba_value_rejected"):
        return str(candidate.get("ba_reject_reason") or "source_rejected_value")
    if not candidate.get("freshness_ok", True):
        return f"stale_{candidate.get('age_seconds')}s"

    source = candidate.get("source")
    control_telemetry = _looks_like_control_telemetry(candidate)

    if source == "RAPT BLE Thermometer" and control_telemetry:
        return "not_active_ble_thermometer_control_telemetry"

    if selected == "Auto" and source == "BrewZilla Control Device" and control_telemetry:
        return "auto_rejects_control_device_telemetry_without_external_mash_probe"

    return None


def _eligible(candidate: dict[str, Any], *, selected: str) -> bool:
    return _candidate_reject_reason(candidate, selected=selected) is None


def _with_diagnostics(candidate: dict[str, Any], *, selected: str) -> dict[str, Any]:
    reject_reason = _candidate_reject_reason(candidate, selected=selected)
    return {
        **{k: v for k, v in candidate.items() if k != "attrs"},
        "eligible": reject_reason is None,
        "reject_reason": reject_reason,
    }


def _resolve_mash_candidate(
    selected: str,
    ble: dict[str, Any],
    control: dict[str, Any],
    internal: dict[str, Any],
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    if selected == "RAPT BLE Thermometer":
        ordered = [ble, internal]
    elif selected == "BrewZilla Control Device":
        ordered = [control, internal]
    elif selected == "BrewZilla Internal":
        ordered = [internal]
    else:
        ordered = [ble, control, internal]

    diagnostics = [_with_diagnostics(candidate, selected=selected) for candidate in ordered]
    mash = next((candidate for candidate in ordered if _eligible(candidate, selected=selected)), None)
    return mash, diagnostics


def brewzilla_temperature_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    """Return resolved BrewZilla mash/wort temperature snapshot.

    Wort/kettle temperature is always the BrewZilla internal thermometer.
    Mash temperature is operator-selectable. Auto prefers a valid, fresh external
    mash probe, but falls back to BrewZilla internal when BLE/control telemetry is
    stale or not a real external mash-temperature source.
    """
    selected = selected_mash_source(hass)

    ble = _candidate(hass, BREWZILLA_BLE_TEMP_SENSOR, "RAPT BLE Thermometer")
    control = _candidate(hass, BREWZILLA_CONTROL_DEVICE_TEMP_SENSOR, "BrewZilla Control Device")
    internal = _candidate(hass, BREWZILLA_INTERNAL_TEMP_SENSOR, "BrewZilla Internal")

    mash, ordered_diagnostics = _resolve_mash_candidate(selected, ble, control, internal)

    mash_temperature = mash["value"] if mash else None
    mash_entity = mash["entity_id"] if mash else None
    mash_source = mash["source"] if mash else "Unavailable"

    wort_temperature = internal["value"]
    delta = None
    if mash_temperature is not None and wort_temperature is not None:
        delta = round(mash_temperature - wort_temperature, 2)

    return {
        "source": "brewzilla_temperature_resolver",
        "mash_source_select_entity": MASH_SOURCE_SELECT,
        "mash_source_selected": selected,
        "mash_temperature": mash_temperature,
        "mash_temperature_entity": mash_entity,
        "mash_temperature_source": mash_source,
        "mash_temperature_source_payload_key": (mash or {}).get("source_payload_key"),
        "mash_temperature_selected_control_device_temperature_source": (mash or {}).get("selected_control_device_temperature_source"),
        "mash_temperature_value_rejected": (mash or {}).get("ba_value_rejected"),
        "mash_temperature_reject_reason": (mash or {}).get("ba_reject_reason"),
        "mash_temperature_age_seconds": (mash or {}).get("age_seconds"),
        "mash_temperature_freshness_ok": (mash or {}).get("freshness_ok"),
        "mash_temperature_external_mash_candidate": (mash or {}).get("external_mash_candidate"),
        "wort_temperature": wort_temperature,
        "wort_temperature_entity": BREWZILLA_INTERNAL_TEMP_SENSOR,
        "wort_temperature_source": "BrewZilla Internal",
        "wort_temperature_age_seconds": internal.get("age_seconds"),
        "temperature_delta_mash_wort": delta,
        "auto_priority": "fresh external mash probe > BrewZilla Internal",
        "candidate_policy": {
            "max_external_mash_temperature_age_seconds": MAX_EXTERNAL_MASH_TEMPERATURE_AGE_SECONDS,
            "auto_rejects_control_device_telemetry_without_external_mash_probe": True,
            "auto_rejects_ble_aliasing_control_device_temperature": True,
        },
        "ordered_candidates": ordered_diagnostics,
        "candidates": {
            "ble": _with_diagnostics(ble, selected=selected),
            "control_device": _with_diagnostics(control, selected=selected),
            "internal": _with_diagnostics(internal, selected=selected),
        },
    }
