"""Home Assistant adapter/runtime for BrewAssistant kegerator fan control."""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from ..configured_entities import configured_entity
from ..const import (
    CONF_KEGERATOR_AIR_TEMP_ENTITY,
    CONF_KEGERATOR_FAN_POWER_ENTITY,
    CONF_KEGERATOR_POWER_ENTITY,
    DEFAULT_KEGERATOR_AIR_TEMP_ENTITY,
    DEFAULT_KEGERATOR_FAN_POWER_ENTITY,
    DEFAULT_KEGERATOR_POWER_ENTITY,
    DOMAIN,
)
from ..control_policy import SOURCE_BACKEND, request_action, section_policy
from .fan_model import (
    AFTERRUN_MODES,
    DEFAULT_FAN_MODE,
    FAN_MODE_OPTIONS,
    MAX_REASONABLE_WARMING_C_H,
    MODE_SMART_AUTO,
    SMART_STOP_DELTA_C,
    SMART_STOP_TREND_C_H,
    TOO_WARM_C,
    WARMING_C_H,
    FanDecision,
    FanInputs as ModelInputs,
    decide,
)

CLIMATE = "climate.kegerator_kylskap"
CHAMBER = "climate.fermentation_chamber"
AIR_STATS = "sensor.brewassistant_kegerator_air_temperature_average"
FAN = "switch.kegerator_fan"
FAN_AUTO_SWITCH = "switch.brewassistant_kegerator_fan_auto_enabled"
FAN_MODE_SELECT = "select.brewassistant_kegerator_fan_mode"
AFTER_RUN_NUMBER = "number.brewassistant_kegerator_fan_afterrun_minutes"
KEGERATOR_SUPERVISOR_SWITCH = "switch.brewassistant_climate_supervisor_enabled"
FERMENTATION_SUPERVISOR_SWITCH = "switch.brewassistant_fermentation_climate_supervisor_enabled"
FERMENTATION_AIR_TARGET = "sensor.brewassistant_fermentation_effective_air_target"

DATA_KEY = "kegerator_fan_auto"
SECTION = "kegerator_fan"
STRATEGY = "smart_temperature_afterrun"
SCHEDULER_OWNER = "fan_auto_switch_timer"

COMPRESSOR_W = 20.0
FAN_W = 2.0
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
RUNTIME_LAST_MODE = "last_mode"
RUNTIME_AFTERRUN_CLEARED_REASON = "afterrun_cleared_reason"
RUNTIME_APPLY_LOCK = "apply_lock"


@dataclass(slots=True)
class FanInputs:
    model: ModelInputs
    kegerator_climate_state: str | None
    fermentation_climate_state: str | None
    active_climate_entity: str | None
    climate_state: str | None
    hvac_action: str | None
    climate_enabled: bool
    climate_conflict: bool
    current_temperature: float | None
    target_temperature: float | None
    temperature_delta: float | None
    temperature_context_available: bool
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
    fan_switch_ok: bool
    temperature_sensor_ok: bool
    power_sensor_ok: bool
    fan_power_sensor_ok: bool


def kegerator_fan_auto_interval() -> timedelta:
    """Return the single fan-controller tick interval."""
    return timedelta(seconds=INTERVAL_SECONDS)


def _bucket(hass: HomeAssistant) -> dict[str, Any]:
    return hass.data.setdefault(DOMAIN, {}).setdefault(DATA_KEY, {})


def _apply_lock(hass: HomeAssistant) -> asyncio.Lock:
    data = _bucket(hass)
    lock = data.get(RUNTIME_APPLY_LOCK)
    if not isinstance(lock, asyncio.Lock):
        lock = asyncio.Lock()
        data[RUNTIME_APPLY_LOCK] = lock
    return lock


def _state(hass: HomeAssistant, entity_id: str) -> str | None:
    state = hass.states.get(entity_id)
    if state is None or state.state in BAD_STATES:
        return None
    return state.state


