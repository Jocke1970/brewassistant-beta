"""Wort cooling intelligence helpers.

Read-only counterflow cooling calculations for BrewAssistant.

This module estimates cooling status, temperature delta, cooling rate and ETA
from current Home Assistant states plus a small in-memory trend buffer.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

DOMAIN_DATA_KEY = "wort_cooling"
BAD_STATES = {"unknown", "unavailable", "none", ""}

STAGE_SENSOR = "sensor.brewassistant_brewday_stage"
CONTROL_HINT_SENSOR = "sensor.brewassistant_brewday_stage_control_hint"
KETTLE_TEMP_SENSOR = "sensor.brewassistant_brewzilla_current_temperature"
BREWZILLA_TARGET_SENSOR = "sensor.brewassistant_brewzilla_target_temperature"
BREWZILLA_POWER_SENSOR = "sensor.brewassistant_brewzilla_power"
PITCH_TARGET_NUMBER = "number.brewzilla_target_temperature"
PUMP_SWITCH = "switch.brewzilla_pump"
HEATER_SWITCH = "switch.brewzilla_heater"
POWER_SWITCH = "switch.brewzilla"

# Optional sensors. The first available source is used as the cooling reference.
OPTIONAL_OUTPUT_TEMP_SENSORS = (
    "sensor.rapt_ble_thermometer_temperature",
    "sensor.rapt_ble_thermometer_temp",
    "sensor.brewzilla_output_temperature",
    "sensor.counterflow_output_temperature",
    "sensor.wort_output_temperature",
)

READY_TOLERANCE_C = 1.0
MIN_SAMPLE_SECONDS = 60
MAX_SAMPLE_SECONDS = 7200
MIN_MEANINGFUL_RATE_C_PER_H = 0.2


@dataclass(slots=True)
class CoolingSample:
    """One temperature trend sample."""

    timestamp: datetime
    temperature: float
    source_entity: str


def _state(hass: HomeAssistant, entity_id: str, default: str | None = None) -> str | None:
    entity_state = hass.states.get(entity_id)
    if entity_state is None or entity_state.state in BAD_STATES:
        return default
    return entity_state.state


def _float(hass: HomeAssistant, entity_id: str) -> float | None:
    raw = _state(hass, entity_id)
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _first_float_source(hass: HomeAssistant, entity_ids: tuple[str, ...]) -> tuple[float | None, str | None]:
    for entity_id in entity_ids:
        value = _float(hass, entity_id)
        if value is not None:
            return value, entity_id
    return None, None


def _cooling_store(hass: HomeAssistant) -> dict[str, CoolingSample | None]:
    return hass.data.setdefault("brewassistant", {}).setdefault(
        DOMAIN_DATA_KEY,
        {"previous": None, "latest": None},
    )


def _update_trend(
    hass: HomeAssistant,
    *,
    reference_temp: float | None,
    reference_source: str | None,
) -> tuple[CoolingSample | None, CoolingSample | None]:
    """Update and return previous/latest trend samples."""
    store = _cooling_store(hass)
    previous = store.get("previous")
    latest = store.get("latest")

    if reference_temp is None or reference_source is None:
        return previous, latest

    now = dt_util.utcnow()
    new_sample = CoolingSample(now, round(reference_temp, 3), reference_source)

    if latest is None:
        store["latest"] = new_sample
        return None, new_sample

    elapsed = (now - latest.timestamp).total_seconds()
    same_value = abs(new_sample.temperature - latest.temperature) < 0.01
    same_source = new_sample.source_entity == latest.source_entity

    if elapsed < MIN_SAMPLE_SECONDS and same_source:
        return previous, latest

    if same_value and same_source and elapsed < MAX_SAMPLE_SECONDS:
        return previous, latest

    store["previous"] = latest
    store["latest"] = new_sample
    return latest, new_sample


def _cooling_rate(previous: CoolingSample | None, latest: CoolingSample | None) -> float | None:
    """Return positive cooling rate in °C/hour when temperature is falling."""
    if previous is None or latest is None:
        return None

    elapsed_seconds = (latest.timestamp - previous.timestamp).total_seconds()
    if elapsed_seconds < MIN_SAMPLE_SECONDS or elapsed_seconds > MAX_SAMPLE_SECONDS:
        return None

    elapsed_hours = elapsed_seconds / 3600
    rate = (previous.temperature - latest.temperature) / elapsed_hours
    if rate <= 0:
        return 0.0
    return round(rate, 2)


def _cooling_status(
    *,
    reference_temp: float | None,
    target_temp: float | None,
    rate_c_per_h: float | None,
    stage: str | None,
    pump_state: str | None,
    heater_state: str | None,
) -> str:
    if reference_temp is None:
        return "no_reference_temperature"
    if target_temp is None:
        return "no_target"

    delta = reference_temp - target_temp
    if abs(delta) <= READY_TOLERANCE_C:
        return "pitch_ready"
    if delta < -READY_TOLERANCE_C:
        return "below_target"
    if heater_state == "on":
        return "heater_on_during_cooling"
    if pump_state == "off" and (stage or "") == "Wort Cooling":
        return "pump_off"
    if rate_c_per_h is not None and rate_c_per_h > MIN_MEANINGFUL_RATE_C_PER_H:
        return "cooling"
    if (stage or "") == "Wort Cooling":
        return "cooling_waiting_for_trend"
    return "monitoring"


def build_wort_cooling_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    """Build read-only wort cooling snapshot."""
    output_temp, output_source = _first_float_source(hass, OPTIONAL_OUTPUT_TEMP_SENSORS)
    kettle_temp = _float(hass, KETTLE_TEMP_SENSOR)
    kettle_source = KETTLE_TEMP_SENSOR if kettle_temp is not None else None

    if output_temp is not None:
        reference_temp = output_temp
        reference_source = output_source
        reference_label = "output"
    else:
        reference_temp = kettle_temp
        reference_source = kettle_source
        reference_label = "kettle"

    pitch_target = _float(hass, PITCH_TARGET_NUMBER)
    brewzilla_target = _float(hass, BREWZILLA_TARGET_SENSOR)
    target_temp = pitch_target if pitch_target is not None else brewzilla_target
    target_source = PITCH_TARGET_NUMBER if pitch_target is not None else BREWZILLA_TARGET_SENSOR

    previous, latest = _update_trend(
        hass,
        reference_temp=reference_temp,
        reference_source=reference_source,
    )
    rate = _cooling_rate(previous, latest)

    delta = None
    eta_minutes = None
    pitch_ready = False
    if reference_temp is not None and target_temp is not None:
        delta = round(reference_temp - target_temp, 2)
        pitch_ready = abs(delta) <= READY_TOLERANCE_C
        if delta > READY_TOLERANCE_C and rate is not None and rate > MIN_MEANINGFUL_RATE_C_PER_H:
            eta_minutes = round((delta / rate) * 60, 1)

    stage = _state(hass, STAGE_SENSOR, "Idle")
    control_hint = _state(hass, CONTROL_HINT_SENSOR, "observe_only")
    pump_state = _state(hass, PUMP_SWITCH, "off")
    heater_state = _state(hass, HEATER_SWITCH, "off")
    power_state = _state(hass, POWER_SWITCH, "off")
    power_w = _float(hass, BREWZILLA_POWER_SENSOR)

    status = _cooling_status(
        reference_temp=reference_temp,
        target_temp=target_temp,
        rate_c_per_h=rate,
        stage=stage,
        pump_state=pump_state,
        heater_state=heater_state,
    )

    temp_text = "—" if reference_temp is None else f"{reference_temp:.1f} °C"
    target_text = "—" if target_temp is None else f"{target_temp:.0f} °C"
    rate_text = "—" if rate is None else f"{rate:.1f} °C/h"
    eta_text = "—" if eta_minutes is None else f"{eta_minutes:.0f} min"

    if pitch_ready:
        summary = f"Pitch ready · {reference_label} {temp_text} · target {target_text}"
    elif delta is not None and delta > 0:
        summary = f"Cooling · {reference_label} {temp_text} → {target_text} · {rate_text} · ETA {eta_text}"
    elif delta is not None:
        summary = f"Below target · {reference_label} {temp_text} · target {target_text}"
    else:
        summary = f"Cooling monitor · {reference_label} {temp_text} · target {target_text}"

    return {
        "status": status,
        "summary": summary,
        "reference_temperature": round(reference_temp, 2) if reference_temp is not None else None,
        "reference_source": reference_source,
        "reference_label": reference_label,
        "output_temperature": round(output_temp, 2) if output_temp is not None else None,
        "output_source": output_source,
        "kettle_temperature": round(kettle_temp, 2) if kettle_temp is not None else None,
        "target_temperature": round(target_temp, 2) if target_temp is not None else None,
        "target_source": target_source,
        "delta": delta,
        "cooling_rate_c_per_h": rate,
        "eta_minutes": eta_minutes,
        "pitch_ready": pitch_ready,
        "ready_tolerance_c": READY_TOLERANCE_C,
        "stage": stage,
        "control_hint": control_hint,
        "pump_state": pump_state,
        "heater_state": heater_state,
        "power_state": power_state,
        "power_w": power_w,
        "previous_sample_temperature": previous.temperature if previous is not None else None,
        "previous_sample_timestamp": previous.timestamp.isoformat() if previous is not None else None,
        "latest_sample_temperature": latest.temperature if latest is not None else None,
        "latest_sample_timestamp": latest.timestamp.isoformat() if latest is not None else None,
    }


def wort_cooling_attrs(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Return common wort cooling attributes."""
    return dict(snapshot)
