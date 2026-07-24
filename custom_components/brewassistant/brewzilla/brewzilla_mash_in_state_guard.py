"""Guard BrewZilla mash-in service transitions.

The Mash-In Started action is a one-way operator gate: ready -> started ->
complete.  Once BA has reached Mash-In Complete, a stale visible button or late
service call must not move the state machine back to mash_in_started.
"""

from __future__ import annotations

from typing import Any, Callable

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from ..brewday.brewday_audit import async_record_brewday_audit_event
from . import brewzilla_mash_in_gate as gate

_INSTALLED = False
_ORIGINAL_MARK_MASH_IN_STARTED: Callable[[HomeAssistant], Any] | None = None


def _ignored_result(hass: HomeAssistant, snapshot: dict[str, Any], *, reason: str) -> dict[str, Any]:
    state = str(snapshot.get("state") or "idle")
    action = f"mash_in_started_ignored:{reason}"
    result = {
        "source": "brewzilla_mash_in_state_guard",
        "applied": False,
        "apply_result": action,
        "actions": [action],
        "mash_in_gate_state": state,
        "mash_in_gate_pending": bool(snapshot.get("pending")),
        "mash_in_gate_latched": state in {gate.READY_STATE, gate.STARTED_STATE},
        "mash_in_gate_active_key": snapshot.get("active_key"),
        "mash_in_gate_trigger": snapshot.get("last_trigger"),
        "mash_in_gate_notification_id": snapshot.get("notification_id"),
        "mash_in_gate_notified_at": snapshot.get("notified_at"),
        "mash_in_gate_confirmed_at": snapshot.get("confirmed_at"),
        "mash_in_gate_last_target": snapshot.get("last_target"),
        "mash_in_gate_last_stage": snapshot.get("last_stage"),
        "mash_in_gate_last_step": snapshot.get("last_step"),
        "mash_in_started_visible": state == gate.READY_STATE,
        "mash_in_complete_visible": state == gate.STARTED_STATE,
        "mash_in_start_result": snapshot.get("last_start_result"),
        "mash_in_resume_result": snapshot.get("last_resume_result"),
        "control_reason": (
            "Mash-In Started ignored because the mash-in state machine only allows "
            f"ready_for_mash_in -> mash_in_started. Current state is {state} ({reason})."
        ),
        "executed_at": dt_util.utcnow().isoformat(),
    }
    hass.data.setdefault("brewassistant", {})["brewzilla_last_apply_result"] = result
    return result


async def _patched_async_mark_mash_in_started(hass: HomeAssistant) -> dict[str, Any]:
    assert _ORIGINAL_MARK_MASH_IN_STARTED is not None
    snapshot = gate.build_mash_in_gate_snapshot(hass)
    state = str(snapshot.get("state") or "idle")

    if bool(snapshot.get("completed_once")) or state == "mash_in_complete":
        result = _ignored_result(hass, snapshot, reason="already_complete")
        await async_record_brewday_audit_event(
            hass,
            "mash_in_started_ignored",
            brewzilla_result=result,
            note="Mash-In Started ignored because mash-in is already complete.",
            always_record=True,
        )
        return result

    if state != gate.READY_STATE:
        result = _ignored_result(hass, snapshot, reason=f"not_ready:{state}")
        await async_record_brewday_audit_event(
            hass,
            "mash_in_started_ignored",
            brewzilla_result=result,
            note=f"Mash-In Started ignored because gate state is {state}, not ready_for_mash_in.",
            always_record=True,
        )
        return result

    return await _ORIGINAL_MARK_MASH_IN_STARTED(hass)


def install_mash_in_state_guard() -> None:
    """Install one-way state protection for Mash-In Started."""
    global _INSTALLED, _ORIGINAL_MARK_MASH_IN_STARTED
    if _INSTALLED:
        return

    _ORIGINAL_MARK_MASH_IN_STARTED = gate.async_mark_mash_in_started
    gate.async_mark_mash_in_started = _patched_async_mark_mash_in_started
    _INSTALLED = True
