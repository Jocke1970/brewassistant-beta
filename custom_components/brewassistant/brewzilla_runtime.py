"""BrewZilla hardware normalization helpers.

This module is intentionally read-only. It normalizes likely BrewZilla/RAPT
entities into a stable BrewAssistant hardware snapshot while we learn what
RAPT exposes in Home Assistant.
"""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

BAD_STATES = {"unknown", "unavailable", "none", ""}

# Current known/preferred entities. These are deliberately easy to patch once
# RAPT exposes the real BrewZilla entity set.
BREWZILLA_POWER_SWITCH = "switch.brewzilla"
BREWZILLA_POWER_SENSOR = "sensor.brewzilla_power"
BREWZILLA_TEMP_SENSOR = "sensor.brewzilla_temperature"
BREWZILLA_TARGET_SENSOR = "sensor.brewzilla_target_temperature"
BREWZILLA_MODE_SENSOR = "sensor.brewzilla_mode"
BREWZILLA_PUMP_SWITCH = "switch.brewzilla_pump"
BREWZILLA_HEAT_SWITCH = "switch.brewzilla_heating"
BREWZILLA_PROFILE_SENSOR = "sensor.brewzilla_profile"

RUNTIME_TARGET_SENSOR = "sensor.brewassistant_brewday_target_temperature"
RUNTIME_STATE_SENSOR = "sensor.brewassistant_brewday_runtime_state"
RUNTIME_STAGE_SENSOR = "sensor.brewassistant_brewday_runtime_stage"
RUNTIME_STEP_SENSOR = "sensor.brewassistant_brewday_runtime_step"


def _state(hass: HomeAssistant, entity_id: str, default: str | None = None) -> str | None:
    state = hass.states.get(entity_id)
    if state is None or state.state in BAD_STATES:
        return default
    return state.state


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
    return raw.lower() in {"on", "true", "active", "running", "heat", "heating"}


def _available(hass: HomeAssistant, entity_id: str) -> bool:
    entity_state = hass.states.get(entity_id)
    return entity_state is not None and entity_state.state not in BAD_STATES


def _hardware_state(
    *,
    power_on: bool | None,
    power_w: float | None,
    current_temp: float | None,
    target_temp: float | None,
    pump_on: bool | None,
) -> str:
    if power_on is False:
        return "off"
    if power_on is None and power_w is None and current_temp is None:
        return "disconnected"
    if pump_on is True:
        return "pumping"
    if power_w is not None and power_w >= 1000:
        return "heating"
    if power_w is not None and power_w > 50:
        return "powered"
    if current_temp is not None and target_temp is not None:
        delta = target_temp - current_temp
        if delta > 1.0:
            return "heating_needed"
        if abs(delta) <= 0.5:
            return "holding"
    if power_on is True:
        return "idle"
    return "unknown"


def _summary(
    *,
    connected: bool,
    state: str,
    current_temp: float | None,
    target_temp: float | None,
    power_w: float | None,
    runtime_stage: str,
) -> str:
    if not connected:
        return "disconnected · waiting for BrewZilla entities"
    temp = "—"
    if current_temp is not None and target_temp is not None:
        temp = f"{current_temp:.1f} → {target_temp:.1f} °C"
    elif current_temp is not None:
        temp = f"{current_temp:.1f} °C"
    power = f"{power_w:.0f} W" if power_w is not None else "— W"
    return f"{state} · {runtime_stage} · {temp} · {power}"


def build_brewzilla_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    """Build a normalized BrewZilla hardware snapshot."""
    power_on = _bool_on(hass, BREWZILLA_POWER_SWITCH)
    pump_on = _bool_on(hass, BREWZILLA_PUMP_SWITCH)
    heat_on = _bool_on(hass, BREWZILLA_HEAT_SWITCH)
    power_w = _float(hass, BREWZILLA_POWER_SENSOR)
    current_temp = _float(hass, BREWZILLA_TEMP_SENSOR)
    target_temp = _float(hass, BREWZILLA_TARGET_SENSOR)
    runtime_target = _float(hass, RUNTIME_TARGET_SENSOR)
    mode = _state(hass, BREWZILLA_MODE_SENSOR, "unknown")
    profile = _state(hass, BREWZILLA_PROFILE_SENSOR, "none")
    runtime_state = _state(hass, RUNTIME_STATE_SENSOR, "idle")
    runtime_stage = _state(hass, RUNTIME_STAGE_SENSOR, "Idle")
    runtime_step = _state(hass, RUNTIME_STEP_SENSOR, "Idle")

    effective_target = target_temp if target_temp is not None else runtime_target
    temp_delta = None
    if current_temp is not None and effective_target is not None:
        temp_delta = round(current_temp - effective_target, 2)

    connected = any(
        _available(hass, entity_id)
        for entity_id in (
            BREWZILLA_POWER_SWITCH,
            BREWZILLA_POWER_SENSOR,
            BREWZILLA_TEMP_SENSOR,
            BREWZILLA_MODE_SENSOR,
        )
    )
    heating = bool(heat_on) or (power_w is not None and power_w >= 1000)
    state = _hardware_state(
        power_on=power_on,
        power_w=power_w,
        current_temp=current_temp,
        target_temp=effective_target,
        pump_on=pump_on,
    )

    return {
        "connected": connected,
        "hardware_state": state,
        "power_on": power_on,
        "power_w": power_w,
        "current_temperature": current_temp,
        "target_temperature": effective_target,
        "device_target_temperature": target_temp,
        "runtime_target_temperature": runtime_target,
        "temperature_delta": temp_delta,
        "mode": mode,
        "profile": profile,
        "pump_on": pump_on,
        "heating": heating,
        "heat_switch_on": heat_on,
        "runtime_state": runtime_state,
        "runtime_stage": runtime_stage,
        "runtime_step": runtime_step,
        "summary": _summary(
            connected=connected,
            state=state,
            current_temp=current_temp,
            target_temp=effective_target,
            power_w=power_w,
            runtime_stage=runtime_stage,
        ),
        "source_entities": {
            "power_switch": BREWZILLA_POWER_SWITCH,
            "power_sensor": BREWZILLA_POWER_SENSOR,
            "temperature_sensor": BREWZILLA_TEMP_SENSOR,
            "target_sensor": BREWZILLA_TARGET_SENSOR,
            "mode_sensor": BREWZILLA_MODE_SENSOR,
            "pump_switch": BREWZILLA_PUMP_SWITCH,
            "heat_switch": BREWZILLA_HEAT_SWITCH,
            "profile_sensor": BREWZILLA_PROFILE_SENSOR,
        },
    }


def brewzilla_attrs(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Return common BrewZilla runtime attributes."""
    return dict(snapshot)
