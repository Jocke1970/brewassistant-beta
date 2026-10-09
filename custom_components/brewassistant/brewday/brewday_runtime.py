"""Normalized Brewday runtime with three explicit execution modes.

Normal modes are Manual Brewing, Brewfather Brewing and RCL Brewing. Recipe
context is separate from execution mode: a lost active external source falls
back to Manual Brewing while retaining its last trustworthy recipe context.
STOP/ABORT is a separate global latch, never a fourth mode.
"""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from . import brewday_execution_mode as execution_mode
from . import brewday_runtime_core as runtime_core
from .brewday_operator_abort import (
    brewday_operator_abort_active,
    brewday_operator_abort_snapshot,
)
from .brewday_ramp_target_gate import build_core_snapshot, core_attrs, source as core_source
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
    return get_manual_brewday_session(hass).state in MANUAL_RUNTIME_ACTIVE_STATES


def _pause_manual_brewday_for_rapt(hass: HomeAssistant) -> bool:
    session = get_manual_brewday_session(hass)
    if session.state not in {ManualRuntimeState.RUNNING, ManualRuntimeState.AWAITING_CONFIRM}:
        return False
    session.pause()
    return True


def _brewfather_transport_unavailable(hass: HomeAssistant) -> bool:
    for entity_id in runtime_core.entity_candidates(runtime_core.BF_STATUS):
        state = hass.states.get(entity_id)
        if state is None:
            continue
        return str(state.state).strip().lower() in runtime_core.BAD
    return True


def _with_operator_control_state(hass: HomeAssistant, snapshot: dict[str, Any]) -> dict[str, Any]:
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
    operator = brewday_operator_abort_snapshot(hass)
    snapshot = build_core_snapshot(hass)
    source_name = str(operator.get("source") or "None")
    stage = str(operator.get("stage") or "Idle")
    step = str(operator.get("step") or "Idle")
    snapshot.update({
        "source": "None", "status": "aborted", "runtime_state": "aborted",
        "stage": stage, "step": step, "next_step": "None", "progress": 0.0,
        "time_remaining_seconds": 0, "time_remaining_minutes": 0,
        "target_temperature": None, "refresh_recommended": False,
        "awaiting_snapshot": False,
        "summary": f"aborted · operator lockout · previous source {source_name} · {stage} · {step}",
    })
    snapshot = execution_mode.decorate_snapshot(
        hass, snapshot, execution_mode.current_mode(hass),
        fallback_from=(execution_mode.last_external_mode(hass) if execution_mode.fallback_active(hass) else None),
        fallback_reason=("operator_abort" if execution_mode.fallback_active(hass) else None),
        reconnect_expected=False,
        recipe_context_retained=execution_mode.fallback_active(hass),
    )
    return _with_operator_control_state(hass, snapshot)


def source(hass: HomeAssistant) -> str:
    from .rapt_profile_runtime import (
        RAPT_PROFILE_SOURCE,
        rapt_profile_runtime_active,
        rapt_profile_runtime_claims_source,
    )
    if rapt_profile_runtime_active(hass):
        return RAPT_PROFILE_SOURCE
    if (
        rapt_profile_runtime_claims_source(hass)
        and execution_mode.has_external_snapshot(hass, execution_mode.RCL_BREWING)
    ):
        return "Manual Brewday"
    selected = core_source(hass)
    if selected == "Brewfather Brew Tracker":
        return selected
    if execution_mode.fallback_active(hass) or _manual_engine_is_active(hass):
        return "Manual Brewday"
    return selected


def build_brewday_runtime_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    if brewday_operator_abort_active(hass):
        return _operator_aborted_snapshot(hass)

    from .rapt_profile_runtime import build_rapt_profile_runtime_snapshot
    rapt_snapshot = build_rapt_profile_runtime_snapshot(hass)
    if rapt_snapshot is not None:
        rapt_state = str(rapt_snapshot.get("runtime_state") or "").lower()
        rapt_live = bool(
            rapt_snapshot.get("profile_active") is True
            and rapt_snapshot.get("profile_source_available") is True
            and rapt_state in {"live", "running", "paused", "awaiting_snapshot"}
        )
        if rapt_live:
            _pause_manual_brewday_for_rapt(hass)
            execution_mode.remember_external_snapshot(hass, rapt_snapshot, execution_mode.RCL_BREWING)
            return _with_operator_control_state(
                hass,
                execution_mode.decorate_snapshot(
                    hass, rapt_snapshot, execution_mode.RCL_BREWING,
                    recipe_context_retained=True,
                ),
            )
        if rapt_state in {"source_unavailable", "source_unverified"}:
            fallback = execution_mode.build_manual_fallback_snapshot(
                hass, from_mode=execution_mode.RCL_BREWING, reason=f"rcl_{rapt_state}"
            )
            if fallback is not None:
                return _with_operator_control_state(hass, fallback)
            return _with_operator_control_state(hass, rapt_snapshot)
        if rapt_state in {"inactive", "completed"}:
            execution_mode.external_ended(hass, execution_mode.RCL_BREWING, reason="rcl_profile_stopped")

    runtime_source = core_source(hass)
    if runtime_source == "Brewfather Brew Tracker":
        pause_manual_brewday_for_brewfather(hass)
        snapshot = build_core_snapshot(hass)
        execution_mode.remember_external_snapshot(hass, snapshot, execution_mode.BREWFATHER_BREWING)
        return _with_operator_control_state(
            hass,
            execution_mode.decorate_snapshot(
                hass, snapshot, execution_mode.BREWFATHER_BREWING,
                recipe_context_retained=True,
            ),
        )

    if (
        execution_mode.last_external_mode(hass) == execution_mode.BREWFATHER_BREWING
        and execution_mode.has_external_snapshot(hass, execution_mode.BREWFATHER_BREWING)
        and _brewfather_transport_unavailable(hass)
    ):
        fallback = execution_mode.build_manual_fallback_snapshot(
            hass, from_mode=execution_mode.BREWFATHER_BREWING,
            reason="brewfather_source_unavailable",
        )
        if fallback is not None:
            return _with_operator_control_state(hass, fallback)

    if execution_mode.last_external_mode(hass) == execution_mode.BREWFATHER_BREWING:
        execution_mode.external_ended(
            hass, execution_mode.BREWFATHER_BREWING, reason="brewfather_session_inactive"
        )

    snapshot = (
        build_manual_engine_snapshot(hass)
        if _manual_engine_is_active(hass) or runtime_source == "Manual Brewday"
        else build_core_snapshot(hass)
    )
    return _with_operator_control_state(
        hass,
        execution_mode.decorate_snapshot(
            hass, snapshot, execution_mode.MANUAL_BREWING,
            recipe_context_retained=False,
        ),
    )


def brewday_runtime_attrs(snapshot: dict[str, Any]) -> dict[str, Any]:
    attrs = core_attrs(snapshot)
    for key in (
        "operator_control_state", "operator_abort_active", "operator_abort_source",
        "operator_abort_stage", "operator_abort_step", "operator_abort_at",
        "operator_rearmed_at", "brewday_mode", "recipe_owner", "step_timer_owner",
        "target_owner", "heat_owner", "pump_owner", "fallback_active",
        "fallback_from_mode", "fallback_reason", "recipe_context_retained",
        "reconnect_expected", "fallback_timeline_frozen", "fallback_progression_policy",
    ):
        attrs[key] = snapshot.get(key)
    return attrs
