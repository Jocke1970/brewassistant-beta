"""Mash-in confirmation gate for BrewZilla orchestration."""

from __future__ import annotations

from collections.abc import Callable
import re
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from ..brewday.brewday_audit import async_record_brewday_audit_event
from ..brewday.brewday_runtime import build_brewday_runtime_snapshot
from . import brewzilla_orchestration as _orchestration

DATA_KEY = "brewzilla_mash_in_gate"
NOTIFICATION_ID = "brewassistant_brewzilla_mash_in_ready"
PUMP_OFF_UTILIZATION = 0.0
MASH_IN_RESUME_PUMP_UTILIZATION = 50.0
MASH_IN_STARTED_MAX_HEAT_UTILIZATION = 15.0
MASH_IN_STARTED_COAST_HEAT_UTILIZATION = 10.0
MASH_IN_STARTED_FEATHER_HEAT_UTILIZATION = 5.0
UTILIZATION_TOLERANCE = 0.1
READY_TOLERANCE_C = 0.3
READY_STATE = "ready_for_mash_in"
STARTED_STATE = "mash_in_started"
_COMPLETE_STATE = "mash_in_complete"
_TERMINAL_STATES = {"idle", "inactive", "completed", "complete", "done"}
_EARLY_MASH_MAX_INDEX = 3
_ORIGINAL_BUILD: Callable[[HomeAssistant], dict[str, Any]] | None = None
_TEMP_RE = re.compile(r"(-?\d+(?:[\.,]\d+)?)\s*(?:°\s*)?c", re.I)


def _gate_store(hass: HomeAssistant) -> dict[str, Any]:
    return hass.data.setdefault("brewassistant", {}).setdefault(
        DATA_KEY,
        {
            "active_key": None,
            "state": "idle",
            "notified_at": None,
            "started_at": None,
            "confirmed_at": None,
            "completed_once": False,
            "last_target": None,
            "last_stage": None,
            "last_step": None,
            "last_phase": None,
            "last_trigger": None,
            "next_target": None,
            "next_target_source": None,
            "effective_target": None,
            "effective_target_source": None,
            "last_start_result": None,
            "last_resume_result": None,
        },
    )


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _bool_state(hass: HomeAssistant, entity_id: str) -> bool:
    state = hass.states.get(entity_id)
    return bool(state is not None and str(state.state).lower() in {"on", "true", "yes"})


def _text(snapshot: dict[str, Any], *keys: str) -> str:
    return " ".join(str(snapshot.get(key) or "") for key in keys).lower()


def _runtime_active_enough(snapshot: dict[str, Any]) -> bool:
    state = str(snapshot.get("brewday_state") or "idle").lower()
    return bool(
        state not in _TERMINAL_STATES
        and not snapshot.get("completed_runtime")
        and not snapshot.get("abort_lockout_active")
    )


def _mash_scope_active(snapshot: dict[str, Any]) -> bool:
    """Return true while the runtime still appears to be in the mash stage."""
    state = str(snapshot.get("brewday_state") or "idle").lower()
    if state in _TERMINAL_STATES or snapshot.get("completed_runtime"):
        return False

    stage_text = _text(snapshot, "runtime_stage", "stage")
    if not stage_text:
        return True
    return "mash" in stage_text or "mäsk" in stage_text


def _temperature_for_gate(snapshot: dict[str, Any]) -> float | None:
    """Return the temperature that should decide mash-in readiness.

    Mash-in is an operator action for the mash, so prefer the selected mash/BLE
    temperature role when available. The generic/current BrewZilla temperature
    is usually the internal/wort fallback and can lag the mash role in the UI.
    """
    for key in (
        "mash_temperature",
        "brewzilla_mash_temperature",
        "advice_learning_temperature",
        "current_temperature",
        "brewzilla_current_temp",
    ):
        value = _num(snapshot.get(key))
        if value is not None:
            return value
    return None


def _target_for_gate(snapshot: dict[str, Any]) -> float | None:
    for key in ("requested_target", "target_temperature", "tracker_target"):
        value = _num(snapshot.get(key))
        if value is not None:
            return value
    return None


def _parse_temperature_from_text(value: Any) -> float | None:
    text = str(value or "")
    match = _TEMP_RE.search(text)
    if not match:
        return None
    return _num(match.group(1).replace(",", "."))


