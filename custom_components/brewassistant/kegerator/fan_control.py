"""Deterministic kegerator fan backend for BrewAssistant.

Default strategy: compressor + afterrun only.

The controller is intentionally state-machine based:

1. Read Home Assistant inputs.
2. Evaluate desired fan state.
3. Apply the desired switch state through the section policy router.
4. Expose rich diagnostics for dashboard/debugging.

Snapshots are read-only. Compressor transition and afterrun state are updated
only from ``async_apply_kegerator_fan_auto`` so dashboard rendering cannot change
runtime behavior.
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from ..const import DOMAIN
from ..control_policy import SOURCE_BACKEND, request_action, section_policy

CLIMATE = "climate.kegerator_kylskap"
AIR_TEMP = "sensor.kyl_temperatur_4"
AIR_STATS = "sensor.brewassistant_kegerator_air_temperature_average"
POWER_CANDIDATES = (
    "sensor.brewassistant_kegerator_power_w",
    "sensor.kegerator_power",
)
FAN = "switch.kegerator_fan"
FAN_POWER = "sensor.kegerator_fan_power"
FAN_MODE_SELECT = "select.brewassistant_kegerator_fan_mode"
AFTER_RUN_NUMBER = "number.brewassistant_kegerator_fan_afterrun_minutes"

MODE_OFF = "Off"
MODE_COOLING_ONLY = "Cooling only"
MODE_AFTERRUN = "Afterrun"
MODE_ALWAYS_ON = "Always on"
FAN_MODE_OPTIONS = [MODE_OFF, MODE_COOLING_ONLY, MODE_AFTERRUN, MODE_ALWAYS_ON]
DEFAULT_FAN_MODE = MODE_AFTERRUN

CHAMBER = "climate.fermentation_chamber"

DATA_KEY = "kegerator_fan_auto"
SECTION = "kegerator_fan"
STRATEGY = "compressor_afterrun_only"

COMPRESSOR_W = 20.0
FAN_W = 2.0
TOO_WARM_C = 0.8
TOO_COLD_C = -0.8
WARMING_C_H = 0.20
MAX_REASONABLE_WARMING_C_H = 5.0
AFTER_RUN_MIN = 10.0
INTERVAL_SECONDS = 30

BAD_STATES = {"unknown", "unavailable", "none", ""}

RUNTIME_LAST_COMPRESSOR_ACTIVE_AT = "last_compressor_active_at"
RUNTIME_PREVIOUS_COMPRESSOR_ACTIVE = "previous_compressor_active"
RUNTIME_AFTERRUN_UNTIL = "afterrun_until"
RUNTIME_LAST_TRANSITION = "last_transition"
RUNTIME_LAST_DECISION = "last_decision"
RUNTIME_LAST_APPLY = "last_apply"
RUNTIME_LAST_POLICY_RESULT = "last_policy_result"


@dataclass(slots=True)
class FanInputs:
    climate_state: str | None
    hvac_action: str | None
    current_temperature: float | None
    target_temperature: float | None
    temperature_delta: float | None
    trend_c_per_hour: float | None
    trend_label: str
    average_15m: float | None
    temperature_summary: str | None
    power_w: float | None
    power_entity: str | None
    compressor_active: bool
    fan_state: str | None
    fan_power_w: float | None
    fan_running: bool
    climate_enabled: bool
    fan_switch_ok: bool
    temperature_sensor_ok: bool
    power_sensor_ok: bool
    fan_power_sensor_ok: bool


@dataclass(slots=True)
class FanDemand:
    too_warm: bool
    too_cold: bool
    cooling_requested: bool
    warming_fast: bool
    diagnostic_reason: str


@dataclass(slots=True)
class FanDecision:
    state: str
    reason: str
    desired_switch_state: str
    should_run: bool
    action: str
    command: str | None
    action_needed: bool
    afterrun_active: bool
    afterrun_until: str | None
    afterrun_remaining_minutes: float
    warning_level: str
    transition: str | None
    demand: FanDemand


def kegerator_fan_auto_interval() -> timedelta:
    return timedelta(seconds=INTERVAL_SECONDS)


def _bucket(hass: HomeAssistant) -> dict[str, Any]:
    return hass.data.setdefault(DOMAIN, {}).setdefault(DATA_KEY, {})


def _state(hass: HomeAssistant, entity_id: str) -> str | None:
    state = hass.states.get(entity_id)
    if state is None or state.state in BAD_STATES:
        return None
    return state.state


def _state_by_suffix(hass: HomeAssistant, domain: str, suffix: str) -> tuple[str | None, str | None]:
    """Return state/entity for exact suffix, allowing HA area prefixes."""
    exact = f"{domain}.{suffix}"
    value = _state(hass, exact)
    if value is not None:
        return value, exact

    wanted_suffix = f"_{suffix}"
    for state in hass.states.async_all(domain):
        object_id = state.entity_id.split(".", 1)[1]
        if object_id == suffix or object_id.endswith(wanted_suffix):
            if state.state not in BAD_STATES:
                return state.state, state.entity_id

    return None, None


def _number_by_suffix(hass: HomeAssistant, suffix: str, default: float) -> tuple[float, str | None]:
    raw, entity_id = _state_by_suffix(hass, "number", suffix)
    if raw is None:
        return default, entity_id
    try:
        return float(str(raw).replace(",", ".")), entity_id
    except (TypeError, ValueError):
        return default, entity_id


def _available(hass: HomeAssistant, entity_id: str) -> bool:
    state = hass.states.get(entity_id)
    return state is not None and state.state not in BAD_STATES


def _any_available(hass: HomeAssistant, entities: tuple[str, ...]) -> bool:
    return any(_available(hass, entity_id) for entity_id in entities)


def _num_state(hass: HomeAssistant, entity_id: str) -> float | None:
    raw = _state(hass, entity_id)
    if raw is None:
        return None
    try:
        return float(str(raw).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _first_num_state(hass: HomeAssistant, entities: tuple[str, ...]) -> tuple[float | None, str | None]:
    for entity_id in entities:
        value = _num_state(hass, entity_id)
        if value is not None:
            return value, entity_id
    return None, None


def _attr(hass: HomeAssistant, entity_id: str, attr: str) -> Any:
    state = hass.states.get(entity_id)
    return None if state is None else state.attributes.get(attr)


def _num_attr(hass: HomeAssistant, entity_id: str, attr: str) -> float | None:
    value = _attr(hass, entity_id, attr)
    if value is None or str(value).lower() in BAD_STATES:
        return None
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _parse_utc(raw: Any) -> Any:
    if raw is None:
        return None
    parsed = dt_util.parse_datetime(str(raw))
    if parsed is None:
        return None
    return dt_util.as_utc(parsed)


def _format_temp(value: float | None) -> str:
    return "—" if value is None else f"{value:.1f} °C"


def _format_trend(value: float | None) -> str:
    return "collecting" if value is None else f"{value:+.2f} °C/h"


def _fan_mode(hass: HomeAssistant) -> str:
    mode, _entity_id = _state_by_suffix(hass, "select", "brewassistant_kegerator_fan_mode")
    return mode if mode in FAN_MODE_OPTIONS else DEFAULT_FAN_MODE


def _afterrun_minutes(hass: HomeAssistant) -> float:
    value, _entity_id = _number_by_suffix(
        hass,
        "brewassistant_kegerator_fan_afterrun_minutes",
        AFTER_RUN_MIN,
    )
    return max(0.0, min(float(value), 60.0))


def _fan_mode_entity(hass: HomeAssistant) -> str | None:
    _value, entity_id = _state_by_suffix(hass, "select", "brewassistant_kegerator_fan_mode")
    return entity_id or FAN_MODE_SELECT


def _afterrun_entity(hass: HomeAssistant) -> str | None:
    _value, entity_id = _number_by_suffix(
        hass,
        "brewassistant_kegerator_fan_afterrun_minutes",
        AFTER_RUN_MIN,
    )
    return entity_id or AFTER_RUN_NUMBER


def _climate_enabled(state: str | None) -> bool:
    return state not in {None, "off", "unknown", "unavailable", "none", ""}


def _read_inputs(hass: HomeAssistant) -> FanInputs:
    climate_state = _state(hass, CLIMATE)
    hvac_action = _attr(hass, CLIMATE, "hvac_action")

    current = _num_state(hass, AIR_TEMP)
    if current is None:
        current = _num_attr(hass, CLIMATE, "current_temperature")

    target = _num_attr(hass, CLIMATE, "temperature")
    delta = round(current - target, 2) if current is not None and target is not None else None

    trend = _num_attr(hass, AIR_STATS, "trend_c_per_hour")
    trend_label = str(_attr(hass, AIR_STATS, "trend_label") or "collecting")
    avg15 = _num_attr(hass, AIR_STATS, "average_15m")
    temp_summary = _attr(hass, AIR_STATS, "summary")

    power, power_entity = _first_num_state(hass, POWER_CANDIDATES)
    compressor = power is not None and power > COMPRESSOR_W

    fan_state = _state(hass, FAN)
    fan_power = _num_state(hass, FAN_POWER)
    fan_running = fan_state == "on" or (fan_power is not None and fan_power > FAN_W)

    return FanInputs(
        climate_state=climate_state,
        hvac_action=str(hvac_action) if hvac_action is not None else None,
        current_temperature=round(current, 2) if current is not None else None,
        target_temperature=round(target, 2) if target is not None else None,
        temperature_delta=delta,
        trend_c_per_hour=trend,
        trend_label=trend_label,
        average_15m=avg15,
        temperature_summary=str(temp_summary) if temp_summary is not None else None,
        power_w=round(power, 2) if power is not None else None,
        power_entity=power_entity,
        compressor_active=compressor,
        fan_state=fan_state,
        fan_power_w=round(fan_power, 2) if fan_power is not None else None,
        fan_running=fan_running,
        climate_enabled=_climate_enabled(climate_state),
        fan_switch_ok=_available(hass, FAN),
        temperature_sensor_ok=_available(hass, AIR_TEMP) or _num_attr(hass, CLIMATE, "current_temperature") is not None,
        power_sensor_ok=power_entity is not None,
        fan_power_sensor_ok=_available(hass, FAN_POWER),
    )


def _demand(inputs: FanInputs) -> FanDemand:
    too_warm = inputs.temperature_delta is not None and inputs.temperature_delta >= TOO_WARM_C
    too_cold = inputs.temperature_delta is not None and inputs.temperature_delta <= TOO_COLD_C
    cooling_requested = inputs.hvac_action == "cooling"
    warming_fast = inputs.trend_c_per_hour is not None and WARMING_C_H <= inputs.trend_c_per_hour <= MAX_REASONABLE_WARMING_C_H

    if too_cold:
        diagnostic_reason = "too_cold"
    elif cooling_requested:
        diagnostic_reason = "cooling_requested"
    elif too_warm:
        diagnostic_reason = "too_warm"
    elif warming_fast:
        diagnostic_reason = "warming_fast"
    else:
        diagnostic_reason = "stable"

    return FanDemand(
        too_warm=too_warm,
        too_cold=too_cold,
        cooling_requested=cooling_requested,
        warming_fast=warming_fast,
        diagnostic_reason=diagnostic_reason,
    )


def _sync_compressor_runtime(hass: HomeAssistant, inputs: FanInputs, afterrun_minutes: float) -> str | None:
    data = _bucket(hass)
    now = dt_util.utcnow()
    previous = data.get(RUNTIME_PREVIOUS_COMPRESSOR_ACTIVE)
    transition = None

    if inputs.compressor_active:
        data[RUNTIME_LAST_COMPRESSOR_ACTIVE_AT] = now.isoformat()
        if previous is False:
            transition = "compressor_idle_to_active"
            data[RUNTIME_LAST_TRANSITION] = {"type": transition, "at": now.isoformat()}
        data[RUNTIME_PREVIOUS_COMPRESSOR_ACTIVE] = True
        return transition

    if previous is True:
        afterrun_until = now + timedelta(minutes=afterrun_minutes)
        transition = "compressor_active_to_idle"
        data[RUNTIME_AFTERRUN_UNTIL] = afterrun_until.isoformat()
        data[RUNTIME_LAST_TRANSITION] = {
            "type": transition,
            "at": now.isoformat(),
            "afterrun_until": afterrun_until.isoformat(),
        }

    data[RUNTIME_PREVIOUS_COMPRESSOR_ACTIVE] = False
    return transition


def _afterrun_state(hass: HomeAssistant, inputs: FanInputs) -> tuple[bool, str | None, float]:
    if inputs.compressor_active:
        return False, _bucket(hass).get(RUNTIME_AFTERRUN_UNTIL), 0.0

    raw_until = _bucket(hass).get(RUNTIME_AFTERRUN_UNTIL)
    until = _parse_utc(raw_until)
    if until is None:
        return False, None, 0.0

    now = dt_util.utcnow()
    remaining_s = max(0.0, (until - now).total_seconds())
    remaining_m = round(remaining_s / 60.0, 1)
    return remaining_s > 0, until.isoformat(), remaining_m


def _warning_level(inputs: FanInputs) -> str:
    if not inputs.fan_switch_ok or not inputs.temperature_sensor_ok or not inputs.power_sensor_ok:
        return "sensor_issue"
    if inputs.temperature_delta is not None and abs(inputs.temperature_delta) >= 2.0:
        return "warning"
    if inputs.trend_c_per_hour is not None and 1.5 <= inputs.trend_c_per_hour <= MAX_REASONABLE_WARMING_C_H:
        return "warning"
    return "ok"


def _evaluate(hass: HomeAssistant, *, mutate: bool) -> tuple[FanInputs, FanDecision]:
    inputs = _read_inputs(hass)
    fan_mode = _fan_mode(hass)
    afterrun_minutes = _afterrun_minutes(hass)
    transition = _sync_compressor_runtime(hass, inputs, afterrun_minutes) if mutate else None
    afterrun_active, afterrun_until, afterrun_remaining = _afterrun_state(hass, inputs)
    demand = _demand(inputs)

    if not inputs.fan_switch_ok:
        desired_state = "blocked"
        reason = "missing_fan_switch"
    elif fan_mode == MODE_OFF:
        desired_state = "off"
        reason = "mode_off"
    elif fan_mode == MODE_ALWAYS_ON:
        desired_state = "always_on"
        reason = "mode_always_on"
    elif fan_mode == MODE_COOLING_ONLY:
        desired_state = "compressor_follow" if inputs.compressor_active else "standby"
        reason = "compressor_active" if inputs.compressor_active else "compressor_idle"
    elif inputs.compressor_active:
        desired_state = "compressor_follow"
        reason = "compressor_active"
    elif afterrun_active:
        desired_state = "afterrun"
        reason = "afterrun"
    else:
        desired_state = "standby"
        reason = "compressor_idle_afterrun_expired"

    should_run = desired_state in {"compressor_follow", "afterrun", "always_on"}
    desired_switch_state = "on" if should_run else "off"

    action = "none"
    command = None
    if inputs.fan_switch_ok:
        if should_run and not inputs.fan_running:
            action = "turn_on_fan"
            command = "kegerator_fan_on"
        elif not should_run and inputs.fan_running:
            action = "turn_off_fan"
            command = "kegerator_fan_off"

    decision = FanDecision(
        state=desired_state,
        reason=reason,
        desired_switch_state=desired_switch_state,
        should_run=should_run,
        action=action,
        command=command,
        action_needed=action != "none",
        afterrun_active=afterrun_active,
        afterrun_until=afterrun_until,
        afterrun_remaining_minutes=afterrun_remaining,
        warning_level=_warning_level(inputs),
        transition=transition,
        demand=demand,
    )

    if mutate:
        data = _bucket(hass)
        data[RUNTIME_LAST_DECISION] = {
            "at": dt_util.utcnow().isoformat(),
            "strategy": STRATEGY,
            "inputs": asdict(inputs),
            "decision": asdict(decision),
        }

    return inputs, decision


def _status_from_decision(inputs: FanInputs, decision: FanDecision) -> str:
    if decision.state == "compressor_follow":
        return "cooling"
    if decision.state == "blocked":
        return "blocked"
    return decision.state


def _snapshot_from(inputs: FanInputs, decision: FanDecision, hass: HomeAssistant) -> dict[str, Any]:
    data = _bucket(hass)
    status = _status_from_decision(inputs, decision)
    summary = (
        f"{status} · {_format_temp(inputs.current_temperature)} → {_format_temp(inputs.target_temperature)} · "
        f"Δ {'—' if inputs.temperature_delta is None else f'{inputs.temperature_delta:+.1f} °C'} · "
        f"{_format_trend(inputs.trend_c_per_hour)} · "
        f"{'compressor active' if inputs.compressor_active else 'compressor idle'} · "
        f"{'fan on' if inputs.fan_running else 'fan off'} · {decision.reason}"
    )

    policy_result = data.get(RUNTIME_LAST_POLICY_RESULT)
    last_decision = data.get(RUNTIME_LAST_DECISION)
    last_apply = data.get(RUNTIME_LAST_APPLY)
    last_transition = data.get(RUNTIME_LAST_TRANSITION)
    demand = decision.demand

    return {
        "source": "python_kegerator_fan_backend_v2_state_machine",
        "strategy": STRATEGY,
        "fan_mode": _fan_mode(hass),
        "fan_mode_entity": _fan_mode_entity(hass),
        "fan_mode_entity_configured": FAN_MODE_SELECT,
        "fan_mode_options": FAN_MODE_OPTIONS,
        "status": status,
        "desired_fan_state": decision.state,
        "desired_switch_state": decision.desired_switch_state,
        "actual_switch_state": inputs.fan_state,
        "summary": summary,
        "warning_level": decision.warning_level,
        "policy_section": SECTION,
        "policy": section_policy(hass, SECTION),
        "last_policy_result": policy_result,
        "last_policy_status": policy_result.get("status") if isinstance(policy_result, dict) else None,
        "last_policy_summary": policy_result.get("summary") if isinstance(policy_result, dict) else None,
        "last_decision": last_decision,
        "last_decision_at": last_decision.get("at") if isinstance(last_decision, dict) else None,
        "last_apply": last_apply,
        "last_apply_action": last_apply.get("action") if isinstance(last_apply, dict) else data.get("last_apply_action"),
        "last_apply_reason": last_apply.get("reason") if isinstance(last_apply, dict) else data.get("last_apply_reason"),
        "last_apply_at": last_apply.get("at") if isinstance(last_apply, dict) else data.get("last_apply_at"),
        "last_apply_result": last_apply.get("result") if isinstance(last_apply, dict) else None,
        "last_transition": last_transition,
        "temperature_demand_reason": demand.diagnostic_reason,
        "temperature_demand_too_warm": demand.too_warm,
        "temperature_demand_too_cold": demand.too_cold,
        "temperature_demand_cooling_requested": demand.cooling_requested,
        "temperature_demand_warming_fast": demand.warming_fast,
        "climate_entity": CLIMATE,
        "climate_state": inputs.climate_state,
        "climate_enabled": inputs.climate_enabled,
        "hvac_action": inputs.hvac_action,
        "air_temperature_entity": AIR_TEMP,
        "current_temperature": inputs.current_temperature,
        "target_temperature": inputs.target_temperature,
        "temperature_delta": inputs.temperature_delta,
        "too_warm": demand.too_warm,
        "too_cold": demand.too_cold,
        "average_15m": inputs.average_15m,
        "trend_c_per_hour": inputs.trend_c_per_hour,
        "trend_label": inputs.trend_label,
        "temperature_summary": inputs.temperature_summary,
        "power_entity": inputs.power_entity,
        "power_entity_candidates": POWER_CANDIDATES,
        "power_w": inputs.power_w,
        "compressor_active": inputs.compressor_active,
        "compressor_threshold_w": COMPRESSOR_W,
        "last_compressor_active_at": data.get(RUNTIME_LAST_COMPRESSOR_ACTIVE_AT),
        "previous_compressor_active": data.get(RUNTIME_PREVIOUS_COMPRESSOR_ACTIVE),
        "afterrun_active": decision.afterrun_active,
        "afterrun_until": decision.afterrun_until,
        "afterrun_remaining_minutes": decision.afterrun_remaining_minutes,
        "afterrun_minutes": _afterrun_minutes(hass),
        "afterrun_entity": _afterrun_entity(hass),
        "afterrun_entity_configured": AFTER_RUN_NUMBER,
        "fan_switch_entity": FAN,
        "fan_state": inputs.fan_state,
        "fan_power_entity": FAN_POWER,
        "fan_power_w": inputs.fan_power_w,
        "fan_running": inputs.fan_running,
        "fan_should_run": decision.should_run,
        "fan_recommendation": "run" if decision.should_run else "stop",
        "fan_action_needed": decision.action_needed,
        "apply_required": decision.action_needed,
        "fan_action": decision.action,
        "fan_command": decision.command,
        "fan_reason": decision.reason,
        "fan_switch_ok": inputs.fan_switch_ok,
        "temperature_sensor_ok": inputs.temperature_sensor_ok,
        "power_sensor_ok": inputs.power_sensor_ok,
        "power_sensor_candidates_ok": _any_available(hass, POWER_CANDIDATES),
        "fan_power_sensor_ok": inputs.fan_power_sensor_ok,
        "fermentation_chamber_entity": CHAMBER,
        "fermentation_chamber_state": _state(hass, CHAMBER),
        "control_interval_seconds": INTERVAL_SECONDS,
        "max_reasonable_warming_c_per_hour": MAX_REASONABLE_WARMING_C_H,
    }


def build_kegerator_fan_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    """Return a read-only snapshot of the current fan decision."""
    inputs, decision = _evaluate(hass, mutate=False)
    return _snapshot_from(inputs, decision, hass)


async def async_apply_kegerator_fan_auto(hass: HomeAssistant) -> dict[str, Any]:
    """Evaluate and apply fan-auto once through the policy router."""
    inputs, decision = _evaluate(hass, mutate=True)
    before_state = inputs.fan_state
    before_power = inputs.fan_power_w

    policy_result: dict[str, Any] | None = None
    if isinstance(decision.command, str):
        policy_result = await request_action(
            hass,
            section=SECTION,
            command=decision.command,
            source=SOURCE_BACKEND,
            reason=f"Kegerator fan auto: {decision.reason}",
            context={
                "strategy": STRATEGY,
                "desired_fan_state": decision.state,
                "desired_switch_state": decision.desired_switch_state,
                "actual_switch_state": inputs.fan_state,
                "fan_action": decision.action,
                "fan_reason": decision.reason,
                "temperature_demand_reason": decision.demand.diagnostic_reason,
                "fan_should_run": decision.should_run,
                "fan_running": inputs.fan_running,
                "fan_power_w": inputs.fan_power_w,
                "compressor_active": inputs.compressor_active,
                "afterrun_active": decision.afterrun_active,
                "afterrun_until": decision.afterrun_until,
                "afterrun_remaining_minutes": decision.afterrun_remaining_minutes,
                "power_entity": inputs.power_entity,
                "power_w": inputs.power_w,
                "temperature_delta": inputs.temperature_delta,
                "transition": decision.transition,
            },
        )
        await asyncio.sleep(1)

    after_inputs = _read_inputs(hass)
    apply_result = {
        "at": dt_util.utcnow().isoformat(),
        "strategy": STRATEGY,
        "action": decision.action,
        "command": decision.command,
        "reason": decision.reason,
        "temperature_demand_reason": decision.demand.diagnostic_reason,
        "desired_fan_state": decision.state,
        "desired_switch_state": decision.desired_switch_state,
        "before_state": before_state,
        "before_power_w": before_power,
        "after_state": after_inputs.fan_state,
        "after_power_w": after_inputs.fan_power_w,
        "policy_status": policy_result.get("status") if isinstance(policy_result, dict) else None,
        "policy_summary": policy_result.get("summary") if isinstance(policy_result, dict) else None,
        "result": "no_action" if decision.action == "none" else (
            "applied" if after_inputs.fan_state == decision.desired_switch_state else "attempted_no_state_change"
        ),
    }

    data = _bucket(hass)
    data[RUNTIME_LAST_APPLY] = apply_result
    data[RUNTIME_LAST_POLICY_RESULT] = policy_result
    data["last_apply_action"] = decision.action
    data["last_apply_reason"] = decision.reason
    data["last_apply_at"] = apply_result["at"]

    refreshed_inputs, refreshed_decision = _evaluate(hass, mutate=False)
    return _snapshot_from(refreshed_inputs, refreshed_decision, hass)


def async_disable_kegerator_fan_auto(hass: HomeAssistant) -> None:
    data = _bucket(hass)
    data["disabled_at"] = dt_util.utcnow().isoformat()
    data["last_apply_action"] = "disabled"
    data[RUNTIME_LAST_APPLY] = {
        "at": data["disabled_at"],
        "action": "disabled",
        "result": "disabled",
    }