def _state_by_suffix(hass: HomeAssistant, domain: str, suffix: str) -> tuple[str | None, str | None]:
    exact = f"{domain}.{suffix}"
    value = _state(hass, exact)
    if value is not None:
        return value, exact

    wanted_suffix = f"_{suffix}"
    for state in hass.states.async_all(domain):
        object_id = state.entity_id.split(".", 1)[1]
        if (object_id == suffix or object_id.endswith(wanted_suffix)) and state.state not in BAD_STATES:
            return state.state, state.entity_id
    return None, None


def _number_by_suffix(hass: HomeAssistant, suffix: str, default: float) -> tuple[float, str | None]:
    raw, entity_id = _state_by_suffix(hass, "number", suffix)
    try:
        return (float(str(raw).replace(",", ".")) if raw is not None else default), entity_id
    except (TypeError, ValueError):
        return default, entity_id


def _available(hass: HomeAssistant, entity_id: str) -> bool:
    state = hass.states.get(entity_id)
    return state is not None and state.state not in BAD_STATES


def _num_state(hass: HomeAssistant, entity_id: str) -> float | None:
    raw = _state(hass, entity_id)
    try:
        return None if raw is None else float(str(raw).replace(",", "."))
    except (TypeError, ValueError):
        return None


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
    parsed = dt_util.parse_datetime(str(raw)) if raw is not None else None
    return dt_util.as_utc(parsed) if parsed is not None else None


def _fan_auto_state(hass: HomeAssistant) -> tuple[bool, str]:
    raw, entity_id = _state_by_suffix(hass, "switch", "brewassistant_kegerator_fan_auto_enabled")
    return raw == "on", entity_id or FAN_AUTO_SWITCH


def _fan_mode(hass: HomeAssistant) -> str:
    mode, _entity_id = _state_by_suffix(hass, "select", "brewassistant_kegerator_fan_mode")
    return mode if mode in FAN_MODE_OPTIONS else DEFAULT_FAN_MODE


def _afterrun_minutes(hass: HomeAssistant) -> float:
    value, _entity_id = _number_by_suffix(hass, "brewassistant_kegerator_fan_afterrun_minutes", AFTER_RUN_MIN)
    return max(0.0, min(float(value), 60.0))


def _fan_mode_entity(hass: HomeAssistant) -> str:
    _value, entity_id = _state_by_suffix(hass, "select", "brewassistant_kegerator_fan_mode")
    return entity_id or FAN_MODE_SELECT


def _afterrun_entity(hass: HomeAssistant) -> str:
    _value, entity_id = _number_by_suffix(hass, "brewassistant_kegerator_fan_afterrun_minutes", AFTER_RUN_MIN)
    return entity_id or AFTER_RUN_NUMBER


def _climate_enabled(state: str | None) -> bool:
    return state not in {None, "off", "unknown", "unavailable", "none", ""}


def _climate_target(hass: HomeAssistant, entity_id: str, hvac_action: str | None) -> float | None:
    target = _num_attr(hass, entity_id, "temperature")
    if target is not None:
        return target
    low = _num_attr(hass, entity_id, "target_temp_low")
    high = _num_attr(hass, entity_id, "target_temp_high")
    if hvac_action == "cooling" and high is not None:
        return high
    if hvac_action == "heating" and low is not None:
        return low
    if low is not None and high is not None:
        return round((low + high) / 2.0, 2)
    return high if high is not None else low


def _bool_attr(hass: HomeAssistant, entity_id: str, attr: str) -> bool:
    value = _attr(hass, entity_id, attr)
    return value is True or str(value).lower() == "true"