def _next_temperature_target(hass: HomeAssistant) -> tuple[float | None, str | None]:
    """Return the next upcoming Brew Tracker temperature target.

    Brewfather often inserts an event step for malt additions between strike and
    the actual mash hold.  The runtime timeline lets BA skip non-temperature
    event steps and find the next ramp/mash step with a numeric value.
    """
    runtime = build_brewday_runtime_snapshot(hass)

    for key in ("next_step_target_temperature", "next_target_temperature"):
        value = _num(runtime.get(key))
        if value is not None:
            return value, key

    parsed = _parse_temperature_from_text(runtime.get("next_step"))
    if parsed is not None:
        return parsed, "next_step_text"

    timeline = runtime.get("timeline")
    if not isinstance(timeline, list):
        return None, None

    seen_active = False
    for stage in timeline:
        if not isinstance(stage, dict):
            continue
        steps = stage.get("steps")
        if not isinstance(steps, list):
            continue
        for step in steps:
            if not isinstance(step, dict):
                continue
            if step.get("active"):
                seen_active = True
                continue
            if not seen_active and not step.get("upcoming"):
                continue
            value = _num(step.get("value"))
            if value is None:
                value = _parse_temperature_from_text(step.get("name"))
            if value is None:
                continue
            kind = str(step.get("type") or "").lower()
            if kind in {"mash", "ramp", "temperature"} or "ramp" in str(step.get("name") or "").lower() or "hold" in str(step.get("name") or "").lower():
                return value, "runtime_timeline"
    return None, None


def _effective_mash_in_target(hass: HomeAssistant, snapshot: dict[str, Any]) -> tuple[float | None, str | None, float | None, str | None]:
    current_target = _target_for_gate(snapshot)
    next_target, next_source = _next_temperature_target(hass)
    if current_target is not None and next_target is not None and next_target <= current_target:
        return next_target, "next_mash_step", next_target, next_source
    return current_target, "current_step", next_target, next_source


def _early_mash_step(snapshot: dict[str, Any]) -> bool:
    for key in ("runtime_raw_step_index", "raw_step_index", "runtime_resolved_step_index", "resolved_step_index"):
        index = _num(snapshot.get(key))
        if index is not None:
            return index <= _EARLY_MASH_MAX_INDEX

    text = _text(snapshot, "runtime_next_step", "next_step", "runtime_raw_step_name", "raw_step_name")
    return any(word in text for word in ("mash-in", "mash in", "mäsk", "mäsktillsats"))


def _legacy_strategy_ready(snapshot: dict[str, Any]) -> bool:
    return bool(
        snapshot.get("mash_in_confirmation_recommended")
        and snapshot.get("mash_in_heat_strategy_active")
        and snapshot.get("mash_in_heat_strategy_phase") in {"mash_in_ready", "overshoot"}
        and _target_for_gate(snapshot) is not None
    )


def _brewfather_advice_ready(snapshot: dict[str, Any]) -> bool:
    if not _runtime_active_enough(snapshot):
        return False

    stage_text = _text(snapshot, "runtime_stage", "stage")
    step_text = _text(snapshot, "runtime_step", "step", "runtime_raw_step_name", "raw_step_name")
    if "mash" not in stage_text and "mäsk" not in stage_text:
        return False
    if not any(word in step_text for word in ("ramp", "hold", "mash", "mäsk")):
        return False
    if not _early_mash_step(snapshot):
        return False

    target = _target_for_gate(snapshot)
    temperature = _temperature_for_gate(snapshot)
    if target is None or temperature is None:
        return False
    return temperature >= target - READY_TOLERANCE_C


def _ready_for_mash_in(snapshot: dict[str, Any]) -> bool:
    return _legacy_strategy_ready(snapshot) or _brewfather_advice_ready(snapshot)


def _trigger_phase(snapshot: dict[str, Any]) -> str:
    if _legacy_strategy_ready(snapshot):
        return str(snapshot.get("mash_in_heat_strategy_phase") or "legacy_mash_in_ready")
    return "brewfather_advice_target_ready"


def _gate_key(snapshot: dict[str, Any]) -> str:
    return "|".join(
        str(part or "")
        for part in (
            snapshot.get("runtime_source") or snapshot.get("source"),
            snapshot.get("runtime_stage") or snapshot.get("stage"),
            _target_for_gate(snapshot),
            "mash_in",
        )
    )


