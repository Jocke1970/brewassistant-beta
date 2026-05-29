"""Semi-automatic BrewZilla orchestration helpers.

This layer is intentionally conservative. BrewAssistant may recommend or apply
BrewZilla targets, but execution is routed through section-scoped policies.
"""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .control_policy import SOURCE_BREW_TRACKER, request_action
from .supervised_apply import (
    clear_pending_action_from_source,
    get_pending_action,
    supervised_apply_enabled,
)

BREWDAY_TARGET_SENSOR = "sensor.brewassistant_brewday_target_temperature"
BREWDAY_STATE_SENSOR = "sensor.brewassistant_brewday_runtime_state"
BREWDAY_STAGE_SENSOR = "sensor.brewassistant_brewday_runtime_stage"
BREWDAY_STEP_SENSOR = "sensor.brewassistant_brewday_runtime_step"
BREWZILLA_TARGET_NUMBER = "number.brewzilla_target_temperature"
BREWZILLA_CONNECTION_SENSOR = "sensor.brewzilla_connection"

ORCHESTRATION_ENABLED = "switch.brewassistant_brewzilla_orchestration_enabled"
APPLY_TARGET_ENABLED = "switch.brewassistant_brewzilla_apply_target_temp"
MANUAL_TARGET_OVERRIDE = "switch.brewassistant_brewzilla_manual_target_override"
ALLOW_HEATER_CONTROL = "switch.brewassistant_brewzilla_allow_heater_control"
ALLOW_PUMP_CONTROL = "switch.brewassistant_brewzilla_allow_pump_control"
ALLOW_BOIL_MODE = "switch.brewassistant_brewzilla_allow_boil_mode"
SAFE_MODE = "switch.brewassistant_brewzilla_safe_mode"

SOURCE = "brewzilla_orchestration"
MIN_TARGET_TEMP = 0.0
MAX_NORMAL_TARGET_TEMP = 100.0
MAX_BOIL_TARGET_TEMP = 110.0
MAX_TARGET_STEP_DELTA = 35.0
TARGET_SYNC_TOLERANCE = 0.1


def _state(hass: HomeAssistant, entity_id: str, default: str | None = None) -> str | None:
    entity_state = hass.states.get(entity_id)
    if entity_state is None:
        return default
    return entity_state.state


def _float(hass: HomeAssistant, entity_id: str) -> float | None:
    raw = _state(hass, entity_id)
    if raw in {None, "unknown", "unavailable", "none", ""}:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _bool(hass: HomeAssistant, entity_id: str, default: bool = False) -> bool:
    fallback = "on" if default else "off"
    return (_state(hass, entity_id, fallback) or fallback).lower() == "on"


def _pending_is_ours(pending: dict[str, Any] | None) -> bool:
    if pending is None:
        return False
    if pending.get("source") == SOURCE:
        return True
    return pending.get("source") == "brewzilla_policy_router" and pending.get("request_source") == SOURCE_BREW_TRACKER


def _build_target_reason(hass: HomeAssistant, target: float) -> str:
    stage = _state(hass, BREWDAY_STAGE_SENSOR, "Brewday")
    step = _state(hass, BREWDAY_STEP_SENSOR, "step")
    return f"Brew Tracker: {stage} · {step} requests BrewZilla target {round(float(target), 1):.1f} °C"