def _climate_context(hass: HomeAssistant) -> tuple[str | None, str | None, str | None, bool, bool, str | None, str | None]:
    """Resolve the climate context that currently owns the shared fridge.

    The kegerator climate may stay enabled while the fridge is used as a
    fermentation chamber. Fermentation scope/supervisor state therefore wins
    over raw climate on/off state. A conflict is only reported when both
    BrewAssistant supervisors explicitly claim the fridge at the same time.
    """
    k_state = _state(hass, CLIMATE)
    f_state = _state(hass, CHAMBER)
    k_enabled = _climate_enabled(k_state)
    f_enabled = _climate_enabled(f_state)

    fermentation_scope = _bool_attr(hass, FERMENTATION_AIR_TARGET, "scope_active")
    fermentation_supervisor = hass.states.is_state(FERMENTATION_SUPERVISOR_SWITCH, "on")
    kegerator_supervisor = hass.states.is_state(KEGERATOR_SUPERVISOR_SWITCH, "on")
    fermentation_owner = fermentation_scope or fermentation_supervisor
    conflict = fermentation_owner and kegerator_supervisor

    if fermentation_owner and f_enabled:
        entity = CHAMBER
        state = f_state
    elif k_enabled:
        entity = CLIMATE
        state = k_state
    elif f_enabled:
        entity = CHAMBER
        state = f_state
    else:
        return None, None, None, False, conflict, k_state, f_state

    action_raw = _attr(hass, entity, "hvac_action")
    action = str(action_raw) if action_raw is not None else None
    return entity, state, action, True, conflict, k_state, f_state


def _read_inputs(hass: HomeAssistant) -> FanInputs:
    air_entity = configured_entity(hass, CONF_KEGERATOR_AIR_TEMP_ENTITY, DEFAULT_KEGERATOR_AIR_TEMP_ENTITY)
    power_entity = configured_entity(hass, CONF_KEGERATOR_POWER_ENTITY, DEFAULT_KEGERATOR_POWER_ENTITY)
    fan_power_entity = configured_entity(hass, CONF_KEGERATOR_FAN_POWER_ENTITY, DEFAULT_KEGERATOR_FAN_POWER_ENTITY)

    active_climate, climate_state, hvac_action, climate_enabled, climate_conflict, k_state, f_state = _climate_context(hass)

    current = _num_state(hass, air_entity)
    if current is None and active_climate is not None:
        current = _num_attr(hass, active_climate, "current_temperature")
    if current is None:
        current = _num_attr(hass, CLIMATE, "current_temperature")
    if current is None:
        current = _num_attr(hass, CHAMBER, "current_temperature")

    target = _climate_target(hass, active_climate, hvac_action) if active_climate is not None else None
    delta = round(current - target, 2) if current is not None and target is not None else None
    trend = _num_attr(hass, AIR_STATS, "trend_c_per_hour")
    avg15 = _num_attr(hass, AIR_STATS, "average_15m")
    power = _num_state(hass, power_entity)
    fan_state = _state(hass, FAN)
    fan_power = _num_state(hass, fan_power_entity)
    compressor = power is not None and power > COMPRESSOR_W
    fan_running = fan_state == "on" or (fan_power is not None and fan_power > FAN_W)
    temp_ok = _available(hass, air_entity) or (
        active_climate is not None and _num_attr(hass, active_climate, "current_temperature") is not None
    )
    temp_context_ok = current is not None and target is not None and not climate_conflict

    model = ModelInputs(
        compressor_active=compressor,
        fan_running=fan_running,
        fan_switch_ok=_available(hass, FAN),
        power_sensor_ok=power is not None,
        temperature_sensor_ok=temp_ok,
        temperature_context_available=temp_context_ok,
        climate_conflict=climate_conflict,
        hvac_action=hvac_action,
        temperature_delta=delta,
        trend_c_per_hour=trend,
    )
    return FanInputs(
        model=model,
        kegerator_climate_state=k_state,
        fermentation_climate_state=f_state,
        active_climate_entity=active_climate,
        climate_state=climate_state,
        hvac_action=hvac_action,
        climate_enabled=climate_enabled,
        climate_conflict=climate_conflict,
        current_temperature=round(current, 2) if current is not None else None,
        target_temperature=round(target, 2) if target is not None else None,
        temperature_delta=delta,
        temperature_context_available=temp_context_ok,
        trend_c_per_hour=trend,
        trend_label=str(_attr(hass, AIR_STATS, "trend_label") or "collecting"),
        average_15m=avg15,
        temperature_summary=str(_attr(hass, AIR_STATS, "summary") or "") or None,
        power_w=round(power, 2) if power is not None else None,
        power_entity=power_entity if power is not None else None,
        compressor_active=compressor,
        fan_state=fan_state,
        fan_power_w=round(fan_power, 2) if fan_power is not None else None,
        fan_running=fan_running,
        fan_switch_ok=model.fan_switch_ok,
        temperature_sensor_ok=temp_ok,
        power_sensor_ok=model.power_sensor_ok,
        fan_power_sensor_ok=_available(hass, fan_power_entity),
    )