def _update_gate_context(
    store: dict[str, Any],
    snapshot: dict[str, Any],
    *,
    trigger: str | None = None,
) -> None:
    target = _target_for_gate(snapshot)
    stage = snapshot.get("runtime_stage") or snapshot.get("stage")
    step = snapshot.get("runtime_step") or snapshot.get("step")

    if target is not None:
        store["last_target"] = target
    if stage:
        store["last_stage"] = stage
    if step:
        store["last_step"] = step

    if trigger:
        store["last_phase"] = trigger
        store["last_trigger"] = trigger
    elif not store.get("last_trigger"):
        phase = _trigger_phase(snapshot)
        store["last_phase"] = phase
        store["last_trigger"] = phase


def _ensure_gate_for_snapshot(hass: HomeAssistant, snapshot: dict[str, Any]) -> dict[str, Any]:
    store = _gate_store(hass)
    key = _gate_key(snapshot)
    if store.get("active_key") != key:
        store.update(
            {
                "active_key": key,
                "state": READY_STATE,
                "notified_at": None,
                "started_at": None,
                "confirmed_at": None,
                "completed_once": False,
                "next_target": None,
                "next_target_source": None,
                "effective_target": None,
                "effective_target_source": None,
                "last_start_result": None,
                "last_resume_result": None,
            }
        )

    _update_gate_context(store, snapshot, trigger=_trigger_phase(snapshot))
    return store


def _reset_if_out_of_scope(hass: HomeAssistant, snapshot: dict[str, Any]) -> bool:
    store = _gate_store(hass)
    if store.get("state") == "idle" and not store.get("completed_once"):
        return False
    if not _mash_scope_active(snapshot):
        store.update(
            {
                "state": "idle",
                "active_key": None,
                "completed_once": False,
                "notified_at": None,
                "started_at": None,
                "confirmed_at": None,
                "next_target": None,
                "next_target_source": None,
                "effective_target": None,
                "effective_target_source": None,
                "last_start_result": None,
                "last_resume_result": None,
            }
        )
        return True
    return False


async def _create_ready_notification(hass: HomeAssistant, snapshot: dict[str, Any]) -> None:
    temperature = _temperature_for_gate(snapshot)
    target = _target_for_gate(snapshot)
    effective, effective_source, next_target, next_source = _effective_mash_in_target(hass, snapshot)
    await hass.services.async_call(
        "persistent_notification",
        "create",
        {
            "notification_id": NOTIFICATION_ID,
            "title": "🍺 BrewAssistant: dags för mash-in",
            "message": (
                "Mash-in target är nådd. Pumpen hålls pausad.\n\n"
                f"Mäsktemperatur: {temperature} °C  \n"
                f"Strike/current target: {target} °C  \n"
                f"Nästa/effective target: {effective} °C ({effective_source}, next={next_target}, source={next_source})\n\n"
                "Tryck först **BrewAssistant Mash-In Started** när du börjar hälla i malten. "
                "När malten är inrörd och bädden är redo: tryck **BrewAssistant Mash-In Complete**."
            ),
        },
        blocking=False,
    )


def _schedule_notification_if_needed(hass: HomeAssistant, snapshot: dict[str, Any], store: dict[str, Any]) -> None:
    if store.get("notified_at"):
        return
    store["notified_at"] = dt_util.utcnow().isoformat()
    hass.async_create_task(_create_ready_notification(hass, snapshot))


def _can_apply_gate(snapshot: dict[str, Any], *, action_needed: bool) -> bool:
    return bool(
        action_needed
        and snapshot.get("connected", True)
        and not snapshot.get("abort_lockout_active")
        and _runtime_active_enough(snapshot)
        and _target_for_gate(snapshot) is not None
    )


