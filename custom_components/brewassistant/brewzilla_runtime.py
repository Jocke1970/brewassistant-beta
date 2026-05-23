"""BrewZilla hardware normalization helpers.

This module is intentionally read-only. It normalizes BrewZilla/RAPT entities
into a stable BrewAssistant hardware snapshot.
"""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

BAD_STATES = {"unknown", "unavailable", "none", ""}

BREWZILLA_POWER_SWITCH = "switch.brewzilla"
BREWZILLA_POWER_SENSOR = "sensor.brewzilla_power"
BREWZILLA_CONNECTION_SENSOR = "sensor.brewzilla_connection"
BREWZILLA_TEMP_SENSOR = "sensor.brewzilla_temperature"
BREWZILLA_TARGET_NUMBER = "number.brewzilla_target_temperature"
BREWZILLA_PUMP_SWITCH = "switch.brewzilla_pump"
BREWZILLA_HEATER_SWITCH = "switch.brewzilla_heater"
BREWZILLA_HEAT_UTILIZATION = "number.brewzilla_heat_utilization"
BREWZILLA_PUMP_UTILIZATION = "number.brewzilla_pump_utilization"

RUNTIME_TARGET_SENSOR = "sensor.brewassistant_brewday_target_temperature"
RUNTIME_STATE_SENSOR = "sensor.brewassistant_brewday_runtime_state"
RUNTIME_STAGE_SENSOR = "sensor.brewassistant_brewday_runtime_stage"
RUNTIME_STEP_SENSOR = "sensor.brewassistant_brewday_runtime_step"


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


def _bool_on(hass: HomeAssistant, entity_id: str) -> bool | None:
    raw = _state(hass, entity_id)
    if raw is None:
        return None
    return raw.lower() in {"on", "true", "active", "running", "heat", "heating", "connected"}


def _available(hass: HomeAssistant, entity_id: str) -> bool:
    entity_state = hass.states.get(entity_id)
    return entity_state is not None and entity_state.state not in BAD_STATES


def _connection_ok(hass: HomeAssistant) -> bool:
    raw = _state(hass, BREWZILLA_CONNECTION_SENSOR)
    if raw is None:
        return _available(hass, BREWZILLA_TEMP_SENSOR) or _available(hass, BREWZILLA_POWER_SENSOR)
    return raw.lower() == "connected"


def _hardware_state(
    *,
    connected: bool,
    power_on: bool | None,
    heater_on: bool | None,
    pump_on: bool | None,
    power_w: float | None,
    current_temp: float | None,
    target_temp: float | None,
) -> str:
    if not connected:
        return "disconnected"
    if power_on is False:
        return "off"
    if pump_on is True and heater_on is True:
        return "heating_pumping"
    if pump_on is True:
        return "pumping"
    if heater_on is True:
        return "heating"
    if power_w is not None and power_w >= 1000:
        return "heating"
    if power_w is not None and power_w > 50:
        return "powered"
    if current_temp is not None and target_temp is not None:
        delta_to_target = target_temp - current_temp
        if delta_to_target > 1.0:
            return "heating_needed"
        if abs(delta_to_target) <= 0.5:
            return "holding"
    if power_on is True:
        return "idle"
    return "unknown"


def _brew_mode(
    *,
    connected: bool,
    heater_on: bool | None,
    pump_on: bool | None,
    power_w: float | None,
    current_temp: float | None,
    target_temp: float | None,
) -> str:
    """Resolve intelligent brewing mode."""

    if not connected:
        return "Disconnected"

    if current_temp is not None and current_temp >= 99 and (power_w or 0) >= 1800:
        return "Boiling"

    if current_temp is not None and target_temp is not None:
        delta = target_temp - current_temp

        if delta > 5:
            if heater_on and pump_on:
                return "Heating + circulation"
            if heater_on:
                return "Heating"

        if 1 < delta <= 5:
            return "Approaching target"

        if abs(delta) <= 1:
            if pump_on:
                return "Holding target"
            return "Near target"

        if delta < -1:
            return "Overshooting"

    if pump_on and not heater_on:
        return "Pump circulation"

    if heater_on:
        return "Heating"

    return "Idle"


