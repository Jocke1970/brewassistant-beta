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
_READY_PHASES = {"mash_in_ready", "overshoot"}
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
        },
    )


def _gate_key(snapshot: dict[str, Any]) -> str:
    return "|".join(
        str(part or "")
        for part in (
            snapshot.get("runtime_source"),
            snapshot.get("runtime_raw_step_index"),
            snapshot.get("runtime_stage"),
            snapshot.get("runtime_step"),
            snapshot.get("requested_target"),
        )
    )


def _ready_for_mash_in(snapshot: dict[str, Any]) -> bool:
    return bool(
        snapshot.get("mash_in_confirmation_recommended")
        and snapshot.get("mash_in_heat_strategy_active")
        and snapshot.get("mash_in_heat_strategy_phase") in _READY_PHASES
        and snapshot.get("requested_target") is not None
    )


def _ensure_gate_for_snapshot(hass: HomeAssistant, snapshot: dict[str, Any]) -> dict[str, Any]:
    store = _gate_store(hass)
    key = _gate_key(snapshot)
    if store.get("active_key") != key:
        store.update(
            {
                "active_key": key,
                "state": "awaiting_mash_in",
                "notified_at": None,
                "confirmed_at": None,
            }
        )

    store.update(
        {
            "last_target": snapshot.get("requested_target"),
            "last_stage": snapshot.get("runtime_stage"),
            "last_step": snapshot.get("runtime_step"),
            "last_phase": snapshot.get("mash_in_heat_strategy_phase"),
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
    await hass.services.async_call(
        "persistent_notification",
        "create",
        {
            "notification_id": NOTIFICATION_ID,
            "title": "🍺 BrewAssistant: dags för mash-in",
            "message": (
                "Mash-in target är nådd. Pumpen hålls pausad medan du mäska in.\n\n"
                f"Mäsktemperatur: {snapshot.get('current_temperature')} °C  \n"
                f"Target: {snapshot.get('requested_target')} °C  \n\n"
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


def _force_pump_pause(snapshot: dict[str, Any]) -> dict[str, Any]:
    current_pump_utilization = snapshot.get("pump_utilization")
    pump_utilization_action_needed = current_pump_utilization is None or abs(float(current_pump_utilization)) > UTILIZATION_TOLERANCE
    pump_on = bool(snapshot.get("pump_on"))
    reason = str(snapshot.get("control_reason") or "Direct production flow active")
    return {
        **snapshot,
        "pump_recommended": False,
        "desired_pump_on": False,
        "desired_pump_utilization": PUMP_OFF_UTILIZATION,
        "pump_action_needed": False,
        "pump_stop_needed": pump_on,
        "pump_utilization_action_needed": pump_utilization_action_needed,
        "mash_in_gate_state": "awaiting_mash_in_complete",
        "mash_in_gate_pending": True,
        "mash_in_gate_notification_id": NOTIFICATION_ID,
        "control_reason": f"{reason}; mash-in confirmation gate active, pump OFF until operator confirms mash-in complete.",
    }


def _augment_snapshot(hass: HomeAssistant, snapshot: dict[str, Any]) -> dict[str, Any]:
    if not _ready_for_mash_in(snapshot):
        _reset_if_out_of_scope(hass, snapshot)
        store = _gate_store(hass)
        return {
            **snapshot,
            "mash_in_gate_state": store.get("state"),
            "mash_in_gate_pending": False,
            "mash_in_gate_notification_id": NOTIFICATION_ID,
        }

    store = _ensure_gate_for_snapshot(hass, snapshot)
    if store.get("state") == "mash_in_complete":
        return {
            **snapshot,
            "mash_in_gate_state": "mash_in_complete",
            "mash_in_gate_pending": False,
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
        "pending": store.get("state") == "awaiting_mash_in",
        "active_key": store.get("active_key"),
        "notified_at": store.get("notified_at"),
        "confirmed_at": store.get("confirmed_at"),
        "last_target": store.get("last_target"),
        "last_stage": store.get("last_stage"),
        "last_step": store.get("last_step"),
        "last_phase": store.get("last_phase"),
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