def _gate_fields(store: dict[str, Any], snapshot: dict[str, Any], *, pending: bool) -> dict[str, Any]:
    state = store.get("state")
    return {
        "mash_in_gate_state": state,
        "mash_in_gate_pending": pending,
        "mash_in_gate_latched": state in {READY_STATE, STARTED_STATE},
        "mash_in_gate_active_key": store.get("active_key"),
        "mash_in_gate_trigger": store.get("last_trigger"),
        "mash_in_gate_notification_id": NOTIFICATION_ID,
        "mash_in_gate_notified_at": store.get("notified_at"),
        "mash_in_gate_started_at": store.get("started_at"),
        "mash_in_gate_confirmed_at": store.get("confirmed_at"),
        "mash_in_gate_last_target": store.get("last_target"),
        "mash_in_gate_last_stage": store.get("last_stage"),
        "mash_in_gate_last_step": store.get("last_step"),
        "mash_in_gate_current_target": _target_for_gate(snapshot),
        "mash_in_gate_current_temperature": _temperature_for_gate(snapshot),
        "mash_in_next_target": store.get("next_target"),
        "mash_in_next_target_source": store.get("next_target_source"),
        "mash_in_effective_target": store.get("effective_target"),
        "mash_in_effective_target_source": store.get("effective_target_source"),
        "mash_in_started_visible": state == READY_STATE,
        "mash_in_complete_visible": state == STARTED_STATE,
        "mash_in_started_active": state == STARTED_STATE,
        "mash_in_start_result": store.get("last_start_result"),
        "mash_in_resume_result": store.get("last_resume_result"),
    }


def _force_pump_pause(snapshot: dict[str, Any], store: dict[str, Any]) -> dict[str, Any]:
    current_pump_utilization = snapshot.get("pump_utilization")
    pump_utilization_action_needed = current_pump_utilization is None or abs(float(current_pump_utilization)) > UTILIZATION_TOLERANCE
    pump_on = bool(snapshot.get("pump_on"))
    action_needed = bool(pump_on or pump_utilization_action_needed)
    can_apply_gate = _can_apply_gate(snapshot, action_needed=action_needed)
    reason = str(snapshot.get("control_reason") or "Direct production flow active")
    return {
        **snapshot,
        "pump_recommended": False,
        "desired_pump_on": False,
        "desired_pump_utilization": PUMP_OFF_UTILIZATION,
        "pump_action_needed": False,
        "pump_stop_needed": pump_on,
        "pump_utilization_action_needed": pump_utilization_action_needed,
        "can_apply_target": can_apply_gate,
        "orchestration_mode": "direct-control" if can_apply_gate else snapshot.get("orchestration_mode"),
        **_gate_fields(store, snapshot, pending=True),
        "control_reason": f"{reason}; mash-in ready gate active, pump OFF until Mash-In Started is pressed.",
    }


