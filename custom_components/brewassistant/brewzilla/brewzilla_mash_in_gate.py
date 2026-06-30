"""Mash-in confirmation gate for BrewZilla orchestration."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import brewzilla_orchestration as _orchestration

DATA_KEY = "brewzilla_mash_in_gate"
NOTIFICATION_ID = "brewassistant_brewzilla_mash_in_ready"
PUMP_OFF_UTILIZATION = 0.0
UTILIZATION_TOLERANCE = 0.1
READY_TOLERANCE_C = 0.3
AWAITING_STATE = "awaiting_mash_in_complete"
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
            "last_target": None,
            "last_stage": None,
            "last_step": None,
            "last_phase": None,
            "last_trigger": None,
        },
    )


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _text(snapshot: dict[str, Any], *keys: str) -> str:
    return " ".join(str(snapshot.get(key) or "") for key in keys).lower()


def _runtime_active_enough(snapshot: dict[str, Any]) -> bool:
    state = str(snapshot.get("brewday_state") or "idle").lower()
    return state not in {"idle", "inactive", "completed", "complete", "done"} and not snapshot.get("completed_runtime")


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
    if store.get("state") == "idle":
        return
    if snapshot.get("brewday_state") in {"idle", "completed"} or snapshot.get("completed_runtime"):
        store.update({"state": "idle", "active_key": None})


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


def _augment_snapshot(hass: HomeAssistant, snapshot: dict[str, Any]) -> dict[str, Any]:
    if not _ready_for_mash_in(snapshot):
        _reset_if_out_of_scope(hass, snapshot)
        store = _gate_store(hass)
        return {
            **snapshot,
            "mash_in_gate_state": store.get("state"),
            "mash_in_gate_pending": False,
            "mash_in_gate_trigger": store.get("last_trigger"),
            "mash_in_gate_notification_id": NOTIFICATION_ID,
        }

    store = _ensure_gate_for_snapshot(hass, snapshot)
    if store.get("state") == "mash_in_complete":
        return {
            **snapshot,
            "mash_in_gate_state": "mash_in_complete",
            "mash_in_gate_pending": False,
            "mash_in_gate_trigger": store.get("last_trigger"),
            "mash_in_gate_notification_id": NOTIFICATION_ID,
        }

    _schedule_notification_if_needed(hass, snapshot, store)
    return _force_pump_pause(snapshot)


async def async_confirm_mash_in_complete(hass: HomeAssistant) -> dict[str, Any]:
    """Mark the current mash-in gate as complete and allow pump control again."""
    store = _gate_store(hass)
    store["state"] = "mash_in_complete"
    store["confirmed_at"] = dt_util.utcnow().isoformat()
    await hass.services.async_call(
        "persistent_notification",
        "dismiss",
        {"notification_id": NOTIFICATION_ID},
        blocking=False,
    )
    return build_mash_in_gate_snapshot(hass)


def build_mash_in_gate_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    store = _gate_store(hass)
    return {
        "source": "brewzilla_mash_in_gate",
        "state": store.get("state"),
        "pending": store.get("state") == AWAITING_STATE,
        "active_key": store.get("active_key"),
        "notified_at": store.get("notified_at"),
        "confirmed_at": store.get("confirmed_at"),
        "last_target": store.get("last_target"),
        "last_stage": store.get("last_stage"),
        "last_step": store.get("last_step"),
        "last_phase": store.get("last_phase"),
        "last_trigger": store.get("last_trigger"),
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