def _clear_afterrun(hass: HomeAssistant, reason: str, *, clear_previous: bool = False) -> None:
    data = _bucket(hass)
    data.pop(RUNTIME_AFTERRUN_UNTIL, None)
    data[RUNTIME_AFTERRUN_CLEARED_REASON] = reason
    if clear_previous:
        data.pop(RUNTIME_PREVIOUS_COMPRESSOR_ACTIVE, None)


def _sync_mode_runtime(hass: HomeAssistant, enabled: bool, mode: str) -> None:
    data = _bucket(hass)
    previous_mode = data.get(RUNTIME_LAST_MODE)
    if not enabled:
        _clear_afterrun(hass, "fan_auto_disabled", clear_previous=True)
    elif previous_mode != mode and (mode not in AFTERRUN_MODES or previous_mode not in AFTERRUN_MODES):
        _clear_afterrun(hass, f"mode_change:{previous_mode}->{mode}")
    data[RUNTIME_LAST_MODE] = mode


def _sync_compressor_runtime(
    hass: HomeAssistant,
    inputs: FanInputs,
    afterrun_minutes: float,
    *,
    allow_afterrun: bool,
) -> str | None:
    data = _bucket(hass)
    now = dt_util.utcnow()
    previous = data.get(RUNTIME_PREVIOUS_COMPRESSOR_ACTIVE)

    if inputs.compressor_active:
        data[RUNTIME_LAST_COMPRESSOR_ACTIVE_AT] = now.isoformat()
        data.pop(RUNTIME_AFTERRUN_UNTIL, None)
        if previous is False:
            data[RUNTIME_LAST_TRANSITION] = {"type": "compressor_idle_to_active", "at": now.isoformat()}
        data[RUNTIME_PREVIOUS_COMPRESSOR_ACTIVE] = True
        return "compressor_idle_to_active" if previous is False else None

    if previous is True:
        transition = {"type": "compressor_active_to_idle", "at": now.isoformat()}
        if allow_afterrun and afterrun_minutes > 0:
            until = now + timedelta(minutes=afterrun_minutes)
            data[RUNTIME_AFTERRUN_UNTIL] = until.isoformat()
            transition["afterrun_until"] = until.isoformat()
        else:
            _clear_afterrun(hass, "compressor_stop_without_afterrun")
        data[RUNTIME_LAST_TRANSITION] = transition
        data[RUNTIME_PREVIOUS_COMPRESSOR_ACTIVE] = False
        return "compressor_active_to_idle"

    data[RUNTIME_PREVIOUS_COMPRESSOR_ACTIVE] = False
    return None


def _afterrun_state(hass: HomeAssistant, inputs: FanInputs, *, enabled: bool, mode: str) -> tuple[bool, str | None, float]:
    if not enabled or mode not in AFTERRUN_MODES or inputs.compressor_active:
        return False, None, 0.0
    until = _parse_utc(_bucket(hass).get(RUNTIME_AFTERRUN_UNTIL))
    if until is None:
        return False, None, 0.0
    remaining = max(0.0, (until - dt_util.utcnow()).total_seconds())
    return remaining > 0, until.isoformat(), round(remaining / 60.0, 1)