def _mash_in_started_hold_snapshot(hass: HomeAssistant, snapshot: dict[str, Any], store: dict[str, Any]) -> dict[str, Any]:
    if store.get("effective_target") is None:
        effective, effective_source, next_target, next_source = _effective_mash_in_target(hass, snapshot)
        store["effective_target"] = effective
        store["effective_target_source"] = effective_source
        store["next_target"] = next_target
        store["next_target_source"] = next_source

    effective_target = _num(store.get("effective_target"))
    current = _temperature_for_gate(snapshot)
    applied = _num(snapshot.get("applied_target"))
    heat_utilization = _num(snapshot.get("heat_utilization"))
    pump_utilization = _num(snapshot.get("pump_utilization"))
    heater_on = bool(snapshot.get("heater_on"))
    pump_on = bool(snapshot.get("pump_on"))

    if effective_target is None or current is None:
        desired_heat = 0.0
        desired_heater_on = False
        delta_to_effective = None
        phase = "unknown_target"
    else:
        delta_to_effective = round(effective_target - current, 2)
        if delta_to_effective > 1.0:
            desired_heat = MASH_IN_STARTED_MAX_HEAT_UTILIZATION
            desired_heater_on = True
            phase = "anti_drop_recovery"
        elif delta_to_effective > 0.2:
            desired_heat = MASH_IN_STARTED_COAST_HEAT_UTILIZATION
            desired_heater_on = True
            phase = "anti_drop_coast"
        elif delta_to_effective >= -0.3:
            desired_heat = MASH_IN_STARTED_FEATHER_HEAT_UTILIZATION
            desired_heater_on = True
            phase = "anti_drop_feather"
        else:
            desired_heat = 0.0
            desired_heater_on = False
            phase = "above_effective_target"

    target_delta = None
    target_sync_needed = False
    if effective_target is not None and applied is not None:
        target_delta = round(effective_target - applied, 2)
        target_sync_needed = abs(target_delta) > _orchestration.TARGET_SYNC_TOLERANCE

    heat_action_needed = _orchestration._utilization_action_needed(heat_utilization, desired_heat)
    pump_utilization_action_needed = _orchestration._utilization_action_needed(pump_utilization, PUMP_OFF_UTILIZATION)
    pump_stop_needed = pump_on
    heater_action_needed = bool(desired_heater_on and not heater_on)
    heater_stop_needed = bool(desired_heater_on is False and heater_on)
    action_needed = bool(
        target_sync_needed
        or heat_action_needed
        or pump_utilization_action_needed
        or pump_stop_needed
        or heater_action_needed
        or heater_stop_needed
    )
    can_apply = bool(
        snapshot.get("connected", True)
        and action_needed
        and not snapshot.get("abort_lockout_active")
        and _runtime_active_enough(snapshot)
        and effective_target is not None
    )

    reason = str(snapshot.get("control_reason") or "Direct production flow active")
    return {
        **snapshot,
        "requested_target": effective_target,
        "requested_target_source": "mash_in_started_effective_target",
        "target_delta": target_delta,
        "target_sync_needed": target_sync_needed,
        "paused_target_rewind_blocked": False,
        "heating_needed": bool(desired_heater_on),
        "desired_heat_utilization": desired_heat,
        "desired_heater_on": desired_heater_on,
        "heat_utilization_action_needed": heat_action_needed,
        "heater_action_needed": heater_action_needed,
        "heater_stop_needed": heater_stop_needed,
        "pump_recommended": False,
        "desired_pump_on": False,
        "desired_pump_utilization": PUMP_OFF_UTILIZATION,
        "pump_action_needed": False,
        "pump_stop_needed": pump_stop_needed,
        "pump_utilization_action_needed": pump_utilization_action_needed,
        "mash_in_started_hold_active": True,
        "mash_in_started_hold_phase": phase,
        "mash_in_started_delta_to_effective_target": delta_to_effective,
        "can_apply_target": can_apply,
        "orchestration_mode": "direct-control" if can_apply else "monitor",
        **_gate_fields(store, snapshot, pending=False),
        "control_reason": (
            f"{reason}; mash-in has started. Strike target released; effective mash target "
            f"{effective_target}°C ({store.get('effective_target_source')}). Pump remains OFF; "
            f"anti-drop heat {desired_heat}% ({phase}) until Mash-In Complete is pressed."
        ),
    }


def _idle_snapshot(snapshot: dict[str, Any], store: dict[str, Any]) -> dict[str, Any]:
    return {
        **snapshot,
        **_gate_fields(store, snapshot, pending=False),
    }


def _completed_snapshot(snapshot: dict[str, Any], store: dict[str, Any]) -> dict[str, Any]:
    return {
        **snapshot,
        **_gate_fields(store, snapshot, pending=False),
        "mash_in_gate_state": _COMPLETE_STATE,
        "mash_in_gate_pending": False,
        "mash_in_gate_latched": False,
        "mash_in_started_visible": False,
        "mash_in_complete_visible": False,
        "mash_in_gate_confirmed_at": store.get("confirmed_at"),
        "mash_in_resume_result": store.get("last_resume_result"),
    }


def _augment_snapshot(hass: HomeAssistant, snapshot: dict[str, Any]) -> dict[str, Any]:
    store = _gate_store(hass)

    if store.get("state") == READY_STATE:
        if _reset_if_out_of_scope(hass, snapshot):
            return _idle_snapshot(snapshot, store)
        _update_gate_context(store, snapshot, trigger=store.get("last_trigger") or "ready_for_mash_in")
        _schedule_notification_if_needed(hass, snapshot, store)
        return _force_pump_pause(snapshot, store)

    if store.get("state") == STARTED_STATE:
        if _reset_if_out_of_scope(hass, snapshot):
            return _idle_snapshot(snapshot, store)
        _update_gate_context(store, snapshot, trigger=store.get("last_trigger") or STARTED_STATE)
        return _mash_in_started_hold_snapshot(hass, snapshot, store)

    if store.get("completed_once"):
        if _reset_if_out_of_scope(hass, snapshot):
            return _idle_snapshot(snapshot, store)
        return _completed_snapshot(snapshot, store)

    if not _ready_for_mash_in(snapshot):
        _reset_if_out_of_scope(hass, snapshot)
        return _idle_snapshot(snapshot, store)

    store = _ensure_gate_for_snapshot(hass, snapshot)
    if store.get("state") == _COMPLETE_STATE:
        store["completed_once"] = True
        return _completed_snapshot(snapshot, store)

    _schedule_notification_if_needed(hass, snapshot, store)
    return _force_pump_pause(snapshot, store)


