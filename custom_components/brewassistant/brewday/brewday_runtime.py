"""Compatibility wrapper for Brewday Runtime normalization.

The public functions in this module are imported by Brewday Runtime sensors.
The actual Brewfather resolver lives in brewday_runtime_core.py and is adjusted
by brewday_ramp_target_gate.py so temperature ramps do not advance before target.
Manual Brewday can be routed through its Python engine adapter without changing
the sensor platform.
"""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .brewday_operator_abort import (
    brewday_operator_abort_active,
    brewday_operator_abort_snapshot,
)
from .brewday_ramp_target_gate import build_core_snapshot, core_attrs, source
from .manual_brewday_adapter import build_manual_engine_snapshot
from .manual_brewday_runtime import ManualRuntimeState
from .manual_brewday_store import (
    get_manual_brewday_session,
    pause_manual_brewday_for_brewfather,
)


MANUAL_RUNTIME_ACTIVE_STATES = {
    ManualRuntimeState.PREPARED,
    ManualRuntimeState.RUNNING,
    ManualRuntimeState.PAUSED,
    ManualRuntimeState.AWAITING_CONFIRM,
    ManualRuntimeState.COMPLETED,
}


def _manual_engine_is_active(hass: HomeAssistant) -> bool:
    """Return true when the Python-owned manual runtime session is active."""
    session = get_manual_brewday_session(hass)
    return session.state in MANUAL_RUNTIME_ACTIVE_STATES


def _with_operator_control_state(hass: HomeAssistant, snapshot: dict[str, Any]) -> dict[str, Any]:
    """Attach the persistent operator-control latch diagnostics."""
    operator = brewday_operator_abort_snapshot(hass)
    snapshot["operator_control_state"] = operator.get("control_state", "armed")
    snapshot["operator_abort_active"] = bool(operator.get("active"))
    snapshot["operator_abort_source"] = operator.get("source")
    snapshot["operator_abort_stage"] = operator.get("stage")
    snapshot["operator_abort_step"] = operator.get("step")
    snapshot["operator_abort_at"] = operator.get("aborted_at")
    snapshot["operator_rearmed_at"] = operator.get("rearmed_at")
    return snapshot


def _operator_aborted_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    """Return an explicit stopped runtime while the operator ABORT latch is set."""
    operator = brewday_operator_abort_snapshot(hass)
    snapshot = build_core_snapshot(hass)
    source_name = str(operator.get("source") or "None")
    stage = str(operator.get("stage") or "Idle")
    step = str(operator.get("step") or "Idle")
    snapshot.update(
        {
            "source": "None",
            "status": "aborted",
            "runtime_state": "aborted",
            "stage": stage,
            "step": step,
            "next_step": "None",
            "progress": 0.0,
            "time_remaining_seconds": 0,
            "time_remaining_minutes": 0,
            "target_temperature": None,
            "refresh_recommended": False,
            "awaiting_snapshot": False,
            "summary": f"aborted · operator lockout · previous source {source_name} · {stage} · {step}",
        }
    )
    return _with_operator_control_state(hass, snapshot)


def build_brewday_runtime_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    """Build a normalized brewday runtime snapshot.

    External live Brewfather Brew Tracker data must win over Manual Brewday.
    Manual runtime is a fallback only when there is no active Brewfather source.
    An explicit operator ABORT outranks both sources and keeps the runtime
    non-owning until control is explicitly rearmed.
    """
    if brewday_operator_abort_active(hass):
        return _operator_aborted_snapshot(hass)

    runtime_source = source(hass)
    if runtime_source == "Brewfather Brew Tracker":
        pause_manual_brewday_for_brewfather(hass)
        return _with_operator_control_state(hass, build_core_snapshot(hass))
    if _manual_engine_is_active(hass):
        return _with_operator_control_state(hass, build_manual_engine_snapshot(hass))
    if runtime_source == "Manual Brewday":
        return _with_operator_control_state(hass, build_manual_engine_snapshot(hass))
    return _with_operator_control_state(hass, build_core_snapshot(hass))


def brewday_runtime_attrs(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Return common runtime attributes for Brewday Runtime sensors."""
    attrs = core_attrs(snapshot)
    for key in (
        "operator_control_state",
        "operator_abort_active",
        "operator_abort_source",
        "operator_abort_stage",
        "operator_abort_step",
        "operator_abort_at",
        "operator_rearmed_at",
    ):
        attrs[key] = snapshot.get(key)
    return attrs
