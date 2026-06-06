"""BrewZilla mash/wort temperature resolver."""

from __future__ import annotations

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


_BAD = {None, "unknown", "unavailable", "none", ""}


def _state_value(hass: HomeAssistant, entity_id: str | None) -> str | None:
    if not entity_id:
        return None
    state = hass.states.get(entity_id)
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


def _attrs(hass: HomeAssistant, entity_id: str | None) -> dict[str, Any]:
    if not entity_id:
        return {}
    state = hass.states.get(entity_id)
    return dict(state.attributes) if state is not None else {}


def selected_mash_source(hass: HomeAssistant) -> str:
    """Return operator-selected mash temperature source."""
    selected = _state_value(hass, MASH_SOURCE_SELECT)
    if selected in MASH_SOURCE_OPTIONS:
        return str(selected)
    return "Auto"


def _candidate(hass: HomeAssistant, entity_id: str, label: str) -> dict[str, Any]:
    value = _float_state(hass, entity_id)
    attrs = _attrs(hass, entity_id)
    return {
        "value": value,
        "entity_id": entity_id,
        "source": label,
        "available": value is not None,
        "attrs": attrs,
        "source_payload_key": attrs.get("source_payload_key"),
        "selected_control_device_temperature_source": attrs.get("selected_control_device_temperature_source"),
        "ba_value_rejected": attrs.get("ba_value_rejected"),
        "ba_reject_reason": attrs.get("ba_reject_reason"),
    }


def brewzilla_temperature_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    """Return resolved BrewZilla mash/wort temperature snapshot.

    Wort/kettle temperature is always the BrewZilla internal thermometer.
    Mash temperature is operator-selectable, with Auto preferring BLE.
    """
    selected = selected_mash_source(hass)

    ble = _candidate(hass, BREWZILLA_BLE_TEMP_SENSOR, "RAPT BLE Thermometer")
    control = _candidate(hass, BREWZILLA_CONTROL_DEVICE_TEMP_SENSOR, "BrewZilla Control Device")
    internal = _candidate(hass, BREWZILLA_INTERNAL_TEMP_SENSOR, "BrewZilla Internal")

    ordered: list[dict[str, Any]]
    if selected == "RAPT BLE Thermometer":
        ordered = [ble]
    elif selected == "BrewZilla Control Device":
        ordered = [control]
    elif selected == "BrewZilla Internal":
        ordered = [internal]
    else:
        ordered = [ble, control, internal]

    mash = next((candidate for candidate in ordered if candidate["available"]), None)

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
        "wort_temperature": wort_temperature,
        "wort_temperature_entity": BREWZILLA_INTERNAL_TEMP_SENSOR,
        "wort_temperature_source": "BrewZilla Internal",
        "temperature_delta_mash_wort": delta,
        "auto_priority": "BLE > Control Device > Internal",
        "candidates": {
            "ble": {k: v for k, v in ble.items() if k != "attrs"},
            "control_device": {k: v for k, v in control.items() if k != "attrs"},
            "internal": {k: v for k, v in internal.items() if k != "attrs"},
        },
    }