def _summary(
    *,
    connected: bool,
    mode: str,
    current_temp: float | None,
    target_temp: float | None,
    power_w: float | None,
    runtime_stage: str,
) -> str:
    if not connected:
        return "disconnected · waiting for BrewZilla"
    temp = "—"
    if current_temp is not None and target_temp is not None:
        temp = f"{current_temp:.1f} → {target_temp:.1f} °C"
    elif current_temp is not None:
        temp = f"{current_temp:.1f} °C"
    power = f"{power_w:.0f} W" if power_w is not None else "— W"
    return f"{mode} · {runtime_stage} · {temp} · {power}"


def build_brewzilla_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    """Build a normalized BrewZilla hardware snapshot."""
    connected = _connection_ok(hass)
    connection_state = _state(hass, BREWZILLA_CONNECTION_SENSOR, "unknown")
    power_on = _bool_on(hass, BREWZILLA_POWER_SWITCH)
    pump_on = _bool_on(hass, BREWZILLA_PUMP_SWITCH)
    heater_on = _bool_on(hass, BREWZILLA_HEATER_SWITCH)
    power_w = _float(hass, BREWZILLA_POWER_SENSOR)
    current_temp = _float(hass, BREWZILLA_TEMP_SENSOR)
    device_target = _float(hass, BREWZILLA_TARGET_NUMBER)
    runtime_target = _float(hass, RUNTIME_TARGET_SENSOR)
    heat_utilization = _float(hass, BREWZILLA_HEAT_UTILIZATION)
    pump_utilization = _float(hass, BREWZILLA_PUMP_UTILIZATION)
    runtime_state = _state(hass, RUNTIME_STATE_SENSOR, "idle")
    runtime_stage = _state(hass, RUNTIME_STAGE_SENSOR, "Idle")
    runtime_step = _state(hass, RUNTIME_STEP_SENSOR, "Idle")

    effective_target = device_target if device_target is not None and device_target >= 0 else runtime_target
    temp_delta = None
    if current_temp is not None and effective_target is not None:
        temp_delta = round(current_temp - effective_target, 2)

    state = _hardware_state(
        connected=connected,
        power_on=power_on,
        heater_on=heater_on,
        pump_on=pump_on,
        power_w=power_w,
        current_temp=current_temp,
        target_temp=effective_target,
    )

    mode = _brew_mode(
        connected=connected,
        heater_on=heater_on,
        pump_on=pump_on,
        power_w=power_w,
        current_temp=current_temp,
        target_temp=effective_target,
    )

    heating = bool(heater_on) or (power_w is not None and power_w >= 1000)

    return {
        "connected": connected,
        "connection_state": connection_state,
        "hardware_state": state,
        "mode": mode,
        "power_on": power_on,
        "power_w": power_w,
        "current_temperature": current_temp,
        "target_temperature": effective_target,
        "device_target_temperature": device_target,
        "runtime_target_temperature": runtime_target,
        "temperature_delta": temp_delta,
        "pump_on": pump_on,
        "heater_on": heater_on,
        "heating": heating,
        "heat_utilization": heat_utilization,
        "pump_utilization": pump_utilization,
        "runtime_state": runtime_state,
        "runtime_stage": runtime_stage,
        "runtime_step": runtime_step,
        "summary": _summary(
            connected=connected,
            mode=mode,
            current_temp=current_temp,
            target_temp=effective_target,
            power_w=power_w,
            runtime_stage=runtime_stage,
        ),
        "source_entities": {
            "power_switch": BREWZILLA_POWER_SWITCH,
            "power_sensor": BREWZILLA_POWER_SENSOR,
            "connection_sensor": BREWZILLA_CONNECTION_SENSOR,
            "temperature_sensor": BREWZILLA_TEMP_SENSOR,
            "target_number": BREWZILLA_TARGET_NUMBER,
            "pump_switch": BREWZILLA_PUMP_SWITCH,
            "heater_switch": BREWZILLA_HEATER_SWITCH,
            "heat_utilization": BREWZILLA_HEAT_UTILIZATION,
            "pump_utilization": BREWZILLA_PUMP_UTILIZATION,
        },
    }


def brewzilla_attrs(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Return common BrewZilla runtime attributes."""
    return dict(snapshot)
