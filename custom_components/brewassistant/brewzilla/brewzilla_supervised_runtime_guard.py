"""Supervised confirmation gate for positive BrewZilla runtime actions.

Runtime progression is never paused by this guard. Manual Brewday and Brewfather
remain the process clocks/state machines. The guard only sits between runtime
intent and physical BrewZilla changes:

* safe-down actions are applied immediately,
* operator-owned Manual setpoints are transported immediately,
* AUTO positive actions are bundled into one supervised plan,
* confirmation re-evaluates the live plan before any positive action is sent.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from homeassistant.util import dt as dt_util

from ..control_policy import (
    APPLY_WITH_CONFIRM_POLICY,
    DIRECT_ACTION_POLICY,
    READ_ONLY_POLICY,
    SOURCE_BACKEND,
    SOURCE_BREW_TRACKER,
    effective_policy,
)
from ..supervised_apply import (
    clear_pending_action_from_source,
    get_last_result,
    get_pending_action,
    set_pending_action,
)
from . import brewzilla_orchestration as base

_BASE_BUILD = None
_BASE_APPLY = None
_INSTALLED = False

SOURCE = "brewzilla_orchestration"
KIND = "brewzilla_runtime_plan"


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_increase(current: Any, desired: Any, *, tolerance: float) -> bool:
    desired_num = _num(desired)
    current_num = _num(current)
    if desired_num is None:
        return False
    if current_num is None:
        return desired_num > tolerance
    return desired_num > current_num + tolerance


def _is_decrease_or_equal(current: Any, desired: Any, *, tolerance: float) -> bool:
    desired_num = _num(desired)
    current_num = _num(current)
    if desired_num is None:
        return False
    if current_num is None:
        return abs(desired_num) <= tolerance
    return desired_num <= current_num + tolerance


def _request_source(snapshot: dict[str, Any]) -> str:
    return (
        SOURCE_BREW_TRACKER
        if snapshot.get("runtime_source") == "Brewfather Brew Tracker"
        else SOURCE_BACKEND
    )


def _positive_actions(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    """Return AUTO actions that can energize or increase BrewZilla output."""
    actions: list[dict[str, Any]] = []

    if (
        snapshot.get("target_sync_needed")
        and not snapshot.get("manual_target_override_active")
        and _is_increase(
            snapshot.get("applied_target"),
            snapshot.get("requested_target"),
            tolerance=base.TARGET_SYNC_TOLERANCE,
        )
    ):
        actions.append(
            {
                "key": "target_up",
                "section": "target",
                "value": _num(snapshot.get("requested_target")),
            }
        )

    if (
        snapshot.get("heat_utilization_action_needed")
        and not snapshot.get("manual_heat_override_active")
        and _is_increase(
            snapshot.get("heat_utilization"),
            snapshot.get("desired_heat_utilization"),
            tolerance=base.UTILIZATION_TOLERANCE,
        )
    ):
        actions.append(
            {
                "key": "heat_up",
                "section": "heater",
                "value": _num(snapshot.get("desired_heat_utilization")),
            }
        )

    if snapshot.get("heater_action_needed"):
        actions.append({"key": "heater_on", "section": "heater", "value": True})

    if (
        snapshot.get("pump_utilization_action_needed")
        and not snapshot.get("manual_pump_override_active")
        and _is_increase(
            snapshot.get("pump_utilization"),
            snapshot.get("desired_pump_utilization"),
            tolerance=base.UTILIZATION_TOLERANCE,
        )
    ):
        actions.append(
            {
                "key": "pump_up",
                "section": "pump",
                "value": _num(snapshot.get("desired_pump_utilization")),
            }
        )

    if snapshot.get("pump_action_needed"):
        actions.append({"key": "pump_on", "section": "pump", "value": True})

    return actions


def _plan_payload(snapshot: dict[str, Any], actions: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "runtime_source": snapshot.get("runtime_source"),
        "runtime_state": snapshot.get("brewday_state"),
        "stage": snapshot.get("runtime_stage"),
        "step": snapshot.get("runtime_step"),
        "raw_step_index": snapshot.get("runtime_raw_step_index"),
        "resolved_step_index": snapshot.get("runtime_resolved_step_index"),
        "requested_target": _num(snapshot.get("requested_target")),
        "actions": actions,
    }


def _plan_id(snapshot: dict[str, Any], actions: list[dict[str, Any]]) -> str:
    payload = _plan_payload(snapshot, actions)
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha1(raw.encode("utf-8"), usedforsecurity=False).hexdigest()[:16]
    return f"brewzilla-runtime:{digest}"


def _plan_summary(snapshot: dict[str, Any], actions: list[dict[str, Any]]) -> str:
    bits: list[str] = []
    for action in actions:
        key = action["key"]
        value = action.get("value")
        if key == "target_up" and value is not None:
            bits.append(f"mål {float(value):.1f} °C")
        elif key == "heat_up" and value is not None:
            bits.append(f"värme {float(value):.0f} %")
        elif key == "heater_on":
            bits.append("värmare PÅ")
        elif key == "pump_up" and value is not None:
            bits.append(f"pump {float(value):.0f} %")
        elif key == "pump_on":
            bits.append("pump PÅ")

    stage = str(snapshot.get("runtime_stage") or "Bryggdag")
    step = str(snapshot.get("runtime_step") or "")
    prefix = f"{stage} · {step}" if step else stage
    return f"{prefix}: " + " · ".join(bits)


def _plan_policy(hass, snapshot: dict[str, Any], actions: list[dict[str, Any]]) -> str:
    """Return read_only, confirm, or direct for the bundled positive plan."""
    request_source = _request_source(snapshot)
    policies: list[dict[str, Any]] = []
    for section in sorted({str(action["section"]) for action in actions}):
        policies.append(effective_policy(hass, section=section, source=request_source))

    if any(item.get("effective_policy") == READ_ONLY_POLICY for item in policies):
        return "read_only"

    if any(item.get("effective_policy") == APPLY_WITH_CONFIRM_POLICY for item in policies):
        return "confirm"

    for item in policies:
        if item.get("effective_policy") != DIRECT_ACTION_POLICY:
            return "confirm"
        if not item.get("direct_unlocked"):
            return "confirm"
        if item.get("feed_policy") is not None and not item.get("feed_direct_unlocked"):
            return "confirm"
    return "direct"


def _pending_for_plan(hass, snapshot: dict[str, Any], actions: list[dict[str, Any]]) -> dict[str, Any]:
    plan_id = _plan_id(snapshot, actions)
    existing = get_pending_action(hass)
    if existing and existing.get("source") == SOURCE and existing.get("id") == plan_id:
        return existing

    action = {
        "id": plan_id,
        "source": SOURCE,
        "kind": KIND,
        "section": "brewzilla_runtime",
        "summary": _plan_summary(snapshot, actions),
        "domain": "brewassistant",
        "service": "apply_brewzilla_target",
        "service_data": {"supervised_plan_id": plan_id},
        "context": _plan_payload(snapshot, actions),
    }
    return set_pending_action(hass, action)


def _confirmation_matches(hass, plan_id: str) -> bool:
    pending = get_pending_action(hass)
    last = get_last_result(hass)
    return bool(
        pending
        and pending.get("source") == SOURCE
        and pending.get("id") == plan_id
        and last
        and last.get("status") == "executing"
        and last.get("id") == plan_id
    )


def _decorate_pending(hass, snapshot: dict[str, Any]) -> dict[str, Any]:
    out = dict(snapshot)
    pending = get_pending_action(hass)
    if pending and pending.get("source") == SOURCE:
        out.update(
            {
                "has_pending_action": True,
                "pending_action": pending,
                "pending_summary": pending.get("summary"),
                "pending_action_id": pending.get("id"),
                "supervised_runtime_plan_pending": True,
            }
        )
        if not out.get("abort_lockout_active"):
            out["safety_state"] = "awaiting_confirmation"
    else:
        out["supervised_runtime_plan_pending"] = False
    return out


def build_orchestration_snapshot(hass) -> dict[str, Any]:
    assert _BASE_BUILD is not None
    return _decorate_pending(hass, _BASE_BUILD(hass))


async def _apply_nonpositive_or_manual_actions(hass, snapshot: dict[str, Any]) -> list[str]:
    """Apply only safe-down actions and explicitly operator-owned Manual values."""
    actions: list[str] = []

    target = _num(snapshot.get("requested_target"))
    applied_target = _num(snapshot.get("applied_target"))
    target_direct = bool(
        snapshot.get("target_sync_needed")
        and target is not None
        and (
            snapshot.get("manual_target_override_active")
            or _is_decrease_or_equal(
                applied_target,
                target,
                tolerance=base.TARGET_SYNC_TOLERANCE,
            )
        )
    )
    if target_direct and await base._set_number(hass, base.BREWZILLA_TARGET_NUMBER, round(target, 1)):
        actions.append(f"set_target:{round(target, 1)}")

    desired_heat = _num(snapshot.get("desired_heat_utilization"))
    heat_direct = bool(
        snapshot.get("heat_utilization_action_needed")
        and desired_heat is not None
        and (
            snapshot.get("manual_heat_override_active")
            or _is_decrease_or_equal(
                snapshot.get("heat_utilization"),
                desired_heat,
                tolerance=base.UTILIZATION_TOLERANCE,
            )
        )
    )
    if heat_direct and await base._set_number(hass, base.BREWZILLA_HEAT_UTILIZATION, round(desired_heat, 1)):
        actions.append(f"set_heat_utilization:{round(desired_heat, 1)}")

    desired_pump = _num(snapshot.get("desired_pump_utilization"))
    pump_direct = bool(
        snapshot.get("pump_utilization_action_needed")
        and desired_pump is not None
        and (
            snapshot.get("manual_pump_override_active")
            or _is_decrease_or_equal(
                snapshot.get("pump_utilization"),
                desired_pump,
                tolerance=base.UTILIZATION_TOLERANCE,
            )
        )
    )
    if pump_direct and await base._set_number(hass, base.BREWZILLA_PUMP_UTILIZATION, round(desired_pump, 1)):
        actions.append(f"set_pump_utilization:{round(desired_pump, 1)}")

    if snapshot.get("heater_stop_needed") and hass.states.get(base.BREWZILLA_HEATER_SWITCH) is not None:
        await base._call_switch(hass, "off", base.BREWZILLA_HEATER_SWITCH)
        actions.append("heater_off")

    if (
        snapshot.get("pump_stop_needed") or snapshot.get("completion_pump_stop_needed")
    ) and hass.states.get(base.BREWZILLA_PUMP_SWITCH) is not None:
        await base._call_switch(hass, "off", base.BREWZILLA_PUMP_SWITCH)
        actions.append("pump_off")

    return actions


async def async_apply_brewzilla_target_if_allowed(hass) -> dict[str, Any]:
    assert _BASE_APPLY is not None
    snapshot = base.build_orchestration_snapshot(hass)

    # ABORT and existing hard safety guards must retain their original direct
    # safe-down behavior without any confirmation layer in the way.
    if snapshot.get("abort_lockout_active") or not snapshot.get("can_apply_target"):
        if not snapshot.get("can_apply_target"):
            positives = _positive_actions(snapshot)
            if not positives:
                clear_pending_action_from_source(hass, SOURCE)
        return await _BASE_APPLY(hass)

    positives = _positive_actions(snapshot)
    if not positives:
        clear_pending_action_from_source(hass, SOURCE)
        return await _BASE_APPLY(hass)

    plan_id = _plan_id(snapshot, positives)

    # The generic BEKRÄFTA button marks the pending action as executing before
    # it calls brewassistant.apply_brewzilla_target. Only that exact live plan is
    # allowed through. If BF/Manual has advanced meanwhile, confirmation is stale
    # and nothing positive is sent.
    last = get_last_result(hass)
    if last and last.get("status") == "executing" and last.get("source") == SOURCE:
        if _confirmation_matches(hass, plan_id):
            return await _BASE_APPLY(hass)

        result = {
            **snapshot,
            "applied": False,
            "apply_result": "supervised_plan_stale",
            "actions": [],
            "supervised_plan_id": plan_id,
            "supervised_plan_summary": _plan_summary(snapshot, positives),
            "executed_at": dt_util.utcnow().isoformat(),
        }
        await base.async_record_brewday_audit_tick(hass, brewzilla_result=result)
        return result

    policy = _plan_policy(hass, snapshot, positives)
    if policy == "direct":
        clear_pending_action_from_source(hass, SOURCE)
        return await _BASE_APPLY(hass)

    direct_actions = await _apply_nonpositive_or_manual_actions(hass, snapshot)

    if policy == "read_only":
        clear_pending_action_from_source(hass, SOURCE)
        result = {
            **snapshot,
            "applied": bool(direct_actions),
            "apply_result": "positive_actions_read_only",
            "actions": direct_actions,
            "supervised_plan_id": plan_id,
            "supervised_plan_summary": _plan_summary(snapshot, positives),
            "supervised_positive_actions": positives,
            "executed_at": dt_util.utcnow().isoformat(),
        }
        await base.async_record_brewday_audit_tick(hass, brewzilla_result=result)
        return result

    pending = _pending_for_plan(hass, snapshot, positives)
    result = {
        **snapshot,
        "applied": bool(direct_actions),
        "apply_result": "pending_confirmation",
        "actions": direct_actions,
        "has_pending_action": True,
        "pending_action": pending,
        "pending_summary": pending.get("summary"),
        "supervised_runtime_plan_pending": True,
        "supervised_plan_id": plan_id,
        "supervised_plan_summary": pending.get("summary"),
        "supervised_positive_actions": positives,
        "executed_at": dt_util.utcnow().isoformat(),
    }
    hass.data.setdefault("brewassistant", {})["brewzilla_last_apply_result"] = result
    await base.async_record_brewday_audit_tick(hass, brewzilla_result=result)
    return result


def install_supervised_runtime_guard() -> None:
    """Install after Manual ownership so the gate sees final channel ownership."""
    global _BASE_BUILD, _BASE_APPLY, _INSTALLED
    if _INSTALLED:
        return
    _BASE_BUILD = base.build_orchestration_snapshot
    _BASE_APPLY = base.async_apply_brewzilla_target_if_allowed
    base.build_orchestration_snapshot = build_orchestration_snapshot
    base.async_apply_brewzilla_target_if_allowed = async_apply_brewzilla_target_if_allowed
    _INSTALLED = True
