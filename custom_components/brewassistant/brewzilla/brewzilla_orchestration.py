"""BrewZilla orchestration helpers."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant, State
from homeassistant.util import dt as dt_util

from ..brewday.brewday_audit import async_record_brewday_audit_tick
from ..brewday.brewday_runtime import build_brewday_runtime_snapshot
from .brewzilla_owned_control import clear_owned_control, get_owned_control

BREWZILLA_TARGET_NUMBER = "number.brewzilla_target_temperature"
BREWZILLA_TEMP_SENSOR = "sensor.brewzilla_temperature"
BREWZILLA_CONNECTION_SENSOR = "sensor.brewzilla_connection"
BREWZILLA_HEATER_SWITCH = "switch.brewzilla_heater"
BREWZILLA_PUMP_SWITCH = "switch.brewzilla_pump"
BREWZILLA_POWER_SENSOR = "sensor.brewzilla_power"
BREWZILLA_MAIN_SWITCH = "switch.brewzilla"
BREWZILLA_HEAT_UTILIZATION = "number.brewzilla_heat_utilization"
BREWZILLA_PUMP_UTILIZATION = "number.brewzilla_pump_utilization"

SOURCE = "brewzilla_orchestration"
MIN_TARGET_TEMP = 0.0
MAX_TARGET_TEMP = 110.0
TARGET_SYNC_TOLERANCE = 0.1
UTILIZATION_TOLERANCE = 0.1
MAX_SNAPSHOT_AGE_MINUTES = 15.0
RAPT_OBSERVATION_WARN_AGE_SECONDS = 300
RAPT_CRITICAL_WINDOW_SECONDS = 90
PAUSED_TARGET_REWIND_GUARD_DELTA = -2.0
BOIL_TARGET_FALLBACK = 100.0
MASH_IN_APPROACH_MARGIN_C = 5.0
MASH_IN_READY_MARGIN_C = 0.5
MASH_IN_OVERSHOOT_MARGIN_C = 0.3
MASH_IN_RAMP_HEAT_UTILIZATION = 100.0
MASH_IN_APPROACH_HEAT_UTILIZATION = 60.0
MASH_IN_APPROACH_PUMP_UTILIZATION = 50.0
MASH_IN_READY_HEAT_UTILIZATION = 40.0
MASH_IN_OVERSHOOT_HEAT_UTILIZATION = 0.0
MASH_IN_PUMP_OFF_UTILIZATION = 0.0
MASH_HOLD_LOWER_MARGIN_C = 0.3
MASH_HOLD_UPPER_MARGIN_C = 0.5
MASH_HOLD_HEAT_UTILIZATION = 40.0
MASH_HOLD_RECOVERY_HEAT_UTILIZATION = 55.0
MASH_HOLD_OVERSHOOT_HEAT_UTILIZATION = 0.0
MASH_HOLD_PUMP_UTILIZATION = 50.0
MASH_HOLD_AWAITING_CONFIRM_PUMP_UTILIZATION = 0.0
ABORT_LOCKOUT_SECONDS = 600
ABORT_DATA_KEY = "brewzilla_last_abort"

_BAD = {None, "unknown", "unavailable", "none", ""}
_ACTIVE_RUNTIME_STATES = {
    "live",
    "running",
    "paused",
    "awaiting_snapshot",
    "prepared",
    "awaiting_confirm",
}
_MASH_WORDS = ("mash", "mäsk", "protein", "beta", "alpha", "saccharification", "sack", "rest")
_BOIL_WORDS = ("boil", "kok", "boiling", "heating to boil", "värm till kok", "kokning", "kokgiva")
_COOL_WORDS = ("cool", "chill", "kyl")
_MASH_IN_HEAT_WORDS = (
    "heat strike",
    "strike water",
    "heating up to mash",
    "heating up to mash-in",
    "heat to mash",
    "heat mash",
    "värm mäsk",
    "värmning till mäsk",
)
_MASH_HOLD_WORDS = (
    "mash in",
    "mash-in",
    "mäsk-in",
    "saccharification",
    "mash rest",
    "mash hold",
    "hold mash",
    "mäskrast",
    "rest",
)
LOCAL_LIVE_ENTITY_IDS = (BREWZILLA_POWER_SENSOR,)
RAPT_CONTROL_ENTITY_IDS = (BREWZILLA_TEMP_SENSOR, BREWZILLA_TARGET_NUMBER)
RAPT_CONFIG_ENTITY_IDS = (BREWZILLA_HEAT_UTILIZATION, BREWZILLA_PUMP_UTILIZATION)
RAPT_BREWZILLA_STATIC_ENTITY_IDS = (
    BREWZILLA_CONNECTION_SENSOR,
    BREWZILLA_MAIN_SWITCH,
    BREWZILLA_HEATER_SWITCH,
    BREWZILLA_PUMP_SWITCH,
)
RAPT_BREWZILLA_DYNAMIC_ENTITY_IDS = LOCAL_LIVE_ENTITY_IDS + RAPT_CONTROL_ENTITY_IDS + RAPT_CONFIG_ENTITY_IDS
RAPT_BREWZILLA_ENTITY_IDS = RAPT_BREWZILLA_DYNAMIC_ENTITY_IDS + RAPT_BREWZILLA_STATIC_ENTITY_IDS


def _state(hass: HomeAssistant, entity_id: str, default: str | None = None) -> str | None:
    entity_state = hass.states.get(entity_id)
    if entity_state is None or entity_state.state in _BAD:
        return default
    return entity_state.state


def _state_obj(hass: HomeAssistant, entity_id: str) -> State | None:
    entity_state = hass.states.get(entity_id)
    if entity_state is None or entity_state.state in _BAD:
        return None
    return entity_state


def _float(hass: HomeAssistant, entity_id: str) -> float | None:
    raw = _state(hass, entity_id)
    if raw in _BAD:
        return None
    try:
        return float(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _bool_state(hass: HomeAssistant, entity_id: str, default: bool = False) -> bool:
    fallback = "on" if default else "off"
    return str(_state(hass, entity_id, fallback)).lower() in {"on", "true", "yes"}


def _runtime_active(state: str | None) -> bool:
    return (state or "").lower() in _ACTIVE_RUNTIME_STATES


def _abort_lockout(hass: HomeAssistant) -> dict[str, Any] | None:
    """Return active ABORT lockout diagnostics, if any."""
    abort = hass.data.setdefault("brewassistant", {}).get(ABORT_DATA_KEY)
    if not isinstance(abort, dict):
        return None

    aborted_at_raw = abort.get("aborted_at")
    if aborted_at_raw is None:
        return None

    aborted_at = dt_util.parse_datetime(str(aborted_at_raw))
    if aborted_at is None:
        return None

    age_seconds = max(
        0,
        int((dt_util.utcnow() - dt_util.as_utc(aborted_at)).total_seconds()),
    )
    remaining_seconds = ABORT_LOCKOUT_SECONDS - age_seconds
    if remaining_seconds <= 0:
        return None

    return {
        "active": True,
        "age_seconds": age_seconds,
        "remaining_seconds": remaining_seconds,
        "seconds": ABORT_LOCKOUT_SECONDS,
        "reason": f"BrewZilla ABORT lockout active ({remaining_seconds}s remaining)",
        "last_abort": abort,
    }


def _entity_age_seconds(entity_state: State | None) -> int | None:
    if entity_state is None:
        return None
    return max(0, int((dt_util.utcnow() - dt_util.as_utc(entity_state.last_updated)).total_seconds()))


def _entity_age_summary(entities: dict[str, dict[str, Any]], entity_ids: tuple[str, ...]) -> dict[str, Any]:
    newest_age: int | None = None
    oldest_age: int | None = None
    newest_entity: str | None = None
    oldest_entity: str | None = None
    for entity_id in entity_ids:
        age = entities.get(entity_id, {}).get("age_seconds")
        if age is None:
            continue
        if newest_age is None or age < newest_age:
            newest_age = age
            newest_entity = entity_id
        if oldest_age is None or age > oldest_age:
            oldest_age = age
            oldest_entity = entity_id
    return {
        "newest_entity": newest_entity,
        "newest_age_seconds": newest_age,
        "oldest_entity": oldest_entity,
        "oldest_age_seconds": oldest_age,
    }


def _rapt_brewzilla_observation(hass: HomeAssistant) -> dict[str, Any]:
    entities: dict[str, dict[str, Any]] = {}
    for entity_id in RAPT_BREWZILLA_ENTITY_IDS:
        entity_state = _state_obj(hass, entity_id)
        age = _entity_age_seconds(entity_state)
        entities[entity_id] = {
            "state": entity_state.state if entity_state is not None else None,
            "last_updated": entity_state.last_updated.isoformat() if entity_state is not None else None,
            "age_seconds": age,
        }
    all_summary = _entity_age_summary(entities, RAPT_BREWZILLA_ENTITY_IDS)
    dynamic_summary = _entity_age_summary(entities, RAPT_BREWZILLA_DYNAMIC_ENTITY_IDS)
    local_summary = _entity_age_summary(entities, LOCAL_LIVE_ENTITY_IDS)
    control_summary = _entity_age_summary(entities, RAPT_CONTROL_ENTITY_IDS)
    config_summary = _entity_age_summary(entities, RAPT_CONFIG_ENTITY_IDS)
    static_summary = _entity_age_summary(entities, RAPT_BREWZILLA_STATIC_ENTITY_IDS)
    dynamic_age = dynamic_summary.get("oldest_age_seconds")
    local_age = local_summary.get("oldest_age_seconds")
    control_age = control_summary.get("oldest_age_seconds")
    config_age = config_summary.get("oldest_age_seconds")
    temperature_age = entities.get(BREWZILLA_TEMP_SENSOR, {}).get("age_seconds")
    power_age = entities.get(BREWZILLA_POWER_SENSOR, {}).get("age_seconds")
    target_age = entities.get(BREWZILLA_TARGET_NUMBER, {}).get("age_seconds")
    heat_util_age = entities.get(BREWZILLA_HEAT_UTILIZATION, {}).get("age_seconds")
    pump_util_age = entities.get(BREWZILLA_PUMP_UTILIZATION, {}).get("age_seconds")
    return {
        "rapt_brewzilla_entities": entities,
        "rapt_brewzilla_entity_count": len(entities),
        "rapt_brewzilla_newest_entity": all_summary.get("newest_entity"),
        "rapt_brewzilla_newest_age_seconds": all_summary.get("newest_age_seconds"),
        "rapt_brewzilla_oldest_entity": all_summary.get("oldest_entity"),
        "rapt_brewzilla_oldest_age_seconds": all_summary.get("oldest_age_seconds"),
        "rapt_brewzilla_dynamic_newest_entity": dynamic_summary.get("newest_entity"),
        "rapt_brewzilla_dynamic_newest_age_seconds": dynamic_summary.get("newest_age_seconds"),
        "rapt_brewzilla_dynamic_oldest_entity": dynamic_summary.get("oldest_entity"),
        "rapt_brewzilla_dynamic_oldest_age_seconds": dynamic_summary.get("oldest_age_seconds"),
        "brewzilla_local_live_oldest_entity": local_summary.get("oldest_entity"),
        "brewzilla_local_live_age_seconds": local_age,
        "brewzilla_local_power_age_seconds": power_age,
        "brewzilla_rapt_control_oldest_entity": control_summary.get("oldest_entity"),
        "brewzilla_rapt_control_age_seconds": control_age,
        "brewzilla_rapt_config_oldest_entity": config_summary.get("oldest_entity"),
        "brewzilla_rapt_config_age_seconds": config_age,
        "brewzilla_rapt_static_oldest_entity": static_summary.get("oldest_entity"),
        "brewzilla_rapt_static_age_seconds": static_summary.get("oldest_age_seconds"),
        "rapt_brewzilla_static_oldest_entity": static_summary.get("oldest_entity"),
        "rapt_brewzilla_static_oldest_age_seconds": static_summary.get("oldest_age_seconds"),
        "rapt_brewzilla_dynamic_age_seconds": dynamic_age,
        "rapt_brewzilla_dynamic_age_minutes": round(dynamic_age / 60, 1) if dynamic_age is not None else None,
        "rapt_brewzilla_temperature_age_seconds": temperature_age,
        "rapt_brewzilla_power_age_seconds": power_age,
        "rapt_brewzilla_target_age_seconds": target_age,
        "rapt_brewzilla_heat_util_age_seconds": heat_util_age,
        "rapt_brewzilla_pump_util_age_seconds": pump_util_age,
        "rapt_brewzilla_poll_age_seconds": control_age,
        "rapt_brewzilla_poll_age_minutes": round(control_age / 60, 1) if control_age is not None else None,
        "rapt_brewzilla_poll_warning": bool(control_age is not None and control_age > RAPT_OBSERVATION_WARN_AGE_SECONDS),
    }


def _current_stage_text(runtime: dict[str, Any]) -> str:
    return f"{runtime.get('stage') or ''} {runtime.get('step') or ''} {runtime.get('raw_step_name') or ''}".lower()


def _stage_text(runtime: dict[str, Any]) -> str:
    return f"{runtime.get('stage') or ''} {runtime.get('step') or ''} {runtime.get('next_step') or ''} {runtime.get('raw_step_name') or ''}".lower()


def _stage_is_boil(runtime: dict[str, Any]) -> bool:
    return any(word in _stage_text(runtime) for word in _BOIL_WORDS)


def _stage_is_heat_to_mash_in(runtime: dict[str, Any]) -> bool:
    text = _current_stage_text(runtime)
    if any(word in text for word in _BOIL_WORDS + _COOL_WORDS):
        return False
    return any(word in text for word in _MASH_IN_HEAT_WORDS)


def _stage_is_mash_hold(runtime: dict[str, Any]) -> bool:
    text = _current_stage_text(runtime)
    if any(word in text for word in _BOIL_WORDS + _COOL_WORDS + _MASH_IN_HEAT_WORDS):
        return False
    return any(word in text for word in _MASH_HOLD_WORDS) or (
        "mash" in text and "strike" not in text and "heat" not in text
    )


def _stage_recommends_pump(runtime: dict[str, Any]) -> bool:
    if _stage_is_boil(runtime):
        return False
    return any(word in _stage_text(runtime) for word in _MASH_WORDS)


def _target_valid(target: float | None) -> bool:
    return target is not None and MIN_TARGET_TEMP <= target <= MAX_TARGET_TEMP


def _utilization_action_needed(current: float | None, desired: float | None) -> bool:
    return desired is not None and (current is None or abs(float(desired) - float(current)) > UTILIZATION_TOLERANCE)


def _inactive_strategy() -> dict[str, Any]:
    return {
        "active": False,
        "phase": None,
        "desired_heat_utilization": None,
        "desired_pump_utilization": None,
        "desired_heater_on": None,
        "desired_pump_on": None,
        "mash_in_confirmation_recommended": False,
        "reason": None,
    }


def _mash_in_heat_strategy(
    runtime: dict[str, Any],
    *,
    current_temperature: float | None,
    requested_target: float | None,
) -> dict[str, Any]:
    """Return stage-specific BrewZilla actions for heating strike water/mash-in."""
    if not _stage_is_heat_to_mash_in(runtime) or current_temperature is None or requested_target is None:
        return _inactive_strategy()

    delta_to_target = requested_target - current_temperature
    if delta_to_target > MASH_IN_APPROACH_MARGIN_C:
        phase = "ramp_far"
        desired_heat_utilization = MASH_IN_RAMP_HEAT_UTILIZATION
        desired_pump_utilization = MASH_IN_PUMP_OFF_UTILIZATION
        desired_heater_on = True
        desired_pump_on = False
        mash_in_confirmation_recommended = False
        reason = "Heating to mash-in: far from target; heater 100%, pump OFF."
    elif delta_to_target > MASH_IN_READY_MARGIN_C:
        phase = "approach"
        desired_heat_utilization = MASH_IN_APPROACH_HEAT_UTILIZATION
        desired_pump_utilization = MASH_IN_APPROACH_PUMP_UTILIZATION
        desired_heater_on = True
        desired_pump_on = True
        mash_in_confirmation_recommended = False
        reason = "Heating to mash-in: target within 5°C; taper heat to 60% and mix with pump at 50%."
    elif current_temperature > requested_target + MASH_IN_OVERSHOOT_MARGIN_C:
        phase = "overshoot"
        desired_heat_utilization = MASH_IN_OVERSHOOT_HEAT_UTILIZATION
        desired_pump_utilization = MASH_IN_PUMP_OFF_UTILIZATION
        desired_heater_on = False
        desired_pump_on = False
        mash_in_confirmation_recommended = True
        reason = "Heating to mash-in: above target; heat OFF and pump OFF while awaiting operator decision."
    else:
        phase = "mash_in_ready"
        desired_heat_utilization = MASH_IN_READY_HEAT_UTILIZATION
        desired_pump_utilization = MASH_IN_PUMP_OFF_UTILIZATION
        desired_heater_on = True
        desired_pump_on = False
        mash_in_confirmation_recommended = True
        reason = "Mash-in target reached; hold gently, pump OFF, await mash-in confirmation."

    return {
        "active": True,
        "phase": phase,
        "delta_to_target": round(delta_to_target, 2),
        "desired_heat_utilization": desired_heat_utilization,
        "desired_pump_utilization": desired_pump_utilization,
        "desired_heater_on": desired_heater_on,
        "desired_pump_on": desired_pump_on,
        "mash_in_confirmation_recommended": mash_in_confirmation_recommended,
        "reason": reason,
    }


def _mash_hold_strategy(
    runtime: dict[str, Any],
    *,
    runtime_state: str,
    current_temperature: float | None,
    requested_target: float | None,
) -> dict[str, Any]:
    """Return BrewZilla actions for mash-in/rest temperature holding."""
    if not _stage_is_mash_hold(runtime) or current_temperature is None or requested_target is None:
        return _inactive_strategy()

    text = _current_stage_text(runtime)
    awaiting_mash_in_confirmation = runtime_state == "awaiting_confirm" and (
        "mash in" in text or "mash-in" in text or "mäsk-in" in text
    )
    desired_pump_on = not awaiting_mash_in_confirmation
    desired_pump_utilization = (
        MASH_HOLD_AWAITING_CONFIRM_PUMP_UTILIZATION
        if awaiting_mash_in_confirmation
        else MASH_HOLD_PUMP_UTILIZATION
    )
    delta_to_target = requested_target - current_temperature

    if delta_to_target > MASH_HOLD_LOWER_MARGIN_C:
        phase = "mash_hold_recover"
        desired_heat_utilization = MASH_HOLD_RECOVERY_HEAT_UTILIZATION
        desired_heater_on = True
        reason = "Mash hold: below target; apply moderate heat and circulate if mash-in is confirmed."
    elif current_temperature > requested_target + MASH_HOLD_UPPER_MARGIN_C:
        phase = "mash_hold_overshoot"
        desired_heat_utilization = MASH_HOLD_OVERSHOOT_HEAT_UTILIZATION
        desired_heater_on = False
        reason = "Mash hold: above target; heat OFF while temperature settles."
    else:
        phase = "mash_hold_stable"
        desired_heat_utilization = MASH_HOLD_HEAT_UTILIZATION
        desired_heater_on = True
        reason = "Mash hold: maintain target with gentle heat and controlled circulation."

    if awaiting_mash_in_confirmation:
        reason = f"{reason} Pump remains OFF while awaiting mash-in confirmation."

    return {
        "active": True,
        "phase": phase,
        "delta_to_target": round(delta_to_target, 2),
        "desired_heat_utilization": desired_heat_utilization,
        "desired_pump_utilization": desired_pump_utilization,
        "desired_heater_on": desired_heater_on,
        "desired_pump_on": desired_pump_on,
        "mash_in_confirmation_recommended": awaiting_mash_in_confirmation,
        "reason": reason,
    }


def build_orchestration_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    runtime = build_brewday_runtime_snapshot(hass)
    runtime_state = str(runtime.get("runtime_state") or "idle")
    abort_lockout = _abort_lockout(hass)
    completed_runtime = runtime_state == "completed"
    requested_target = runtime.get("target_temperature")
    try:
        requested_target = float(requested_target) if requested_target is not None else None
    except (TypeError, ValueError):
        requested_target = None

    applied_target = _float(hass, BREWZILLA_TARGET_NUMBER)
    current_temperature = _float(hass, BREWZILLA_TEMP_SENSOR)
    heat_utilization = _float(hass, BREWZILLA_HEAT_UTILIZATION)
    pump_utilization = _float(hass, BREWZILLA_PUMP_UTILIZATION)
    connection = _state(hass, BREWZILLA_CONNECTION_SENSOR, "unknown")
    connected = connection == "Connected"
    awaiting_snapshot = bool(runtime.get("awaiting_snapshot"))
    snapshot_age_minutes = float(runtime.get("snapshot_age_minutes") or 0.0)
    step_remaining_seconds = int(runtime.get("current_step_remaining_seconds") or runtime.get("time_remaining_seconds") or 0)
    heater_on = _bool_state(hass, BREWZILLA_HEATER_SWITCH)
    pump_on = _bool_state(hass, BREWZILLA_PUMP_SWITCH)
    boil_stage = _stage_is_boil(runtime)
    boil_target_fallback_active = False
    runtime_source = str(runtime.get("source") or "")
    requested_target_source = "manual_brewday" if runtime_source == "Manual Brewday" else "brew_tracker"

    if requested_target is None and boil_stage and _runtime_active(runtime_state):
        requested_target = BOIL_TARGET_FALLBACK
        boil_target_fallback_active = True
        requested_target_source = "boil_fallback"

    target_delta = None
    if requested_target is not None and applied_target is not None:
        target_delta = round(requested_target - applied_target, 2)

    paused_target_rewind_blocked = bool(
        runtime_state == "paused"
        and target_delta is not None
        and target_delta < PAUSED_TARGET_REWIND_GUARD_DELTA
    )
    target_sync_needed = target_delta is not None and abs(target_delta) > TARGET_SYNC_TOLERANCE
    heating_needed = False
    if requested_target is not None and current_temperature is not None:
        heating_needed = current_temperature < requested_target - TARGET_SYNC_TOLERANCE

    mash_in_strategy = _mash_in_heat_strategy(
        runtime,
        current_temperature=current_temperature,
        requested_target=requested_target,
    )
    mash_hold_strategy = _mash_hold_strategy(
        runtime,
        runtime_state=runtime_state,
        current_temperature=current_temperature,
        requested_target=requested_target,
    )
    active_strategy = mash_in_strategy if mash_in_strategy.get("active") else mash_hold_strategy

    pump_recommended = _stage_recommends_pump(runtime)
    heater_action_needed = heating_needed and not heater_on
    pump_action_needed = pump_recommended and not pump_on
    pump_stop_needed = boil_stage and pump_on
    heater_stop_needed = completed_runtime and heater_on
    desired_heat_utilization = active_strategy.get("desired_heat_utilization")
    desired_pump_utilization = active_strategy.get("desired_pump_utilization")

    if abort_lockout is not None:
        owned_control = clear_owned_control(hass, reason="abort_lockout")
    elif completed_runtime:
        owned_control = clear_owned_control(hass, reason="completed_runtime")
    else:
        owned_control = get_owned_control(hass)

    owned_control_active = bool(
        owned_control.get("active")
        and _runtime_active(runtime_state)
        and not completed_runtime
        and abort_lockout is None
    )
    ba_owned_desired_heat_utilization = (
        owned_control.get("desired_heat_utilization") if owned_control_active else None
    )
    ba_owned_desired_pump_utilization = (
        owned_control.get("desired_pump_utilization") if owned_control_active else None
    )

    if ba_owned_desired_heat_utilization is not None:
        desired_heat_utilization = ba_owned_desired_heat_utilization
    if ba_owned_desired_pump_utilization is not None:
        desired_pump_utilization = ba_owned_desired_pump_utilization

    heat_utilization_action_needed = False
    pump_utilization_action_needed = False

    if active_strategy.get("active") and not completed_runtime:
        desired_heater_on = active_strategy.get("desired_heater_on")
        desired_pump_on = active_strategy.get("desired_pump_on")
        pump_recommended = bool(desired_pump_on)
        heater_action_needed = bool(desired_heater_on is True and not heater_on)
        heater_stop_needed = bool(desired_heater_on is False and heater_on)
        pump_action_needed = bool(desired_pump_on is True and not pump_on)
        pump_stop_needed = bool((desired_pump_on is False and pump_on) or (boil_stage and pump_on))

    if (active_strategy.get("active") or owned_control_active) and not completed_runtime:
        heat_utilization_action_needed = _utilization_action_needed(
            heat_utilization,
            desired_heat_utilization,
        )
        pump_utilization_action_needed = _utilization_action_needed(
            pump_utilization,
            desired_pump_utilization,
        )

    ba_owned_reassert_action_needed = bool(
        owned_control_active
        and (heat_utilization_action_needed or pump_utilization_action_needed)
    )

    completion_stop_needed = completed_runtime and (heater_on or pump_on)
    completion_pump_stop_needed = completed_runtime and pump_on

    rapt_observation = _rapt_brewzilla_observation(hass)
    control_age = rapt_observation.get("brewzilla_rapt_control_age_seconds")
    critical_refresh_recommended = bool(
        _runtime_active(runtime_state)
        and (
            awaiting_snapshot
            or target_sync_needed
            or heater_action_needed
            or heater_stop_needed
            or pump_action_needed
            or pump_stop_needed
            or heat_utilization_action_needed
            or pump_utilization_action_needed
            or (0 < step_remaining_seconds <= RAPT_CRITICAL_WINDOW_SECONDS)
            or (control_age is not None and control_age > RAPT_OBSERVATION_WARN_AGE_SECONDS)
        )
    )

    hard_block = None
    if abort_lockout is not None:
        hard_block = str(abort_lockout.get("reason") or "BrewZilla ABORT lockout active")
    elif not connected:
        hard_block = "BrewZilla disconnected"
    elif completed_runtime:
        hard_block = None
    elif not _runtime_active(runtime_state):
        hard_block = f"Brewday runtime {runtime_state}"
    elif snapshot_age_minutes > MAX_SNAPSHOT_AGE_MINUTES:
        hard_block = "Brewday Runtime snapshot too old"
    elif not _target_valid(requested_target):
        hard_block = "Missing or invalid Brewday Runtime target"
    elif paused_target_rewind_blocked:
        hard_block = "Paused target rewind guard active"

    can_control = hard_block is None
    action_needed = (
        target_sync_needed
        or heater_action_needed
        or heater_stop_needed
        or pump_action_needed
        or pump_stop_needed
        or heat_utilization_action_needed
        or pump_utilization_action_needed
        or completion_stop_needed
    )
    mode = "direct-control" if can_control and action_needed else "monitor"
    if hard_block is not None:
        mode = "blocked"

    reason = hard_block or "Direct production flow active"
    if completed_runtime and completion_stop_needed:
        reason = "Brewday runtime completed; heater/pump should be OFF"
    elif completed_runtime:
        reason = "Brewday runtime completed"
    elif hard_block is None and boil_target_fallback_active:
        reason = "Boil stage detected without Brewday Runtime target; using 100°C boil fallback"
    if not completed_runtime and hard_block is None and ba_owned_reassert_action_needed:
        reason = "BA-owned Brewday Advice utilization should be reasserted"
    elif not completed_runtime and hard_block is None and mash_in_strategy.get("active"):
        reason = str(mash_in_strategy.get("reason") or reason)
    elif not completed_runtime and hard_block is None and mash_hold_strategy.get("active"):
        reason = str(mash_hold_strategy.get("reason") or reason)
    elif not completed_runtime and hard_block is None and pump_stop_needed:
        reason = "Pump should be OFF"
    elif not completed_runtime and hard_block is None and heater_stop_needed:
        reason = "Heater should be OFF"
    elif not completed_runtime and hard_block is None and heater_action_needed:
        reason = "Heating needed; heater should be ON"
    elif not completed_runtime and hard_block is None and pump_action_needed:
        reason = "Mash circulation recommended; pump should be ON"
    elif not completed_runtime and hard_block is None and awaiting_snapshot:
        reason = "Awaiting fresh snapshot, using current valid Brewday Runtime target"
    elif not completed_runtime and hard_block is None and runtime_state == "paused":
        reason = "Brewday paused; maintaining current valid target"

    if completed_runtime:
        target_sync_needed = False
        heating_needed = False
        heater_action_needed = False
        pump_action_needed = False
        heat_utilization_action_needed = False
        pump_utilization_action_needed = False

    return {
        "source": SOURCE,
        "connected": connected,
        "connection_state": connection,
        "brewday_state": runtime_state,
        "runtime_source": runtime_source,
        "runtime_stage": runtime.get("stage"),
        "runtime_step": runtime.get("step"),
        "runtime_raw_step_name": runtime.get("raw_step_name"),
        "runtime_raw_step_index": runtime.get("raw_step_index"),
        "runtime_resolved_step_index": runtime.get("resolved_step_index"),
        "runtime_step_remaining_seconds": step_remaining_seconds,
        "requested_target": requested_target,
        "requested_target_source": requested_target_source,
        "boil_stage": boil_stage,
        "boil_target_fallback_active": boil_target_fallback_active,
        "completed_runtime": completed_runtime,
        "terminal_complete_inferred": runtime.get("terminal_complete_inferred"),
        "applied_target": applied_target,
        "current_temperature": current_temperature,
        "target_delta": target_delta,
        "target_sync_needed": target_sync_needed,
        "paused_target_rewind_blocked": paused_target_rewind_blocked,
        "can_apply_target": can_control and action_needed,
        "heating_needed": heating_needed,
        "heater_on": heater_on,
        "heater_action_needed": heater_action_needed,
        "heater_stop_needed": heater_stop_needed,
        "pump_recommended": pump_recommended,
        "pump_on": pump_on,
        "pump_action_needed": pump_action_needed,
        "pump_stop_needed": pump_stop_needed,
        "heat_utilization": heat_utilization,
        "pump_utilization": pump_utilization,
        "desired_heat_utilization": desired_heat_utilization,
        "desired_pump_utilization": desired_pump_utilization,
        "ba_owned_control_active": owned_control_active,
        "ba_owned_control_source": owned_control.get("source"),
        "ba_owned_control_recommendation_id": owned_control.get("recommendation_id"),
        "ba_owned_desired_heat_utilization": ba_owned_desired_heat_utilization,
        "ba_owned_desired_pump_utilization": ba_owned_desired_pump_utilization,
        "ba_owned_control_created_at": owned_control.get("created_at"),
        "ba_owned_control_updated_at": owned_control.get("updated_at"),
        "ba_owned_control_cleared_at": owned_control.get("cleared_at"),
        "ba_owned_control_clear_reason": owned_control.get("clear_reason"),
        "ba_owned_reassert_action_needed": ba_owned_reassert_action_needed,
        "heat_utilization_action_needed": heat_utilization_action_needed,
        "pump_utilization_action_needed": pump_utilization_action_needed,
        "mash_in_heat_strategy_active": bool(mash_in_strategy.get("active")),
        "mash_in_heat_strategy_phase": mash_in_strategy.get("phase"),
        "mash_in_heat_strategy_delta_to_target": mash_in_strategy.get("delta_to_target"),
        "mash_in_confirmation_recommended": bool(active_strategy.get("mash_in_confirmation_recommended")),
        "mash_hold_strategy_active": bool(mash_hold_strategy.get("active")),
        "mash_hold_strategy_phase": mash_hold_strategy.get("phase"),
        "mash_hold_strategy_delta_to_target": mash_hold_strategy.get("delta_to_target"),
        "desired_heater_on": active_strategy.get("desired_heater_on"),
        "desired_pump_on": active_strategy.get("desired_pump_on"),
        "completion_stop_needed": completion_stop_needed,
        "completion_pump_stop_needed": completion_pump_stop_needed,
        "awaiting_snapshot": awaiting_snapshot,
        "snapshot_age_minutes": snapshot_age_minutes,
        "rapt_critical_refresh_recommended": critical_refresh_recommended,
        "orchestration_mode": mode,
        "safety_state": "operator-supervised",
        "control_reason": reason,
        "abort_lockout_active": bool(abort_lockout),
        "abort_lockout_remaining_seconds": (
            abort_lockout.get("remaining_seconds") if abort_lockout is not None else None
        ),
        "abort_lockout_age_seconds": (
            abort_lockout.get("age_seconds") if abort_lockout is not None else None
        ),
        "abort_lockout_seconds": ABORT_LOCKOUT_SECONDS,
        "has_pending_action": False,
        "pending_action": None,
        "pending_summary": None,
        "mode_scope": "direct_with_abort",
        **rapt_observation,
    }


async def _call_switch(hass: HomeAssistant, service_suffix: str, entity_id: str) -> None:
    await hass.services.async_call(
        "switch",
        f"turn_{service_suffix}",
        {"entity_id": entity_id},
        blocking=True,
    )


async def _set_number(hass: HomeAssistant, entity_id: str, value: float) -> bool:
    if hass.states.get(entity_id) is None:
        return False
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": entity_id, "value": value},
        blocking=True,
    )
    return True


def _safe_zero(value: float | None) -> bool:
    return value is None or abs(float(value)) <= UTILIZATION_TOLERANCE


async def _enforce_brewzilla_safe_state(
    hass: HomeAssistant,
    result: dict[str, Any],
    *,
    action_prefix: str,
    force: bool = False,
) -> None:
    """Send and verify BrewZilla safe-state commands.

    ABORT/safety lockout uses the RAPT Cloud Link HA entities as the command
    surface. If an external owner writes values back during lockout, BA reasserts
    heater OFF, pump OFF, heat utilization 0 and pump utilization 0.
    """
    actions: list[str] = result.setdefault("actions", [])

    for entity_id in (BREWZILLA_HEATER_SWITCH, BREWZILLA_PUMP_SWITCH):
        state = hass.states.get(entity_id)
        if state is None:
            actions.append(f"{action_prefix}_missing:{entity_id}")
            continue
        if force or _bool_state(hass, entity_id):
            await _call_switch(hass, "off", entity_id)
            actions.append(f"{action_prefix}_off:{entity_id}")

    for entity_id in (BREWZILLA_HEAT_UTILIZATION, BREWZILLA_PUMP_UTILIZATION):
        state = hass.states.get(entity_id)
        if state is None:
            actions.append(f"{action_prefix}_missing:{entity_id}")
            continue
        current = _float(hass, entity_id)
        if force or not _safe_zero(current):
            if await _set_number(hass, entity_id, 0):
                actions.append(f"{action_prefix}_zero:{entity_id}")

    heat_utilization = _float(hass, BREWZILLA_HEAT_UTILIZATION)
    pump_utilization = _float(hass, BREWZILLA_PUMP_UTILIZATION)
    heater_on = _bool_state(hass, BREWZILLA_HEATER_SWITCH)
    pump_on = _bool_state(hass, BREWZILLA_PUMP_SWITCH)

    result["safe_state_enforced"] = True
    result["safe_state_ok"] = (
        not heater_on
        and not pump_on
        and _safe_zero(heat_utilization)
        and _safe_zero(pump_utilization)
    )
    result["safe_state_heater_on"] = heater_on
    result["safe_state_pump_on"] = pump_on
    result["safe_state_heat_utilization"] = heat_utilization
    result["safe_state_pump_utilization"] = pump_utilization


async def async_abort_brewzilla(hass: HomeAssistant) -> dict[str, Any]:
    result: dict[str, Any] = {
        "source": SOURCE,
        "status": "aborted",
        "aborted_at": dt_util.utcnow().isoformat(),
        "abort_lockout_seconds": ABORT_LOCKOUT_SECONDS,
        "actions": [],
    }
    clear_owned_control(hass, reason="abort")
    await _enforce_brewzilla_safe_state(hass, result, action_prefix="abort", force=True)
    hass.data.setdefault("brewassistant", {})[ABORT_DATA_KEY] = result
    return result


async def async_apply_brewzilla_target_if_allowed(hass: HomeAssistant) -> dict[str, Any]:
    snapshot = build_orchestration_snapshot(hass)
    if not snapshot["can_apply_target"]:
        apply_result = (
            "abort_lockout_active"
            if snapshot.get("abort_lockout_active")
            else "not_needed_or_blocked"
        )
        result = {**snapshot, "applied": False, "apply_result": apply_result, "actions": []}

        if snapshot.get("abort_lockout_active"):
            await _enforce_brewzilla_safe_state(
                hass,
                result,
                action_prefix="abort_lockout",
                force=False,
            )
            if result.get("actions"):
                result["apply_result"] = "abort_lockout_enforced"

        await async_record_brewday_audit_tick(hass, brewzilla_result=result)
        return result
    target = snapshot["requested_target"]
    target_changed = False
    actions: list[str] = []
    if snapshot.get("target_sync_needed") and target is not None:
        rounded_target = round(float(target), 1)
        await _set_number(hass, BREWZILLA_TARGET_NUMBER, rounded_target)
        target_changed = True
        actions.append(f"set_target:{rounded_target}")
    else:
        rounded_target = round(float(target), 1) if target is not None else None

    heat_utilization_changed = False
    desired_heat_utilization = snapshot.get("desired_heat_utilization")
    if snapshot.get("heat_utilization_action_needed") and desired_heat_utilization is not None:
        heat_value = round(float(desired_heat_utilization), 1)
        heat_action = (
            "ba_owned_reassert_heat_utilization"
            if snapshot.get("ba_owned_control_active")
            and snapshot.get("ba_owned_desired_heat_utilization") is not None
            else "set_heat_utilization"
        )
        if await _set_number(hass, BREWZILLA_HEAT_UTILIZATION, heat_value):
            heat_utilization_changed = True
            actions.append(f"{heat_action}:{heat_value}")

    pump_utilization_changed = False
    desired_pump_utilization = snapshot.get("desired_pump_utilization")
    if snapshot.get("pump_utilization_action_needed") and desired_pump_utilization is not None:
        pump_value = round(float(desired_pump_utilization), 1)
        pump_action = (
            "ba_owned_reassert_pump_utilization"
            if snapshot.get("ba_owned_control_active")
            and snapshot.get("ba_owned_desired_pump_utilization") is not None
            else "set_pump_utilization"
        )
        if await _set_number(hass, BREWZILLA_PUMP_UTILIZATION, pump_value):
            pump_utilization_changed = True
            actions.append(f"{pump_action}:{pump_value}")

    heater_changed = False
    if snapshot.get("heater_action_needed") and hass.states.get(BREWZILLA_HEATER_SWITCH) is not None:
        await _call_switch(hass, "on", BREWZILLA_HEATER_SWITCH)
        heater_changed = True
        actions.append("heater_on")

    heater_stopped = False
    if snapshot.get("heater_stop_needed") and hass.states.get(BREWZILLA_HEATER_SWITCH) is not None:
        await _call_switch(hass, "off", BREWZILLA_HEATER_SWITCH)
        heater_stopped = True
        actions.append("heater_off")

    pump_started = False
    if snapshot.get("pump_action_needed") and hass.states.get(BREWZILLA_PUMP_SWITCH) is not None:
        await _call_switch(hass, "on", BREWZILLA_PUMP_SWITCH)
        pump_started = True
        actions.append("pump_on")

    pump_stopped = False
    if (
        (snapshot.get("pump_stop_needed") or snapshot.get("completion_pump_stop_needed"))
        and hass.states.get(BREWZILLA_PUMP_SWITCH) is not None
    ):
        await _call_switch(hass, "off", BREWZILLA_PUMP_SWITCH)
        pump_stopped = True
        actions.append("pump_off")

    applied = (
        target_changed
        or heat_utilization_changed
        or pump_utilization_changed
        or heater_changed
        or heater_stopped
        or pump_started
        or pump_stopped
    )
    result = {
        **snapshot,
        "applied": applied,
        "apply_result": "direct_applied" if applied else "no_action_needed",
        "applied_target_value": rounded_target,
        "target_changed": target_changed,
        "heat_utilization_changed": heat_utilization_changed,
        "pump_utilization_changed": pump_utilization_changed,
        "heater_started": heater_changed,
        "heater_stopped": heater_stopped,
        "pump_started": pump_started,
        "pump_stopped": pump_stopped,
        "actions": actions,
        "executed_at": dt_util.utcnow().isoformat(),
    }
    hass.data.setdefault("brewassistant", {})["brewzilla_last_apply_result"] = result
    await async_record_brewday_audit_tick(hass, brewzilla_result=result)
    return result
