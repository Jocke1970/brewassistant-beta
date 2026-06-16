"""Kegerator compressor guard."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from ..control_policy import SOURCE_BACKEND, request_action, section_policy

DOMAIN_DATA = "brewassistant"
GUARD_WATCHDOG_UNSUB_KEY = "kegerator_guard_watchdog_unsub"
GUARD_ENABLED_KEY = "kegerator_guard_enabled_runtime"
GUARD_LAST_ACTION_KEY = "kegerator_guard_last_action"
GUARD_LAST_EVALUATION_KEY = "kegerator_guard_last_evaluation"
GUARD_LAST_CLIMATE_ACTION_KEY = "kegerator_guard_last_climate_action"
SECTION = "kegerator_guard"
STRATEGY = "serving_carbonation_air_control"
CONTROL_OWNER = "kegerator_guard"

GUARD_SWITCH = "switch.brewassistant_kegerator_guard_enabled"
KEGERATOR_SWITCH = "switch.kegerator"
AIR_TEMP_ENTITY = "sensor.kyl_temperatur_4"
CARBONATION_STATUS_ENTITY = "sensor.brewassistant_carbonation_status"
CARBONATION_TEMP_ENTITY = "sensor.brewassistant_carbonation_temperature"
KEGERATOR_CLIMATE_ENTITY = "climate.kegerator_kylskap"
KEGERATOR_CLIMATE_RESTART_TARGET = 4.0
CLIMATE_OFF_STATES = {"off", "unknown", "unavailable", "none", ""}

# climate.kegerator_kylskap is the protected cooling controller and must not be
# disabled by the guard on Home Assistant restart. The kegerator climate is owned
# by Home Assistant's climate layer and should remain available/on unless the
# operator explicitly disables it.
CLIMATE_CONFLICT_ENTITIES = (
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
    """Return climate controllers that may conflict with guard control."""
    conflicts: list[str] = []
    for entity_id in CLIMATE_CONFLICT_ENTITIES:
        state = _state(hass, entity_id)
        if state is not None and state != "off":
            conflicts.append(entity_id)
    return conflicts


def _summary(status: str, air_temp: float | None, action: str, reason: str) -> str:
    air = "—" if air_temp is None else f"{air_temp:.1f} °C"
    return f"{status} · air {air} · {action} · {reason}"


def _command_for_action(action: str) -> str | None:
    if action == "turn_on":
        return "kegerator_guard_on"
    if action == "turn_off":
        return "kegerator_guard_off"
    return None


def _desired_power(control_action: str, compressor_on: bool) -> str:
    if control_action == "turn_on":
        return "on"
    if control_action == "turn_off":
        return "off"
    return "on" if compressor_on else "off"


async def async_restore_kegerator_climate_if_needed(
    hass: HomeAssistant,
    *,
    source: str = "watchdog",
) -> dict[str, Any]:
    """Ensure the kegerator climate is cooling after HA restart.

    This is intentionally simple and safety-first:
    if kegerator guard is enabled and the climate entity is off/unknown/unavailable,
    restore cool mode and a conservative 4 °C target.
    """
    runtime = _runtime_data(hass)
    climate_state_obj = hass.states.get(KEGERATOR_CLIMATE_ENTITY)
    climate_state = climate_state_obj.state if climate_state_obj is not None else "missing"
    enabled = _guard_enabled(hass)

    result = {
        "at": dt_util.utcnow().isoformat(),
        "source": source,
        "enabled": enabled,
        "climate_entity": KEGERATOR_CLIMATE_ENTITY,
        "climate_state": climate_state,
        "target_temperature": KEGERATOR_CLIMATE_RESTART_TARGET,
        "action": "none",
        "status": "ok",
    }

    if not enabled:
        result["status"] = "disabled"
        result["reason"] = "kegerator guard is disabled"
        runtime["kegerator_climate_restart_last_action"] = result
        return result

    if climate_state not in CLIMATE_OFF_STATES and climate_state != "missing":
        result["reason"] = "climate already active"
        runtime["kegerator_climate_restart_last_action"] = result
        return result

    try:
        await hass.services.async_call(
            "climate",
            "set_temperature",
            {
                "entity_id": KEGERATOR_CLIMATE_ENTITY,
                "temperature": KEGERATOR_CLIMATE_RESTART_TARGET,
            },
            blocking=True,
        )
        await hass.services.async_call(
            "climate",
            "set_hvac_mode",
            {
                "entity_id": KEGERATOR_CLIMATE_ENTITY,
                "hvac_mode": "cool",
            },
            blocking=True,
        )
        result["action"] = "restore_cool"
        result["status"] = "restored"
        result["reason"] = f"{KEGERATOR_CLIMATE_ENTITY} was {climate_state}; restored to cool"
        await hass.services.async_call(
            "persistent_notification",
            "create",
            {
                "notification_id": "brewassistant_kegerator_climate_restart_guard",
                "title": "Kegerator climate restored",
                "message": (
                    f"{KEGERATOR_CLIMATE_ENTITY} was {climate_state}. "
                    f"BrewAssistant restored cool mode and target "
                    f"{KEGERATOR_CLIMATE_RESTART_TARGET:.1f} °C."
                ),
            },
            blocking=False,
        )
    except Exception as ex:
        result["action"] = "restore_failed"
        result["status"] = "failed"
        result["reason"] = str(ex)
        await hass.services.async_call(
            "persistent_notification",
            "create",
            {
                "notification_id": "brewassistant_kegerator_climate_restart_guard",
                "title": "Kegerator climate restore FAILED",
                "message": (
                    f"{KEGERATOR_CLIMATE_ENTITY} was {climate_state}, "
                    f"but BrewAssistant could not restore it: {ex}"
                ),
            },
            blocking=False,
        )

    runtime["kegerator_climate_restart_last_action"] = result
    return result


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
    last_climate_action = runtime.get(GUARD_LAST_CLIMATE_ACTION_KEY)

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

    command = _command_for_action(control_action)
    desired_power = _desired_power(control_action, compressor_on)

    return {
        "source": "python_kegerator_guard_backend",
        "enabled": enabled,
        "status": status,
        "action": action,
        "control_action": control_action,
        "control_command": command,
        "control_owner": CONTROL_OWNER if enabled else "none",
        "guard_strategy": STRATEGY,
        "desired_kegerator_power": desired_power,
        "actual_kegerator_power_state": kegerator_state,
        "action_needed": control_action in {"turn_on", "turn_off"},
        "reason": reason,
        "summary": _summary(status, air_temp, action, reason),
        "policy_section": SECTION,
        "policy": section_policy(hass, SECTION),
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
        "climate_conflict_entities": CLIMATE_CONFLICT_ENTITIES,
        "climate_conflicts": conflicts,
        "climate_conflict": bool(conflicts),
        "climate_conflict_action": "turn_off" if conflicts and enabled else "none",
        "last_climate_conflict_action": last_climate_action,
        "kegerator_climate_entity": KEGERATOR_CLIMATE_ENTITY,
        "kegerator_climate_state": hass.states.get(KEGERATOR_CLIMATE_ENTITY).state if hass.states.get(KEGERATOR_CLIMATE_ENTITY) is not None else None,
        "kegerator_climate_restart_target": KEGERATOR_CLIMATE_RESTART_TARGET,
        "last_climate_restart_action": runtime.get("kegerator_climate_restart_last_action"),
        "last_control_action": last_action,
        "last_policy_result": last_action,
        "last_policy_status": last_action.get("status") if isinstance(last_action, dict) else None,
        "last_policy_summary": last_action.get("summary") if isinstance(last_action, dict) else None,
        "last_evaluation": last_evaluation,
        "watchdog_active": runtime.get(GUARD_WATCHDOG_UNSUB_KEY) is not None,
        "mode": STRATEGY,
    }


async def async_apply_kegerator_guard(hass: HomeAssistant) -> dict[str, Any]:
    """Apply the kegerator guard once if enabled."""
    runtime = _runtime_data(hass)
    runtime[GUARD_LAST_EVALUATION_KEY] = dt_util.utcnow().isoformat()
    await async_restore_kegerator_climate_if_needed(hass, source="kegerator_guard_watchdog")
    snapshot = build_kegerator_guard_snapshot(hass)
    action = snapshot.get("control_action")
    command = snapshot.get("control_command")

    if not snapshot.get("enabled") or action not in {"turn_on", "turn_off"} or not isinstance(command, str):
        return snapshot

    result = await request_action(
        hass,
        section=SECTION,
        command=command,
        source=SOURCE_BACKEND,
        reason=f"Kegerator guard: {snapshot.get('reason')}",
        context={
            "control_owner": CONTROL_OWNER,
            "guard_strategy": STRATEGY,
            "control_action": action,
            "desired_kegerator_power": snapshot.get("desired_kegerator_power"),
            "actual_kegerator_power_state": snapshot.get("actual_kegerator_power_state"),
            "air_temperature": snapshot.get("air_temperature"),
            "kegerator_state": snapshot.get("kegerator_state"),
            "compressor_on": snapshot.get("compressor_on"),
            "on_minutes": snapshot.get("on_minutes"),
            "off_minutes": snapshot.get("off_minutes"),
            "start_temperature": snapshot.get("start_temperature"),
            "stop_temperature": snapshot.get("stop_temperature"),
            "safety_low_temperature": snapshot.get("safety_low_temperature"),
            "climate_conflicts": snapshot.get("climate_conflicts"),
        },
    )
    runtime[GUARD_LAST_ACTION_KEY] = result
    return build_kegerator_guard_snapshot(hass)


async def async_setup_kegerator_guard(hass: HomeAssistant) -> None:
    """Install an always-on watchdog that applies the guard when the switch is on."""
    data = _runtime_data(hass)
    if data.get(GUARD_WATCHDOG_UNSUB_KEY) is not None:
        return

    async def _tick(now: datetime) -> None:
        await async_apply_kegerator_guard(hass)

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

    conflicts = _climate_conflicts(hass)
    if conflicts:
        data[GUARD_LAST_CLIMATE_ACTION_KEY] = {
            "at": dt_util.utcnow().isoformat(),
            "action": "climate.turn_off",
            "entity_id": conflicts,
            "reason": "avoid controller conflict while guard is enabled",
        }
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
