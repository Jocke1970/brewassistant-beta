"""Mash-in confirmation gate for BrewZilla orchestration."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from ..brewday.brewday_audit import async_record_brewday_audit_event
from . import brewzilla_orchestration as _orchestration

DATA_KEY = "brewzilla_mash_in_gate"
NOTIFICATION_ID = "brewassistant_brewzilla_mash_in_ready"
PUMP_OFF_UTILIZATION = 0.0
MASH_IN_RESUME_PUMP_UTILIZATION = 50.0
UTILIZATION_TOLERANCE = 0.1
READY_TOLERANCE_C = 0.3
AWAITING_STATE = "awaiting_mash_in_complete"
_COMPLETE_STATE = "mash_in_complete"
_READY_PHASES = {"mash_in_ready", "overshoot"}
_EARLY_MASH_MAX_INDEX = 3
_ORIGINAL_BUILD: Callable[[HomeAssistant], dict[str, Any]] | None = None


def _gate_store(hass: HomeAssistant) -> dict[str, Any]:
    return hass.data.setdefault("brewassistant", {}).setdefault(
        DATA_KEY,
        {
            "active_key": None,
            "state": "idle",
            "notified_at": None,
            "confirmed_at": None,
            "completed_once": False,
            "last_target": None,
            "last_stage": None,
            "last_step": None,
            "last_phase": None,
            "last_trigger": None,
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
        state not in {"idle", "inactive", "completed", "complete", "done"}
        and not snapshot.get("completed_runtime")
        and not snapshot.get("abort_lockout_active")
    )


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
        and snapshot.get("mash_in_heat_strategy_phase") in _READY_PHASES
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


def _ensure_gate_for_snapshot(hass: HomeAssistant, snapshot: dict[str, Any]) -> dict[str, Any]:
    store = _gate_store(hass)
    key = _gate_key(snapshot)
    if store.get("active_key") != key:
        store.update(
            {
                "active_key": key,
                "state": AWAITING_STATE,
                "notified_at": None,
                "confirmed_at": None,
                "last_resume_result": None,
            }
        )

    store.update(
        {
            "last_target": _target_for_gate(snapshot),
            "last_stage": snapshot.get("runtime_stage") or snapshot.get("stage"),
            "last_step": snapshot.get("runtime_step") or snapshot.get("step"),
            "last_phase": _trigger_phase(snapshot),
            "last_trigger": _trigger_phase(snapshot),
        }
    )
    return store


def _reset_if_out_of_scope(hass: HomeAssistant, snapshot: dict[str, Any]) -> None:
    store = _gate_store(hass)
    if store.get("state") == "idle" and not store.get("completed_once"):
        return
    if snapshot.get("brewday_state") in {"idle", "completed"} or snapshot.get("completed_runtime"):
        store.update({"state": "idle", "active_key": None, "completed_once": False})


async def _create_ready_notification(hass: HomeAssistant, snapshot: dict[str, Any]) -> None:
    temperature = _temperature_for_gate(snapshot)
    target = _target_for_gate(snapshot)
    await hass.services.async_call(
        "persistent_notification",
        "create",
        {
            "notification_id": NOTIFICATION_ID,
            "title": "🍺 BrewAssistant: dags för mash-in",
            "message": (
                "Mash-in target är nådd. Pumpen hålls pausad medan du mäskar in.\n\n"
                f"Mäsktemperatur: {temperature} °C  \n"
                f"Target: {target} °C  \n\n"
                "När mash-in är klar: tryck på **BrewAssistant Mash-In Complete**."
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


def _force_pump_pause(snapshot: dict[str, Any]) -> dict[str, Any]:
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
        "mash_in_gate_state": AWAITING_STATE,
        "mash_in_gate_pending": True,
        "mash_in_gate_trigger": _trigger_phase(snapshot),
        "mash_in_gate_notification_id": NOTIFICATION_ID,
        "control_reason": f"{reason}; mash-in confirmation gate active, pump OFF until mash-in complete is confirmed.",
    }


def _completed_snapshot(snapshot: dict[str, Any], store: dict[str, Any]) -> dict[str, Any]:
    return {
        **snapshot,
        "mash_in_gate_state": _COMPLETE_STATE,
        "mash_in_gate_pending": False,
        "mash_in_gate_trigger": store.get("last_trigger"),
        "mash_in_gate_notification_id": NOTIFICATION_ID,
        "mash_in_gate_confirmed_at": store.get("confirmed_at"),
        "mash_in_resume_result": store.get("last_resume_result"),
    }


def _augment_snapshot(hass: HomeAssistant, snapshot: dict[str, Any]) -> dict[str, Any]:
    store = _gate_store(hass)
    if store.get("completed_once"):
        _reset_if_out_of_scope(hass, snapshot)
        return _completed_snapshot(snapshot, store)

    if not _ready_for_mash_in(snapshot):
        _reset_if_out_of_scope(hass, snapshot)
        return {
            **snapshot,
            "mash_in_gate_state": store.get("state"),
            "mash_in_gate_pending": False,
            "mash_in_gate_trigger": store.get("last_trigger"),
            "mash_in_gate_notification_id": NOTIFICATION_ID,
        }

    store = _ensure_gate_for_snapshot(hass, snapshot)
    if store.get("state") == _COMPLETE_STATE:
        store["completed_once"] = True
        return _completed_snapshot(snapshot, store)

    _schedule_notification_if_needed(hass, snapshot, store)
    return _force_pump_pause(snapshot)


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
        "mash_in_gate_confirmed": action_name == "mash_in_complete",
        "mash_in_gate_confirmed_at": dt_util.utcnow().isoformat() if action_name == "mash_in_complete" else snapshot.get("mash_in_gate_confirmed_at"),
        "mash_in_resume_allowed": blocked_reason is None,
        "desired_pump_on": True if blocked_reason is None else None,
        "desired_pump_utilization": MASH_IN_RESUME_PUMP_UTILIZATION if blocked_reason is None else None,
        "pump_recommended": bool(blocked_reason is None),
        "pump_action_needed": False,
        "pump_stop_needed": False,
        "control_reason": (
            "Operator action: mash circulation requested; pump utilization set and pump start sent."
            if blocked_reason is None
            else f"Operator action blocked: {blocked_reason}."
        ),
        "executed_at": dt_util.utcnow().isoformat(),
    }
    hass.data.setdefault("brewassistant", {})["brewzilla_last_apply_result"] = result
    return result


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
        "pending": store.get("state") == AWAITING_STATE,
        "completed_once": bool(store.get("completed_once")),
        "active_key": store.get("active_key"),
        "notified_at": store.get("notified_at"),
        "confirmed_at": store.get("confirmed_at"),
        "last_target": store.get("last_target"),
        "last_stage": store.get("last_stage"),
        "last_step": store.get("last_step"),
        "last_phase": store.get("last_phase"),
        "last_trigger": store.get("last_trigger"),
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
