"""Kegerator compressor guard.

This module provides an emergency-safe serving/carbonation controller for the
kegerator compressor. It intentionally controls air temperature only and is
meant to prevent short cycling while a keg is carbonating/serving.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

DOMAIN_DATA = "brewassistant"
GUARD_UNSUB_KEY = "kegerator_guard_unsub"
GUARD_WATCHDOG_UNSUB_KEY = "kegerator_guard_watchdog_unsub"
GUARD_ENABLED_KEY = "kegerator_guard_enabled_runtime"
GUARD_LAST_ACTION_KEY = "kegerator_guard_last_action"
GUARD_LAST_EVALUATION_KEY = "kegerator_guard_last_evaluation"

GUARD_SWITCH = "switch.brewassistant_kegerator_guard_enabled"
KEGERATOR_SWITCH = "switch.kegerator"
AIR_TEMP_ENTITY = "sensor.kyl_temperatur_4"
CARBONATION_STATUS_ENTITY = "sensor.brewassistant_carbonation_status"
CARBONATION_TEMP_ENTITY = "sensor.brewassistant_carbonation_temperature"

CLIMATE_CONFLICT_ENTITIES = (
    "climate.kegerator_kylskap",
    "climate.fermentation_chamber",
)

TARGET_TEMP = 4.0
START_TEMP = 4.8
STOP_TEMP = 3.4
SAFETY_LOW_TEMP = 1.0
MIN_ON_MINUTES = 10.0
MIN_OFF_MINUTES = 6.0
INTERVAL_SECONDS = 30
INVALID_STATES = {"unknown", "unavailable", "none", ""}


def _runtime_data(hass: HomeAssistant) -> dict[str, Any]:
    """Return BrewAssistant hass.data bucket."""
    return hass.data.setdefault(DOMAIN_DATA, {})


def _state(hass: HomeAssistant, entity_id: str) -> str | None:
    state = hass.states.get(entity_id)
    if state is None or state.state in INVALID_STATES:
        return None
    return state.state


def _float_state(hass: HomeAssistant, entity_id: str) -> float | None:
    raw = _state(hass, entity_id)
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _is_on(hass: HomeAssistant, entity_id: str) -> bool:
    return hass.states.is_state(entity_id, "on")


def _guard_enabled(hass: HomeAssistant) -> bool:
    """Return guard enabled state from runtime flag or entity state."""
    return bool(_runtime_data(hass).get(GUARD_ENABLED_KEY)) or _is_on(hass, GUARD_SWITCH)


def _minutes_since_changed(hass: HomeAssistant, entity_id: str) -> float | None:
    state = hass.states.get(entity_id)
    if state is None:
        return None
    changed = state.last_changed
    now = dt_util.utcnow()
    return max(0.0, (now - changed).total_seconds() / 60)


def _climate_conflicts(hass: HomeAssistant) -> list[str]:
    """Return climate controllers that may fight the guard."""
    conflicts: list[str] = []
    for entity_id in CLIMATE_CONFLICT_ENTITIES:
        state = _state(hass, entity_id)
        if state is not None and state != "off":
            conflicts.append(entity_id)
    return conflicts


def _summary(status: str, air_temp: float | None, action: str, reason: str) -> str:
    air = "—" if air_temp is None else f"{air_temp:.1f} °C"
    return f"{status} · air {air} · {action} · {reason}"


def build_kegerator_guard_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    """Build current kegerator guard state."""
    enabled = _guard_enabled(hass)
    air_temp = _float_state(hass, AIR_TEMP_ENTITY)
    carbonation_temp = _float_state(hass, CARBONATION_TEMP_ENTITY)
    carbonation_status = _state(hass, CARBONATION_STATUS_ENTITY) or "unknown"
    kegerator_state = _state(hass, KEGERATOR_SWITCH)
    switch_available = kegerator_state is not None
    compressor_on = kegerator_state == "on"
    elapsed = _minutes_since_changed(hass, KEGERATOR_SWITCH)
    on_minutes = round(elapsed or 0, 1) if compressor_on else 0.0
    off_minutes = round(elapsed or 0, 1) if switch_available and not compressor_on else 0.0
    conflicts = _climate_conflicts(hass)
    runtime = _runtime_data(hass)
    last_action = runtime.get(GUARD_LAST_ACTION_KEY)
    last_evaluation = runtime.get(GUARD_LAST_EVALUATION_KEY)

    status = "disabled"
    action = "none"
    reason = "guard disabled"
    control_action = "none"

    if not enabled:
        status = "disabled"
    elif air_temp is None:
        status = "unavailable"
        reason = f"missing air temperature source {AIR_TEMP_ENTITY}"
    elif not switch_available:
        status = "unavailable"
        reason = f"missing kegerator switch {KEGERATOR_SWITCH}"
    elif compressor_on and air_temp <= SAFETY_LOW_TEMP:
        status = "safety_stop"
        action = "turn_off"
        control_action = "turn_off"
        reason = f"air temperature below safety floor {SAFETY_LOW_TEMP:.1f} °C"
    elif compressor_on and air_temp <= STOP_TEMP and on_minutes >= MIN_ON_MINUTES:
        status = "stop_ready"
        action = "turn_off"
        control_action = "turn_off"
        reason = f"air temperature reached stop threshold {STOP_TEMP:.1f} °C and min-on is satisfied"
    elif compressor_on and air_temp <= STOP_TEMP:
        status = "min_on_hold"
        action = "keep_on"
        reason = f"air is cold enough but compressor must run at least {MIN_ON_MINUTES:.0f} min"
    elif compressor_on:
        status = "cooling"
        action = "keep_on"
        reason = "compressor running toward air stop threshold"
    elif air_temp >= START_TEMP and off_minutes >= MIN_OFF_MINUTES:
        status = "start_ready"
        action = "turn_on"
        control_action = "turn_on"
        reason = f"air temperature reached start threshold {START_TEMP:.1f} °C and min-off is satisfied"
    elif air_temp >= START_TEMP:
        status = "min_off_hold"
        action = "keep_off"
        reason = f"cooling is needed but compressor must rest at least {MIN_OFF_MINUTES:.0f} min"
    else:
        status = "holding"
        action = "keep_off"
        reason = "air temperature is inside serving/carbonation band"

    return {
        "enabled": enabled,
        "status": status,
        "action": action,
        "control_action": control_action,
        "reason": reason,
        "summary": _summary(status, air_temp, action, reason),
        "air_temperature": round(air_temp, 2) if air_temp is not None else None,
        "target_temperature": TARGET_TEMP,
        "start_temperature": START_TEMP,
        "stop_temperature": STOP_TEMP,
        "safety_low_temperature": SAFETY_LOW_TEMP,
        "min_on_minutes": MIN_ON_MINUTES,
        "min_off_minutes": MIN_OFF_MINUTES,
        "compressor_on": compressor_on,
        "kegerator_state": kegerator_state,
        "on_minutes": on_minutes,
        "off_minutes": off_minutes,
        "air_temperature_entity": AIR_TEMP_ENTITY,
        "kegerator_switch_entity": KEGERATOR_SWITCH,
        "carbonation_status": carbonation_status,
        "carbonation_temperature": carbonation_temp,
        "climate_conflicts": conflicts,
        "climate_conflict": bool(conflicts),
        "last_control_action": last_action,
        "last_evaluation": last_evaluation,
        "watchdog_active": runtime.get(GUARD_WATCHDOG_UNSUB_KEY) is not None,
        "mode": "serving_carbonation_air_control",
    }


async def async_apply_kegerator_guard(hass: HomeAssistant) -> dict[str, Any]:
    """Apply the kegerator guard once if enabled."""
    runtime = _runtime_data(hass)
    runtime[GUARD_LAST_EVALUATION_KEY] = dt_util.utcnow().isoformat()
    snapshot = build_kegerator_guard_snapshot(hass)
    action = snapshot.get("control_action")

    if not snapshot.get("enabled") or action not in {"turn_on", "turn_off"}:
        return snapshot

    await hass.services.async_call(
        "switch",
        str(action),
        {"entity_id": KEGERATOR_SWITCH},
        blocking=True,
    )
    runtime[GUARD_LAST_ACTION_KEY] = {
        "action": action,
        "entity_id": KEGERATOR_SWITCH,
        "at": dt_util.utcnow().isoformat(),
        "reason": snapshot.get("reason"),
        "air_temperature": snapshot.get("air_temperature"),
    }
    return build_kegerator_guard_snapshot(hass)


async def async_setup_kegerator_guard(hass: HomeAssistant) -> None:
    """Install an always-on watchdog that applies the guard when the switch is on."""
    data = _runtime_data(hass)
    if data.get(GUARD_WATCHDOG_UNSUB_KEY) is not None:
        return

    def _tick(now: datetime) -> None:
        hass.async_create_task(async_apply_kegerator_guard(hass))

    data[GUARD_WATCHDOG_UNSUB_KEY] = async_track_time_interval(
        hass,
        _tick,
        timedelta(seconds=INTERVAL_SECONDS),
    )
    await async_apply_kegerator_guard(hass)


async def async_enable_kegerator_guard(hass: HomeAssistant) -> None:
    """Enable periodic kegerator guard control."""
    data = _runtime_data(hass)
    data[GUARD_ENABLED_KEY] = True

    # Prevent generic/dual thermostats from fighting direct compressor guard control.
    conflicts = _climate_conflicts(hass)
    if conflicts:
        await hass.services.async_call(
            "climate",
            "turn_off",
            {"entity_id": conflicts},
            blocking=True,
        )

    await async_setup_kegerator_guard(hass)
    await async_apply_kegerator_guard(hass)


def async_disable_kegerator_guard(hass: HomeAssistant) -> None:
    """Disable kegerator guard control."""
    _runtime_data(hass)[GUARD_ENABLED_KEY] = False