async def async_request_brewtracker_target_sync(
    hass: HomeAssistant,
    *,
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    """Request target sync through the section-scoped policy router."""
    requested_target = snapshot.get("requested_target")
    if requested_target is None:
        return {**snapshot, "policy_result": {"status": "missing_target"}}

    result = await request_action(
        hass,
        section="target",
        command="set_target_temperature",
        value=float(requested_target),
        source=SOURCE_BREW_TRACKER,
        reason=_build_target_reason(hass, float(requested_target)),
        context={
            "orchestration_source": SOURCE,
            "brewday_state": snapshot.get("brewday_state"),
            "runtime_stage": _state(hass, BREWDAY_STAGE_SENSOR),
            "runtime_step": _state(hass, BREWDAY_STEP_SENSOR),
            "applied_target": snapshot.get("applied_target"),
            "target_delta": snapshot.get("target_delta"),
        },
    )
    return {**snapshot, "policy_result": result}


def build_orchestration_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    """Build orchestration state snapshot."""

    orchestration_enabled = _bool(hass, ORCHESTRATION_ENABLED)
    apply_target = _bool(hass, APPLY_TARGET_ENABLED)
    manual_override = _bool(hass, MANUAL_TARGET_OVERRIDE)
    allow_heater = _bool(hass, ALLOW_HEATER_CONTROL)
    allow_pump = _bool(hass, ALLOW_PUMP_CONTROL)
    allow_boil = _bool(hass, ALLOW_BOIL_MODE)
    safe_mode = _bool(hass, SAFE_MODE, True)
    supervised_enabled = supervised_apply_enabled(hass)

    brewday_target = _float(hass, BREWDAY_TARGET_SENSOR)
    brewzilla_target = _float(hass, BREWZILLA_TARGET_NUMBER)
    brewday_state = _state(hass, BREWDAY_STATE_SENSOR, "inactive")
    connection = _state(hass, BREWZILLA_CONNECTION_SENSOR, "unknown")

    connected = connection == "Connected"
    requested_target = brewday_target
    applied_target = brewzilla_target
    target_delta = None
    if requested_target is not None and applied_target is not None:
        target_delta = round(requested_target - applied_target, 2)

    reason = "Observe only"
    orchestration_mode = "observe"
    safety_state = "safe-mode" if safe_mode else "safe"
    can_apply_target = False
    target_sync_needed = False

    if not orchestration_enabled:
        reason = "Orchestration disabled"
        clear_pending_action_from_source(hass, SOURCE)

    elif manual_override:
        reason = "Manual target override active"
        orchestration_mode = "manual-override"
        clear_pending_action_from_source(hass, SOURCE)

    elif not connected:
        reason = "BrewZilla disconnected"
        orchestration_mode = "blocked"
        clear_pending_action_from_source(hass, SOURCE)

    elif brewday_state in {"inactive", "completed", "idle"}:
        reason = f"Brewday runtime {brewday_state}"
        orchestration_mode = "idle"
        clear_pending_action_from_source(hass, SOURCE)

    elif requested_target is None:
        reason = "No Brewday target available"
        orchestration_mode = "idle"
        clear_pending_action_from_source(hass, SOURCE)

    elif requested_target < MIN_TARGET_TEMP:
        reason = "Requested target below minimum"
        orchestration_mode = "blocked"
        clear_pending_action_from_source(hass, SOURCE)

    elif requested_target > MAX_NORMAL_TARGET_TEMP and not allow_boil:
        reason = "Boil-range target blocked"
        orchestration_mode = "blocked"
        clear_pending_action_from_source(hass, SOURCE)

    elif requested_target > MAX_BOIL_TARGET_TEMP:
        reason = "Requested target above BrewZilla maximum"
        orchestration_mode = "blocked"
        clear_pending_action_from_source(hass, SOURCE)

    elif target_delta is not None and abs(target_delta) > MAX_TARGET_STEP_DELTA:
        reason = "Target jump too large"
        orchestration_mode = "blocked"
        clear_pending_action_from_source(hass, SOURCE)

    elif apply_target:
        reason = "Target sync active"
        orchestration_mode = "target-sync"
        can_apply_target = True
        target_sync_needed = target_delta is not None and abs(target_delta) > TARGET_SYNC_TOLERANCE
        if not target_sync_needed:
            clear_pending_action_from_source(hass, SOURCE)

    if allow_heater or allow_pump or allow_boil:
        safety_state = "extra-controls-enabled"

    pending_action = get_pending_action(hass)
    has_ours = _pending_is_ours(pending_action)

    if can_apply_target and target_sync_needed and requested_target is not None:
        orchestration_mode = "pending-confirmation" if supervised_enabled else "policy-controlled"
        reason = "Target sync routed through section policy"

    return {
        "connected": connected,
        "orchestration_enabled": orchestration_enabled,
        "apply_target_enabled": apply_target,
        "manual_target_override": manual_override,
        "allow_heater_control": allow_heater,
        "allow_pump_control": allow_pump,
        "allow_boil_mode": allow_boil,
        "safe_mode": safe_mode,
        "requested_target": requested_target,
        "applied_target": applied_target,
        "target_delta": target_delta,
        "target_sync_needed": target_sync_needed,
        "can_apply_target": can_apply_target,
        "brewday_state": brewday_state,
        "orchestration_mode": orchestration_mode,
        "safety_state": safety_state,
        "control_reason": reason,
        "supervised_apply_enabled": supervised_enabled,
        "pending_action": pending_action if has_ours else None,
        "has_pending_action": has_ours,
        "pending_summary": pending_action.get("summary") if has_ours else None,
        "pending_section": pending_action.get("section") if has_ours else None,
        "pending_command": pending_action.get("command") if has_ours else None,
        "mode_scope": "section_policy",
    }


async def async_apply_brewzilla_target_if_allowed(hass: HomeAssistant) -> dict[str, Any]:
    """Route Brewday target to BrewZilla through section-scoped policy."""
    snapshot = build_orchestration_snapshot(hass)

    if snapshot.get("manual_target_override"):
        return {**snapshot, "applied": False, "apply_result": "manual_override_active"}

    if not snapshot["can_apply_target"]:
        return {**snapshot, "applied": False, "apply_result": "blocked"}

    if not snapshot["target_sync_needed"]:
        return {**snapshot, "applied": False, "apply_result": "already_in_sync"}

    if snapshot.get("has_pending_action"):
        return {**snapshot, "applied": False, "apply_result": "pending_confirmation"}

    routed = await async_request_brewtracker_target_sync(hass, snapshot=snapshot)
    policy_result = routed.get("policy_result") or {}
    status = policy_result.get("status")

    return {
        **routed,
        "applied": status == "executed",
        "apply_result": status or "policy_routed",
    }