def _hard_action_block(snapshot: dict[str, Any]) -> str | None:
    if snapshot.get("abort_lockout_active"):
        return "abort_lockout_active"
    if snapshot.get("completed_runtime"):
        return "completed_runtime"
    return None


async def _start_mash_circulation(
    hass: HomeAssistant,
    snapshot: dict[str, Any],
    *,
    action_name: str,
) -> dict[str, Any]:
    """Set mash pump utilization and start the pump as an explicit operator action."""
    actions = [action_name]
    blocked_reason = _hard_action_block(snapshot)
    pump_utilization_changed = False
    pump_started = False
    pump_utilization_entity_present = hass.states.get(_orchestration.BREWZILLA_PUMP_UTILIZATION) is not None
    pump_switch_entity_present = hass.states.get(_orchestration.BREWZILLA_PUMP_SWITCH) is not None

    if blocked_reason is None:
        if pump_utilization_entity_present:
            if await _orchestration._set_number(
                hass,
                _orchestration.BREWZILLA_PUMP_UTILIZATION,
                MASH_IN_RESUME_PUMP_UTILIZATION,
            ):
                pump_utilization_changed = True
                actions.append(f"set_pump_utilization:{MASH_IN_RESUME_PUMP_UTILIZATION}")
            else:
                actions.append("set_pump_utilization_failed_or_unchanged")
        else:
            actions.append("pump_utilization_entity_missing")

        if pump_switch_entity_present:
            if not _bool_state(hass, _orchestration.BREWZILLA_PUMP_SWITCH):
                await _orchestration._call_switch(hass, "on", _orchestration.BREWZILLA_PUMP_SWITCH)
                pump_started = True
                actions.append("pump_on")
            else:
                actions.append("pump_already_on")
        else:
            actions.append("pump_switch_entity_missing")

    applied = bool(blocked_reason is None and (pump_utilization_entity_present or pump_switch_entity_present))
    result = {
        **snapshot,
        "source": "brewzilla_mash_in_gate",
        "applied": applied,
        "apply_result": "mash_circulation_started" if applied else f"mash_circulation_blocked:{blocked_reason}",
        "actions": actions,
        "target_changed": False,
        "heater_started": False,
        "pump_started": pump_started,
        "pump_utilization_changed": pump_utilization_changed,
        "mash_in_gate_state": _COMPLETE_STATE,
        "mash_in_gate_pending": False,
        "mash_in_gate_latched": False,
        "mash_in_gate_confirmed": action_name == "mash_in_complete",
        "mash_in_gate_confirmed_at": dt_util.utcnow().isoformat() if action_name == "mash_in_complete" else snapshot.get("mash_in_gate_confirmed_at"),
        "mash_in_resume_allowed": blocked_reason is None,
        "desired_pump_on": True if blocked_reason is None else None,
        "desired_pump_utilization": MASH_IN_RESUME_PUMP_UTILIZATION if blocked_reason is None else None,
        "pump_recommended": bool(blocked_reason is None),
        "pump_action_needed": False,
        "pump_stop_needed": False,
        "mash_in_started_visible": False,
        "mash_in_complete_visible": False,
        "control_reason": (
            "Operator action: mash circulation requested; pump utilization set and pump start sent."
            if blocked_reason is None
            else f"Operator action blocked: {blocked_reason}."
        ),
        "executed_at": dt_util.utcnow().isoformat(),
    }
    hass.data.setdefault("brewassistant", {})["brewzilla_last_apply_result"] = result
    return result


