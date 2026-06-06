"""Kegerator fan/compressor backend for BrewAssistant."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from ..const import DOMAIN

CLIMATE = "climate.kegerator_kylskap"
AIR_TEMP = "sensor.kyl_temperatur_4"
AIR_STATS = "sensor.brewassistant_kegerator_air_temperature_average"
POWER = "sensor.kegerator_power"
FAN = "switch.kegerator_fan"
FAN_POWER = "sensor.kegerator_fan_power"
CHAMBER = "climate.fermentation_chamber"

DATA_KEY = "kegerator_fan_auto"

COMPRESSOR_W = 20.0
FAN_W = 2.0
TOO_WARM_C = 0.8
TOO_COLD_C = -0.8
WARMING_C_H = 0.20
AFTER_RUN_MIN = 10.0
INTERVAL_SECONDS = 30

_BAD = {"unknown", "unavailable", "none", ""}


def kegerator_fan_auto_interval() -> timedelta:
    return timedelta(seconds=INTERVAL_SECONDS)


def _bucket(hass: HomeAssistant) -> dict[str, Any]:
    return hass.data.setdefault(DOMAIN, {}).setdefault(DATA_KEY, {})


def _state(hass: HomeAssistant, entity: str) -> str | None:
    s = hass.states.get(entity)
    return s.state if s is not None else None


def _available(hass: HomeAssistant, entity: str) -> bool:
    s = hass.states.get(entity)
    return s is not None and s.state not in _BAD


def _num_state(hass: HomeAssistant, entity: str) -> float | None:
    s = hass.states.get(entity)
    if s is None or s.state in _BAD:
        return None
    try:
        return float(str(s.state).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _attr(hass: HomeAssistant, entity: str, attr: str) -> Any:
    s = hass.states.get(entity)
    return None if s is None else s.attributes.get(attr)


def _num_attr(hass: HomeAssistant, entity: str, attr: str) -> float | None:
    value = _attr(hass, entity, attr)
    if value is None or str(value).lower() in _BAD:
        return None
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _compressor_active(power: float | None) -> bool:
    return power is not None and power > COMPRESSOR_W


def _fan_running(fan_state: str | None, fan_power: float | None) -> bool:
    return fan_state == "on" or (fan_power is not None and fan_power > FAN_W)


def _climate_enabled(state: str | None) -> bool:
    return state not in {None, "off", "unknown", "unavailable", "none", ""}


def _remember_compressor(hass: HomeAssistant, active: bool) -> tuple[str | None, float | None, bool, float]:
    data = _bucket(hass)
    now = dt_util.utcnow()

    if active:
        data["last_compressor_active_at"] = now.isoformat()

    raw = data.get("last_compressor_active_at")
    if raw is None:
        return None, None, False, 0.0

    last = dt_util.parse_datetime(str(raw))
    if last is None:
        return None, None, False, 0.0

    age_s = max(0.0, (now - dt_util.as_utc(last)).total_seconds())
    age_m = round(age_s / 60.0, 1)
    remaining = round(max(0.0, AFTER_RUN_MIN - age_m), 1)
    afterrun = (not active) and remaining > 0

    return dt_util.as_utc(last).isoformat(), age_m, afterrun, remaining


def _fmt_temp(v: float | None) -> str:
    return "—" if v is None else f"{v:.1f} °C"


def _fmt_trend(v: float | None) -> str:
    return "collecting" if v is None else f"{v:+.2f} °C/h"


def build_kegerator_fan_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    climate_state = _state(hass, CLIMATE)
    hvac_action = _attr(hass, CLIMATE, "hvac_action")

    current = _num_state(hass, AIR_TEMP)
    if current is None:
        current = _num_attr(hass, CLIMATE, "current_temperature")

    target = _num_attr(hass, CLIMATE, "temperature")
    delta = round(current - target, 2) if current is not None and target is not None else None

    trend = _num_attr(hass, AIR_STATS, "trend_c_per_hour")
    trend_label = _attr(hass, AIR_STATS, "trend_label") or "collecting"
    avg15 = _num_attr(hass, AIR_STATS, "average_15m")
    temp_summary = _attr(hass, AIR_STATS, "summary")

    power = _num_state(hass, POWER)
    compressor = _compressor_active(power)

    last_at, last_age, afterrun, afterrun_left = _remember_compressor(hass, compressor)

    fan_state = _state(hass, FAN)
    fan_power = _num_state(hass, FAN_POWER)
    fan_running = _fan_running(fan_state, fan_power)

    climate_on = _climate_enabled(climate_state)
    too_warm = delta is not None and delta >= TOO_WARM_C
    too_cold = delta is not None and delta <= TOO_COLD_C
    warming = trend is not None and trend >= WARMING_C_H
    cooling_requested = hvac_action == "cooling"

    should_run = False
    reason = "climate_off"

    if not climate_on:
        reason = "climate_off"
    elif too_cold and not compressor:
        reason = "too_cold"
    elif compressor:
        should_run = True
        reason = "compressor_active"
    elif afterrun:
        should_run = True
        reason = "afterrun"
    elif cooling_requested:
        should_run = True
        reason = "cooling_requested"
    elif too_warm:
        should_run = True
        reason = "too_warm"
    elif warming:
        should_run = True
        reason = "warming_fast"
    else:
        reason = "standby"

    action = "none"
    if _available(hass, FAN):
        if should_run and not fan_running:
            action = "turn_on_fan"
        elif not should_run and fan_running:
            action = "turn_off_fan"

    if not climate_on:
        status = "off"
    elif compressor:
        status = "cooling"
    elif afterrun:
        status = "afterrun"
    elif fan_running:
        status = "circulating"
    else:
        status = "standby"

    if not _available(hass, CLIMATE) or not _available(hass, AIR_TEMP) or not _available(hass, POWER):
        warning = "sensor_issue"
    elif delta is not None and abs(delta) >= 2.0:
        warning = "warning"
    elif trend is not None and trend >= 1.5:
        warning = "warning"
    else:
        warning = "ok"

    summary = (
        f"{status} · {_fmt_temp(current)} → {_fmt_temp(target)} · "
        f"Δ {'—' if delta is None else f'{delta:+.1f} °C'} · "
        f"{_fmt_trend(trend)} · "
        f"{'compressor active' if compressor else 'compressor idle'} · "
        f"{'fan on' if fan_running else 'fan off'} · {reason}"
    )

    return {
        "source": "python_kegerator_fan_backend",
        "status": status,
        "summary": summary,
        "warning_level": warning,
        "climate_entity": CLIMATE,
        "climate_state": climate_state,
        "climate_enabled": climate_on,
        "hvac_action": hvac_action,
        "air_temperature_entity": AIR_TEMP,
        "current_temperature": round(current, 2) if current is not None else None,
        "target_temperature": round(target, 2) if target is not None else None,
        "temperature_delta": delta,
        "too_warm": too_warm,
        "too_cold": too_cold,
        "average_15m": avg15,
        "trend_c_per_hour": trend,
        "trend_label": trend_label,
        "temperature_summary": temp_summary,
        "power_entity": POWER,
        "power_w": round(power, 2) if power is not None else None,
        "compressor_active": compressor,
        "compressor_threshold_w": COMPRESSOR_W,
        "last_compressor_active_at": last_at,
        "last_compressor_active_age_minutes": last_age,
        "afterrun_active": afterrun,
        "afterrun_remaining_minutes": afterrun_left,
        "afterrun_minutes": AFTER_RUN_MIN,
        "fan_switch_entity": FAN,
        "fan_state": fan_state,
        "fan_power_entity": FAN_POWER,
        "fan_power_w": round(fan_power, 2) if fan_power is not None else None,
        "fan_running": fan_running,
        "fan_should_run": should_run,
        "fan_recommendation": "run" if should_run else "stop",
        "fan_action_needed": action != "none",
        "fan_action": action,
        "fan_reason": reason,
        "fan_switch_ok": _available(hass, FAN),
        "temperature_sensor_ok": _available(hass, AIR_TEMP),
        "power_sensor_ok": _available(hass, POWER),
        "fan_power_sensor_ok": _available(hass, FAN_POWER),
        "fermentation_chamber_entity": CHAMBER,
        "fermentation_chamber_state": _state(hass, CHAMBER),
        "control_interval_seconds": INTERVAL_SECONDS,
    }


async def async_apply_kegerator_fan_auto(hass: HomeAssistant) -> dict[str, Any]:
    snapshot = build_kegerator_fan_snapshot(hass)
    action = snapshot.get("fan_action")

    if action == "turn_on_fan":
        await hass.services.async_call("switch", "turn_on", {"entity_id": FAN}, blocking=False)
    elif action == "turn_off_fan":
        await hass.services.async_call("switch", "turn_off", {"entity_id": FAN}, blocking=False)

    data = _bucket(hass)
    data["last_apply_action"] = action
    data["last_apply_reason"] = snapshot.get("fan_reason")
    data["last_apply_at"] = dt_util.utcnow().isoformat()

    refreshed = build_kegerator_fan_snapshot(hass)
    refreshed["last_apply_action"] = data["last_apply_action"]
    refreshed["last_apply_reason"] = data["last_apply_reason"]
    refreshed["last_apply_at"] = data["last_apply_at"]
    return refreshed


def async_disable_kegerator_fan_auto(hass: HomeAssistant) -> None:
    data = _bucket(hass)
    data["disabled_at"] = dt_util.utcnow().isoformat()
    data["last_apply_action"] = "disabled"