def _evaluate(hass: HomeAssistant, *, mutate: bool) -> tuple[FanInputs, FanDecision, bool, str | None, float]:
    inputs = _read_inputs(hass)
    enabled, _auto_entity = _fan_auto_state(hass)
    mode = _fan_mode(hass)
    afterrun_minutes = _afterrun_minutes(hass)
    transition = None

    if mutate:
        _sync_mode_runtime(hass, enabled, mode)
        if enabled:
            transition = _sync_compressor_runtime(
                hass,
                inputs,
                afterrun_minutes,
                allow_afterrun=mode in AFTERRUN_MODES,
            )

    afterrun_active, afterrun_until, afterrun_remaining = _afterrun_state(
        hass, inputs, enabled=enabled, mode=mode
    )
    decision = decide(enabled=enabled, mode=mode, inputs=inputs.model, afterrun_active=afterrun_active)

    if mutate:
        _bucket(hass)[RUNTIME_LAST_DECISION] = {
            "at": dt_util.utcnow().isoformat(),
            "strategy": STRATEGY,
            "mode": mode,
            "transition": transition,
            "inputs": asdict(inputs.model),
            "decision": asdict(decision),
            "afterrun_active": afterrun_active,
            "afterrun_until": afterrun_until,
            "afterrun_remaining_minutes": afterrun_remaining,
        }
    return inputs, decision, afterrun_active, afterrun_until, afterrun_remaining


def _status(decision: FanDecision) -> str:
    return "cooling" if decision.state == "compressor_follow" else decision.state