async def async_mark_mash_in_started(hass: HomeAssistant) -> dict[str, Any]:
    """Mark that malt addition has started, release strike target and keep pump paused."""
    snapshot = _orchestration.build_orchestration_snapshot(hass)
    store = _gate_store(hass)
    effective, effective_source, next_target, next_source = _effective_mash_in_target(hass, snapshot)
    store.update(
        {
            "state": STARTED_STATE,
            "started_at": dt_util.utcnow().isoformat(),
            "completed_once": False,
            "effective_target": effective,
            "effective_target_source": effective_source,
            "next_target": next_target,
            "next_target_source": next_source,
            "last_start_result": None,
        }
    )
    _update_gate_context(store, snapshot, trigger=STARTED_STATE)

    apply_result = await _orchestration.async_apply_brewzilla_target_if_allowed(hass)
    store["last_start_result"] = {
        "apply_result": apply_result.get("apply_result"),
        "actions": apply_result.get("actions"),
        "target_changed": apply_result.get("target_changed"),
        "effective_target": effective,
        "effective_target_source": effective_source,
        "next_target": next_target,
        "next_target_source": next_source,
        "executed_at": apply_result.get("executed_at"),
    }
    await async_record_brewday_audit_event(
        hass,
        "mash_in_started",
        brewzilla_result=apply_result,
        always_record=True,
    )
    return build_mash_in_gate_snapshot(hass)


async def async_start_mash_circulation(hass: HomeAssistant) -> dict[str, Any]:
    """Explicitly start mash circulation: pump utilization 50%, pump ON."""
    snapshot = _orchestration.build_orchestration_snapshot(hass)
    result = await _start_mash_circulation(hass, snapshot, action_name="start_mash_circulation")
    await async_record_brewday_audit_event(
        hass,
        "mash_circulation_started",
        brewzilla_result=result,
        always_record=True,
    )
    return result


async def async_confirm_mash_in_complete(hass: HomeAssistant) -> dict[str, Any]:
    """Mark the current mash-in gate as complete and start mash circulation."""
    store = _gate_store(hass)
    store["state"] = _COMPLETE_STATE
    store["completed_once"] = True
    store["confirmed_at"] = dt_util.utcnow().isoformat()

    await hass.services.async_call(
        "persistent_notification",
        "dismiss",
        {"notification_id": NOTIFICATION_ID},
        blocking=False,
    )

    snapshot = _orchestration.build_orchestration_snapshot(hass)
    resume_result = await _start_mash_circulation(hass, snapshot, action_name="mash_in_complete")
    store["last_resume_result"] = {
        "apply_result": resume_result.get("apply_result"),
        "actions": resume_result.get("actions"),
        "pump_started": resume_result.get("pump_started"),
        "pump_utilization_changed": resume_result.get("pump_utilization_changed"),
        "resume_allowed": resume_result.get("mash_in_resume_allowed"),
        "executed_at": resume_result.get("executed_at"),
    }
    await async_record_brewday_audit_event(
        hass,
        "mash_in_confirmed",
        brewzilla_result=resume_result,
        always_record=True,
    )
    return build_mash_in_gate_snapshot(hass)


def build_mash_in_gate_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    store = _gate_store(hass)
    return {
        "source": "brewzilla_mash_in_gate",
        "state": store.get("state"),
        "pending": store.get("state") == READY_STATE,
        "started": store.get("state") == STARTED_STATE,
        "completed_once": bool(store.get("completed_once")),
        "active_key": store.get("active_key"),
        "notified_at": store.get("notified_at"),
        "started_at": store.get("started_at"),
        "confirmed_at": store.get("confirmed_at"),
        "last_target": store.get("last_target"),
        "last_stage": store.get("last_stage"),
        "last_step": store.get("last_step"),
        "last_phase": store.get("last_phase"),
        "last_trigger": store.get("last_trigger"),
        "next_target": store.get("next_target"),
        "next_target_source": store.get("next_target_source"),
        "effective_target": store.get("effective_target"),
        "effective_target_source": store.get("effective_target_source"),
        "mash_in_started_visible": store.get("state") == READY_STATE,
        "mash_in_complete_visible": store.get("state") == STARTED_STATE,
        "last_start_result": store.get("last_start_result"),
        "last_resume_result": store.get("last_resume_result"),
        "notification_id": NOTIFICATION_ID,
    }


def install_mash_in_gate() -> None:
    """Install mash-in confirmation gate around orchestration snapshots."""
    global _ORIGINAL_BUILD
    if _ORIGINAL_BUILD is not None:
        return

    _ORIGINAL_BUILD = _orchestration.build_orchestration_snapshot

    def build_orchestration_snapshot(hass: HomeAssistant) -> dict[str, Any]:
        snapshot = _ORIGINAL_BUILD(hass)
        return _augment_snapshot(hass, snapshot)

    _orchestration.build_orchestration_snapshot = build_orchestration_snapshot
