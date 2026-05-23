"""Semi-automatic BrewZilla orchestration helpers.

This layer is intentionally conservative.
BrewAssistant may recommend or apply BrewZilla targets,
but dangerous actions are disabled unless explicitly enabled.
"""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

BREWDAY_TARGET_SENSOR = "sensor.brewassistant_brewday_target_temperature"
BREWDAY_STATE_SENSOR = "sensor.brewassistant_brewday_runtime_state"
BREWZILLA_TARGET_NUMBER = "number.brewzilla_target_temperature"
BREWZILLA_CONNECTION_SENSOR = "sensor.brewzilla_connection"

ORCHESTRATION_ENABLED = "input_boolean.brewassistant_brewzilla_orchestration_enabled"
APPLY_TARGET_ENABLED = "input_boolean.brewassistant_brewzilla_apply_target_temp"
ALLOW_HEATER_CONTROL = "input_boolean.brewassistant_brewzilla_allow_heater_control"
ALLOW_PUMP_CONTROL = "input_boolean.brewassistant_brewzilla_allow_pump_control"
ALLOW_BOIL_MODE = "input_boolean.brewassistant_brewzilla_allow_boil_mode"
SAFE_MODE = "input_boolean.brewassistant_brewzilla_safe_mode"


def _state(hass: HomeAssistant, entity_id: str, default: str | None = None) -> str | None:
    entity_state = hass.states.get(entity_id)
    if entity_state is None:
        return default
    return entity_state.state


def _float(hass: HomeAssistant, entity_id: str) -> float | None:
    raw = _state(hass, entity_id)
    if raw in {None, "unknown", "unavailable", "none", ""}:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _bool(hass: HomeAssistant, entity_id: str, default: bool = False) -> bool:
    return (_state(hass, entity_id, "off") or "off").lower() == "on"


def build_orchestration_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    """Build orchestration state snapshot."""

    orchestration_enabled = _bool(hass, ORCHESTRATION_ENABLED)
    apply_target = _bool(hass, APPLY_TARGET_ENABLED)
    allow_heater = _bool(hass, ALLOW_HEATER_CONTROL)
    allow_pump = _bool(hass, ALLOW_PUMP_CONTROL)
    allow_boil = _bool(hass, ALLOW_BOIL_MODE)
    safe_mode = _bool(hass, SAFE_MODE, True)

    brewday_target = _float(hass, BREWDAY_TARGET_SENSOR)
    brewzilla_target = _float(hass, BREWZILLA_TARGET_NUMBER)
    brewday_state = _state(hass, BREWDAY_STATE_SENSOR, "inactive")
    connection = _state(hass, BREWZILLA_CONNECTION_SENSOR, "unknown")

    connected = connection == "connected"

    requested_target = brewday_target
    applied_target = brewzilla_target

    reason = "Observe only"
    orchestration_mode = "observe"
    safety_state = "safe"

    if not orchestration_enabled:
        reason = "Orchestration disabled"

    elif not connected:
        reason = "BrewZilla disconnected"
        orchestration_mode = "blocked"

    elif brewday_state in {"inactive", "completed"}:
        reason = f"Brewday runtime {brewday_state}"
        orchestration_mode = "idle"

    elif requested_target is None:
        reason = "No Brewday target available"
        orchestration_mode = "idle"

    elif safe_mode:
        reason = "Safe mode enabled"
        orchestration_mode = "safe-mode"

    elif apply_target:
        reason = "Target sync active"
        orchestration_mode = "target-sync"

    if allow_heater or allow_pump or allow_boil:
        safety_state = "dangerous-controls-enabled"

    return {
        "connected": connected,
        "orchestration_enabled": orchestration_enabled,
        "apply_target_enabled": apply_target,
        "allow_heater_control": allow_heater,
        "allow_pump_control": allow_pump,
        "allow_boil_mode": allow_boil,
        "safe_mode": safe_mode,
        "requested_target": requested_target,
        "applied_target": applied_target,
        "brewday_state": brewday_state,
        "orchestration_mode": orchestration_mode,
        "safety_state": safety_state,
        "control_reason": reason,
    }