def _snapshot_from(
    hass: HomeAssistant,
    inputs: FanInputs,
    decision: FanDecision,
    afterrun_active: bool,
    afterrun_until: str | None,
    afterrun_remaining: float,
) -> dict[str, Any]:
    air_entity = configured_entity(hass, CONF_KEGERATOR_AIR_TEMP_ENTITY, DEFAULT_KEGERATOR_AIR_TEMP_ENTITY)
    power_entity = configured_entity(hass, CONF_KEGERATOR_POWER_ENTITY, DEFAULT_KEGERATOR_POWER_ENTITY)
    fan_power_entity = configured_entity(hass, CONF_KEGERATOR_FAN_POWER_ENTITY, DEFAULT_KEGERATOR_FAN_POWER_ENTITY)
    enabled, auto_entity = _fan_auto_state(hass)
    data = _bucket(hass)
    demand = decision.demand
    status = _status(decision)
    delta_text = "—" if inputs.temperature_delta is None else f"{inputs.temperature_delta:+.1f} °C"
    temp_text = "—" if inputs.current_temperature is None else f"{inputs.current_temperature:.1f} °C"
    target_text = "—" if inputs.target_temperature is None else f"{inputs.target_temperature:.1f} °C"
    trend_text = "collecting" if inputs.trend_c_per_hour is None else f"{inputs.trend_c_per_hour:+.2f} °C/h"
    last_apply = data.get(RUNTIME_LAST_APPLY)
    policy_result = data.get(RUNTIME_LAST_POLICY_RESULT)
    last_decision = data.get(RUNTIME_LAST_DECISION)

    return {
        "source": "python_kegerator_fan_backend_v3_smart_auto",
        "strategy": STRATEGY,
        "scheduler_owner": SCHEDULER_OWNER,
        "controller_enabled": enabled,
        "control_owner": SCHEDULER_OWNER if enabled else "none",
        "fan_auto_entity": auto_entity,
        "fan_mode": _fan_mode(hass),
        "fan_mode_entity": _fan_mode_entity(hass),
        "fan_mode_entity_configured": FAN_MODE_SELECT,
        "fan_mode_options": FAN_MODE_OPTIONS,
        "default_fan_mode": DEFAULT_FAN_MODE,
        "status": status,
        "desired_fan_state": decision.state,
        "desired_switch_state": decision.desired_switch_state,
        "actual_switch_state": inputs.fan_state,
        "summary": (
            f"{status} · {temp_text} → {target_text} · Δ {delta_text} · {trend_text} · "
            f"{'compressor active' if inputs.compressor_active else 'compressor idle'} · "
            f"{'fan on' if inputs.fan_running else 'fan off'} · {decision.reason}"
        ),
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
        "last_transition": data.get(RUNTIME_LAST_TRANSITION),
        "last_mode": data.get(RUNTIME_LAST_MODE),
        "afterrun_cleared_reason": data.get(RUNTIME_AFTERRUN_CLEARED_REASON),
        "temperature_demand_reason": demand.diagnostic_reason,
        "temperature_demand_too_warm": demand.too_warm,
        "temperature_demand_too_cold": demand.too_cold,
        "temperature_demand_cooling_requested": demand.cooling_requested,
        "temperature_demand_warming_fast": demand.warming_fast,
        "temperature_demand_hysteresis_run": demand.hysteresis_run,
        "climate_entity": inputs.active_climate_entity,
        "active_climate_entity": inputs.active_climate_entity,
        "climate_state": inputs.climate_state,
        "climate_enabled": inputs.climate_enabled,
        "climate_conflict": inputs.climate_conflict,
        "kegerator_climate_entity": CLIMATE,
        "kegerator_climate_state": inputs.kegerator_climate_state,
        "fermentation_chamber_entity": CHAMBER,
        "fermentation_chamber_state": inputs.fermentation_climate_state,
        "hvac_action": inputs.hvac_action,
        "air_temperature_entity": air_entity,
        "current_temperature": inputs.current_temperature,
        "target_temperature": inputs.target_temperature,
        "temperature_delta": inputs.temperature_delta,
        "temperature_context_available": inputs.temperature_context_available,
        "too_warm": demand.too_warm,
        "too_cold": demand.too_cold,
        "average_15m": inputs.average_15m,
        "trend_c_per_hour": inputs.trend_c_per_hour,
        "trend_label": inputs.trend_label,
        "temperature_summary": inputs.temperature_summary,
        "smart_start_delta_c": TOO_WARM_C,
        "smart_stop_delta_c": SMART_STOP_DELTA_C,
        "smart_start_trend_c_per_hour": WARMING_C_H,
        "smart_stop_trend_c_per_hour": SMART_STOP_TREND_C_H,
        "power_entity": inputs.power_entity or power_entity,
        "power_entity_candidates": (power_entity,),
        "power_w": inputs.power_w,
        "compressor_active": inputs.compressor_active,
        "compressor_threshold_w": COMPRESSOR_W,
        "last_compressor_active_at": data.get(RUNTIME_LAST_COMPRESSOR_ACTIVE_AT),
        "previous_compressor_active": data.get(RUNTIME_PREVIOUS_COMPRESSOR_ACTIVE),
        "afterrun_active": afterrun_active,
        "afterrun_until": afterrun_until,
        "afterrun_remaining_minutes": afterrun_remaining,
        "afterrun_minutes": _afterrun_minutes(hass),
        "afterrun_modes": tuple(sorted(AFTERRUN_MODES)),
        "afterrun_entity": _afterrun_entity(hass),
        "afterrun_entity_configured": AFTER_RUN_NUMBER,
        "fan_switch_entity": FAN,
        "fan_state": inputs.fan_state,
        "fan_power_entity": fan_power_entity,
        "fan_power_w": inputs.fan_power_w,
        "fan_running": inputs.fan_running,
        "fan_should_run": decision.should_run,
        "fan_recommendation": "run" if decision.should_run else "stop" if enabled else "unmanaged",
        "fan_action_needed": decision.action_needed,
        "apply_required": decision.action_needed,
        "fan_action": decision.action,
        "fan_command": decision.command,
        "fan_reason": decision.reason,
        "fan_switch_ok": inputs.fan_switch_ok,
        "temperature_sensor_ok": inputs.temperature_sensor_ok,
        "power_sensor_ok": inputs.power_sensor_ok,
        "power_sensor_candidates_ok": _available(hass, power_entity),
        "fan_power_sensor_ok": inputs.fan_power_sensor_ok,
        "control_interval_seconds": INTERVAL_SECONDS,
        "max_reasonable_warming_c_per_hour": MAX_REASONABLE_WARMING_C_H,
    }


