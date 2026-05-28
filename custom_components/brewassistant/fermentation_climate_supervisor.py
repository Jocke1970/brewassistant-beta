"""Monitor-only fermentation climate supervisor snapshot."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

DOMAIN_DATA = "brewassistant"
ENABLED_KEY = "fermentation_climate_supervisor_enabled_runtime"
LAST_EVALUATION_KEY = "fermentation_climate_supervisor_last_evaluation"

SUPERVISOR_SWITCH = "switch.brewassistant_fermentation_climate_supervisor_enabled"
AIR_TARGET_SENSOR = "sensor.brewassistant_fermentation_effective_air_target"
FERMENTATION_CLIMATE = "climate.fermentation_chamber"
APPLY_INTERVAL_SECONDS = 30
TARGET_EPSILON = 0.05
INVALID_STATES = {"unknown", "unavailable", "none", ""}


def _runtime_data(hass: HomeAssistant) -> dict[str, Any]:
    """Return BrewAssistant hass.data bucket."""
    return hass.data.setdefault(DOMAIN_DATA, {})


def _state(hass: HomeAssistant, entity_id: str) -> str | None:
    state = hass.states.get(entity_id)
    if state is None or state.state in INVALID_STATES:
        return None
    return str(state.state)


def _float_state(hass: HomeAssistant, entity_id: str) -> float | None:
    raw = _state(hass, entity_id)
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _float_attr(hass: HomeAssistant, entity_id: str, attr: str) -> float | None:
    state = hass.states.get(entity_id)
    if state is None:
        return None
    try:
        value = state.attributes.get(attr)
        if value is None or str(value).lower() in INVALID_STATES:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _bool_attr(hass: HomeAssistant, entity_id: str, attr: str) -> bool | None:
    state = hass.states.get(entity_id)
    if state is None:
        return None
    value = state.attributes.get(attr)
    if isinstance(value, bool):
        return value
    return None


def _attr(hass: HomeAssistant, entity_id: str, attr: str) -> Any:
    state = hass.states.get(entity_id)
    if state is None:
        return None
    return state.attributes.get(attr)


def _enabled(hass: HomeAssistant) -> bool:
    return bool(_runtime_data(hass).get(ENABLED_KEY)) or hass.states.is_state(SUPERVISOR_SWITCH, "on")


def _climate_target(hass: HomeAssistant) -> float | None:
    low = _float_attr(hass, FERMENTATION_CLIMATE, "target_temp_low")
    high = _float_attr(hass, FERMENTATION_CLIMATE, "target_temp_high")
    single = _float_attr(hass, FERMENTATION_CLIMATE, "temperature")
    if low is not None and high is not None:
        return round((low + high) / 2, 2)
    return single


def _recommended_target(hass: HomeAssistant) -> float | None:
    value = _float_state(hass, AIR_TARGET_SENSOR)
    if value is not None:
        return value
    return _float_attr(hass, AIR_TARGET_SENSOR, "effective_air_target")


def build_fermentation_climate_supervisor_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    """Build current monitor-only fermentation climate supervisor snapshot."""
    runtime = _runtime_data(hass)
    enabled = _enabled(hass)
    runtime[LAST_EVALUATION_KEY] = dt_util.utcnow().isoformat()

    air_target_state = _state(hass, AIR_TARGET_SENSOR)
    ready = _bool_attr(hass, AIR_TARGET_SENSOR, "ready") is True
    scope_active = _bool_attr(hass, AIR_TARGET_SENSOR, "scope_active") is True
    test_mode_active = _bool_attr(hass, AIR_TARGET_SENSOR, "test_mode_active") is True
    mode = _attr(hass, AIR_TARGET_SENSOR, "mode") or "standby"
    demand = _attr(hass, AIR_TARGET_SENSOR, "demand") or "standby"
    air_target_reason = _attr(hass, AIR_TARGET_SENSOR, "reason") or "unknown"
    recommended = _recommended_target(hass)

    climate_state = _state(hass, FERMENTATION_CLIMATE)
    climate_target = _climate_target(hass)
    chamber_air = _float_attr(hass, AIR_TARGET_SENSOR, "chamber_air_temperature")
    liquid = _float_attr(hass, AIR_TARGET_SENSOR, "liquid_temperature")
    liquid_target = _float_attr(hass, AIR_TARGET_SENSOR, "liquid_target_temperature")
    liquid_delta = _float_attr(hass, AIR_TARGET_SENSOR, "liquid_delta")
    raw_air_target = _float_attr(hass, AIR_TARGET_SENSOR, "raw_air_target")
    min_air_target = _float_attr(hass, AIR_TARGET_SENSOR, "min_air_target")
    max_air_target = _float_attr(hass, AIR_TARGET_SENSOR, "max_air_target")
    clamp_applied = _bool_attr(hass, AIR_TARGET_SENSOR, "clamp_applied") is True
    clamp_reason = _attr(hass, AIR_TARGET_SENSOR, "clamp_reason")
    target_plausible = _attr(hass, AIR_TARGET_SENSOR, "target_plausible_for_mode")

    target_delta = None
    if recommended is not None and climate_target is not None:
        target_delta = round(recommended - climate_target, 2)

    status = "disabled"
    action = "none"
    reason = "supervisor disabled"

    if enabled:
        if not scope_active:
            status = "standby"
            reason = "no active fermentation or cold-crash scope"
        elif not ready:
            status = "unavailable"
            reason = air_target_reason
        elif climate_state is None:
            status = "unavailable"
            reason = f"missing climate entity {FERMENTATION_CLIMATE}"
        else:
            status = str(demand)
            if target_delta is None:
                action = "observe"
            elif abs(target_delta) >= TARGET_EPSILON:
                action = "would_apply_target"
            else:
                action = "hold_target"
            reason = air_target_reason

    summary = f"{status} · {reason}"
    if recommended is not None:
        summary = f"{status} · recommended {recommended:.1f} °C · {reason}"

    return {
        "enabled": enabled,
        "mode": mode,
        "status": status,
        "action": action,
        "reason": reason,
        "ready": ready,
        "scope_active": scope_active,
        "test_mode_active": test_mode_active,
        "demand": demand,
        "recommended_air_target": recommended,
        "air_target_sensor_state": air_target_state,
        "raw_air_target": raw_air_target,
        "min_air_target": min_air_target,
        "max_air_target": max_air_target,
        "clamp_applied": clamp_applied,
        "clamp_reason": clamp_reason,
        "target_plausible_for_mode": target_plausible,
        "controller_entity": FERMENTATION_CLIMATE,
        "controller_state": climate_state,
        "controller_target_temperature": climate_target,
        "target_delta": target_delta,
        "chamber_air_temperature": chamber_air,
        "liquid_temperature": liquid,
        "liquid_target_temperature": liquid_target,
        "liquid_delta": liquid_delta,
        "last_evaluation": runtime.get(LAST_EVALUATION_KEY),
        "summary": summary,
        "source": "python_fermentation_climate_supervisor",
        "mode_scope": "monitor_only",
    }


async def async_enable_fermentation_climate_supervisor(hass: HomeAssistant) -> None:
    """Enable monitor-only supervisor."""
    _runtime_data(hass)[ENABLED_KEY] = True
    build_fermentation_climate_supervisor_snapshot(hass)


def async_disable_fermentation_climate_supervisor(hass: HomeAssistant) -> None:
    """Disable monitor-only supervisor."""
    _runtime_data(hass)[ENABLED_KEY] = False


def fermentation_supervisor_interval() -> timedelta:
    """Return monitor interval."""
    return timedelta(seconds=APPLY_INTERVAL_SECONDS)
