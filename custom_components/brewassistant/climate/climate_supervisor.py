"""BrewAssistant Climate Supervisor.

The supervisor owns target selection, not compressor switching.
It adjusts climate targets dynamically and lets Home Assistant climate
integrations handle hysteresis, compressor min-cycle and cooldown.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

DOMAIN_DATA = "brewassistant"
SUPERVISOR_ENABLED_KEY = "climate_supervisor_enabled_runtime"
SUPERVISOR_BASE_TARGET_KEY = "climate_supervisor_base_target"
SUPERVISOR_LAST_ACTION_KEY = "climate_supervisor_last_action"
SUPERVISOR_LAST_EVALUATION_KEY = "climate_supervisor_last_evaluation"

SUPERVISOR_SWITCH = "switch.brewassistant_climate_supervisor_enabled"
LEGACY_KEGERATOR_GUARD_SWITCH = "switch.brewassistant_kegerator_guard_enabled"

KEGERATOR_CLIMATE = "climate.kegerator_kylskap"
KEGERATOR_AIR_TEMP = "sensor.kyl_temperatur_4"
CARBONATION_STATUS = "sensor.brewassistant_carbonation_status"
CARBONATION_TEMP = "sensor.brewassistant_carbonation_temperature"

DEFAULT_SERVING_TARGET = 4.0
MIN_EFFECTIVE_TARGET = 3.4
MAX_EFFECTIVE_TARGET = 5.0
APPLY_INTERVAL_SECONDS = 30
TARGET_APPLY_EPSILON = 0.05
INVALID_STATES = {"unknown", "unavailable", "none", ""}
ACTIVE_CARBONATION_STATES = {"carbonating", "conditioning", "ready to serve"}


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
    value = state.attributes.get(attr)
    try:
        if value is None or str(value).lower() in INVALID_STATES:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_on(hass: HomeAssistant, entity_id: str) -> bool:
    return hass.states.is_state(entity_id, "on")


def _supervisor_enabled(hass: HomeAssistant) -> bool:
    return bool(_runtime_data(hass).get(SUPERVISOR_ENABLED_KEY)) or _is_on(hass, SUPERVISOR_SWITCH)


def _carbonation_active(hass: HomeAssistant) -> bool:
    status = (_state(hass, CARBONATION_STATUS) or "").lower()
    state = hass.states.get(CARBONATION_STATUS)
    attr_active = bool(state.attributes.get("active")) if state is not None else False
    return attr_active or status in ACTIVE_CARBONATION_STATES


def _base_target(hass: HomeAssistant) -> float:
    runtime = _runtime_data(hass)
    value = runtime.get(SUPERVISOR_BASE_TARGET_KEY)
    try:
        if value is not None:
            return round(float(value), 1)
    except (TypeError, ValueError):
        pass
    return DEFAULT_SERVING_TARGET


def _capture_base_target(hass: HomeAssistant) -> float:
    """Capture base target when supervisor is enabled."""
    runtime = _runtime_data(hass)
    if runtime.get(SUPERVISOR_BASE_TARGET_KEY) is not None:
        return _base_target(hass)

    current_target = _float_attr(hass, KEGERATOR_CLIMATE, "temperature")
    if current_target is None or current_target < 1.0 or current_target > 12.0:
        current_target = DEFAULT_SERVING_TARGET
    runtime[SUPERVISOR_BASE_TARGET_KEY] = round(current_target, 1)
    return round(current_target, 1)


def _effective_target(base_target: float, delta: float | None) -> tuple[float, str, str]:
    """Return dynamic climate target, demand label and reason."""
    if delta is None:
        return base_target, "unknown", "missing air temperature delta"

    if delta >= 2.0:
        target = base_target - 0.6
        return target, "strong_cooling", "air is far above target; lowering climate target"
    if delta >= 1.0:
        target = base_target - 0.4
        return target, "cooling", "air is above target; using lower climate target"
    if delta >= 0.5:
        target = base_target - 0.2
        return target, "mild_cooling", "air is slightly above target; nudging target lower"
    if delta <= -0.7:
        target = base_target + 0.4
        return target, "relax", "air is below target; relaxing climate target"
    if delta <= -0.3:
        target = base_target + 0.2
        return target, "hold_warm", "air is slightly below target; easing cooling demand"
    return base_target, "hold", "air is close to target"


def _clamp_target(value: float) -> float:
    return round(max(MIN_EFFECTIVE_TARGET, min(MAX_EFFECTIVE_TARGET, value)), 1)


def build_climate_supervisor_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    """Build current Climate Supervisor snapshot."""
    runtime = _runtime_data(hass)
    enabled = _supervisor_enabled(hass)
    carbonation_active = _carbonation_active(hass)
    carbonation_status = _state(hass, CARBONATION_STATUS) or "unknown"
    air_temp = _float_state(hass, KEGERATOR_AIR_TEMP)
    carbonation_temp = _float_state(hass, CARBONATION_TEMP)
    climate_state = _state(hass, KEGERATOR_CLIMATE)
    current_climate_target = _float_attr(hass, KEGERATOR_CLIMATE, "temperature")
    base_target = _base_target(hass)
    delta = round(air_temp - base_target, 2) if air_temp is not None else None
    raw_effective, demand, dynamic_reason = _effective_target(base_target, delta)
    effective_target = _clamp_target(raw_effective)
    target_delta = None
    if current_climate_target is not None:
        target_delta = round(effective_target - current_climate_target, 2)

    mode = "standby"
    status = "disabled"
    action = "none"
    reason = "supervisor disabled"
    control_action = "none"

    if enabled and carbonation_active:
        mode = "carbonation_serving"
        if air_temp is None:
            status = "unavailable"
            reason = f"missing air temperature source {KEGERATOR_AIR_TEMP}"
        elif climate_state is None:
            status = "unavailable"
            reason = f"missing climate controller {KEGERATOR_CLIMATE}"
        else:
            status = demand
            action = "apply_target" if target_delta is None or abs(target_delta) >= TARGET_APPLY_EPSILON or climate_state == "off" else "hold_target"
            control_action = "apply" if action == "apply_target" else "none"
            reason = dynamic_reason
    elif enabled:
        status = "standby"
        reason = "no active carbonation/serving scope detected"

    return {
        "enabled": enabled,
        "mode": mode,
        "status": status,
        "action": action,
        "control_action": control_action,
        "reason": reason,
        "base_target_temperature": base_target,
        "effective_air_target": effective_target,
        "air_temperature": round(air_temp, 2) if air_temp is not None else None,
        "air_delta": delta,
        "cooling_demand": demand,
        "controller_entity": KEGERATOR_CLIMATE,
        "controller_state": climate_state,
        "controller_target_temperature": current_climate_target,
        "target_delta": target_delta,
        "air_temperature_entity": KEGERATOR_AIR_TEMP,
        "carbonation_active": carbonation_active,
        "carbonation_status": carbonation_status,
        "carbonation_temperature": carbonation_temp,
        "legacy_guard_enabled": _is_on(hass, LEGACY_KEGERATOR_GUARD_SWITCH),
        "last_control_action": runtime.get(SUPERVISOR_LAST_ACTION_KEY),
        "last_evaluation": runtime.get(SUPERVISOR_LAST_EVALUATION_KEY),
        "summary": f"{status} · air {air_temp:.1f} °C → target {effective_target:.1f} °C · {reason}" if air_temp is not None else f"{status} · {reason}",
        "source": "python_climate_supervisor",
    }


async def async_apply_climate_supervisor(hass: HomeAssistant) -> dict[str, Any]:
    """Apply Climate Supervisor target once if enabled and in scope."""
    runtime = _runtime_data(hass)
    runtime[SUPERVISOR_LAST_EVALUATION_KEY] = dt_util.utcnow().isoformat()
    snapshot = build_climate_supervisor_snapshot(hass)
    if snapshot.get("control_action") != "apply":
        return snapshot

    effective_target = snapshot.get("effective_air_target")
    if effective_target is None:
        return snapshot

    attempt = {
        "action": "climate_set_temperature",
        "entity_id": KEGERATOR_CLIMATE,
        "at": dt_util.utcnow().isoformat(),
        "effective_air_target": effective_target,
        "base_target_temperature": snapshot.get("base_target_temperature"),
        "air_temperature": snapshot.get("air_temperature"),
        "air_delta": snapshot.get("air_delta"),
        "before_state": snapshot.get("controller_state"),
        "before_target": snapshot.get("controller_target_temperature"),
        "result": "attempting",
    }
    runtime[SUPERVISOR_LAST_ACTION_KEY] = attempt

    try:
        if snapshot.get("legacy_guard_enabled"):
            await hass.services.async_call(
                "switch",
                "turn_off",
                {"entity_id": LEGACY_KEGERATOR_GUARD_SWITCH},
                blocking=True,
            )

        if snapshot.get("controller_state") == "off":
            await hass.services.async_call(
                "climate",
                "set_hvac_mode",
                {"entity_id": KEGERATOR_CLIMATE, "hvac_mode": "cool"},
                blocking=True,
            )

        await hass.services.async_call(
            "climate",
            "set_temperature",
            {"entity_id": KEGERATOR_CLIMATE, "temperature": float(effective_target)},
            blocking=True,
        )
        await asyncio.sleep(1)
        after = build_climate_supervisor_snapshot(hass)
        attempt["after_state"] = after.get("controller_state")
        attempt["after_target"] = after.get("controller_target_temperature")
        attempt["result"] = "applied" if after.get("controller_target_temperature") == effective_target else "attempted_no_target_change"
    except Exception as err:  # noqa: BLE001 - expose HA service failure in diagnostics
        attempt["result"] = "error"
        attempt["error"] = str(err)

    runtime[SUPERVISOR_LAST_ACTION_KEY] = attempt
    return build_climate_supervisor_snapshot(hass)


async def async_enable_climate_supervisor(hass: HomeAssistant) -> None:
    """Enable Climate Supervisor."""
    runtime = _runtime_data(hass)
    runtime[SUPERVISOR_ENABLED_KEY] = True
    _capture_base_target(hass)
    await async_apply_climate_supervisor(hass)


def async_disable_climate_supervisor(hass: HomeAssistant) -> None:
    """Disable Climate Supervisor."""
    _runtime_data(hass)[SUPERVISOR_ENABLED_KEY] = False


def supervisor_interval() -> timedelta:
    """Return supervisor apply interval."""
    return timedelta(seconds=APPLY_INTERVAL_SECONDS)