def build_kegerator_fan_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    """Return a read-only snapshot without changing runtime transitions."""
    inputs, decision, active, until, remaining = _evaluate(hass, mutate=False)
    return _snapshot_from(hass, inputs, decision, active, until, remaining)


async def async_apply_kegerator_fan_auto(hass: HomeAssistant) -> dict[str, Any]:
    """Evaluate and apply one fan-control tick through the policy router."""
    async with _apply_lock(hass):
        inputs, decision, active, until, remaining = _evaluate(hass, mutate=True)
        before_state, before_power = inputs.fan_state, inputs.fan_power_w
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
                    "scheduler_owner": SCHEDULER_OWNER,
                    "fan_mode": _fan_mode(hass),
                    "fan_reason": decision.reason,
                    "fan_should_run": decision.should_run,
                    "compressor_active": inputs.compressor_active,
                    "afterrun_active": active,
                    "afterrun_until": until,
                    "afterrun_remaining_minutes": remaining,
                    "power_entity": inputs.power_entity,
                    "power_w": inputs.power_w,
                    "active_climate_entity": inputs.active_climate_entity,
                    "climate_conflict": inputs.climate_conflict,
                    "temperature_delta": inputs.temperature_delta,
                    "trend_c_per_hour": inputs.trend_c_per_hour,
                },
            )
            await asyncio.sleep(1)

        after_inputs = _read_inputs(hass)
        result = "no_action"
        if decision.action != "none":
            result = (
                "applied"
                if after_inputs.fan_state == decision.desired_switch_state
                else "attempted_no_state_change"
            )

        apply_result = {
            "at": dt_util.utcnow().isoformat(),
            "strategy": STRATEGY,
            "scheduler_owner": SCHEDULER_OWNER,
            "action": decision.action,
            "command": decision.command,
            "reason": decision.reason,
            "desired_fan_state": decision.state,
            "desired_switch_state": decision.desired_switch_state,
            "before_state": before_state,
            "before_power_w": before_power,
            "after_state": after_inputs.fan_state,
            "after_power_w": after_inputs.fan_power_w,
            "policy_status": policy_result.get("status") if isinstance(policy_result, dict) else None,
            "policy_summary": policy_result.get("summary") if isinstance(policy_result, dict) else None,
            "result": result,
        }
        data = _bucket(hass)
        data[RUNTIME_LAST_APPLY] = apply_result
        data[RUNTIME_LAST_POLICY_RESULT] = policy_result
        data["last_apply_action"] = decision.action
        data["last_apply_reason"] = decision.reason
        data["last_apply_at"] = apply_result["at"]

        refreshed = _evaluate(hass, mutate=False)
        return _snapshot_from(hass, *refreshed)


def async_disable_kegerator_fan_auto(hass: HomeAssistant) -> None:
    """Release fan ownership without forcing the physical fan off."""
    data = _bucket(hass)
    _clear_afterrun(hass, "fan_auto_disabled", clear_previous=True)
    disabled_at = dt_util.utcnow().isoformat()
    data["disabled_at"] = disabled_at
    data["last_apply_action"] = "disabled"
    data["last_apply_reason"] = "fan_auto_disabled"
    data["last_apply_at"] = disabled_at
    data[RUNTIME_LAST_POLICY_RESULT] = None
    data[RUNTIME_LAST_APPLY] = {
        "at": disabled_at,
        "action": "disabled",
        "reason": "fan_auto_disabled",
        "result": "disabled_unmanaged",
    }
