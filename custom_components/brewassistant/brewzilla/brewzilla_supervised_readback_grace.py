"""Suppress duplicate Supervised Apply prompts caused by stale RCL config readback.

A confirmed BrewZilla plan may update Home Assistant optimistically and then be
briefly overwritten by an older RAPT Cloud Link value. That stale value must not
look like new operator intent and immediately request another confirmation.

This guard remembers only the configuration increases that were both confirmed
and actually sent by the explicit CONFIRM executor. For a short bounded window,
an identical runtime/step/target may therefore ignore a stale target/heat/pump
number readback. Switch ON actions are deliberately excluded: if heater or pump
really goes OFF, re-energizing still requires a fresh confirmation.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from ..supervised_apply import clear_pending_action_from_source, register_supervised_executor
from . import brewzilla_orchestration as base
from . import brewzilla_supervised_runtime_guard as supervised

_BASE_APPLY = None
_BASE_EXECUTE = None
_INSTALLED = False

DATA_KEY = "brewzilla_supervised_confirmed_readback_grace"
CONFIRMED_READBACK_GRACE_SECONDS = 240
_CONFIG_ACTION_KEYS = {"target_up", "heat_up", "pump_up"}


def _data(hass: HomeAssistant) -> dict[str, Any]:
    return hass.data.setdefault("brewassistant", {})


def _clear_grace(hass: HomeAssistant) -> None:
    _data(hass).pop(DATA_KEY, None)


def _executed_action_keys(result: dict[str, Any]) -> set[str]:
    keys: set[str] = set()
    for raw in result.get("actions") or []:
        action = str(raw)
        if action.startswith("set_target:"):
            keys.add("target_up")
        elif action.startswith("set_heat_utilization:") or action.startswith(
            "ba_owned_reassert_heat_utilization:"
        ):
            keys.add("heat_up")
        elif action.startswith("set_pump_utilization:") or action.startswith(
            "ba_owned_reassert_pump_utilization:"
        ):
            keys.add("pump_up")
    return keys


def _confirmed_config_actions(
    pending: dict[str, Any], result: dict[str, Any]
) -> list[dict[str, Any]]:
    context = pending.get("context")
    actions = context.get("actions") if isinstance(context, dict) else None
    if not isinstance(actions, list):
        return []
    executed_keys = _executed_action_keys(result)
    return [
        dict(action)
        for action in actions
        if isinstance(action, dict)
        and action.get("key") in _CONFIG_ACTION_KEYS
        and action.get("key") in executed_keys
    ]


def _store_grace(
    hass: HomeAssistant,
    pending: dict[str, Any],
    result: dict[str, Any],
) -> None:
    actions = _confirmed_config_actions(pending, result)
    if not actions:
        _clear_grace(hass)
        return

    context = pending.get("context")
    if not isinstance(context, dict):
        _clear_grace(hass)
        return

    now = dt_util.utcnow()
    _data(hass)[DATA_KEY] = {
        "plan_id": pending.get("id"),
        "context": dict(context),
        "actions": actions,
        "confirmed_at": now.isoformat(),
        "expires_at": (now + timedelta(seconds=CONFIRMED_READBACK_GRACE_SECONDS)).isoformat(),
    }


def _active_grace(hass: HomeAssistant) -> dict[str, Any] | None:
    grace = _data(hass).get(DATA_KEY)
    if not isinstance(grace, dict):
        return None
    expires_at = dt_util.parse_datetime(str(grace.get("expires_at") or ""))
    if expires_at is None or dt_util.utcnow() >= dt_util.as_utc(expires_at):
        _clear_grace(hass)
        return None
    return grace


def _intent_context(snapshot: dict[str, Any]) -> dict[str, Any]:
    context = supervised._plan_payload(snapshot, [])
    context.pop("actions", None)
    return context


def _same_intent(snapshot: dict[str, Any], grace: dict[str, Any]) -> bool:
    stored = grace.get("context")
    if not isinstance(stored, dict):
        return False
    current = _intent_context(snapshot)
    return all(stored.get(key) == value for key, value in current.items())


def _action_matches(current: dict[str, Any], confirmed: dict[str, Any]) -> bool:
    key = current.get("key")
    if key != confirmed.get("key") or key not in _CONFIG_ACTION_KEYS:
        return False
    current_value = supervised._num(current.get("value"))
    confirmed_value = supervised._num(confirmed.get("value"))
    if current_value is None or confirmed_value is None:
        return current_value == confirmed_value
    tolerance = (
        base.TARGET_SYNC_TOLERANCE if key == "target_up" else base.UTILIZATION_TOLERANCE
    )
    return abs(current_value - confirmed_value) <= tolerance


def _covered_by_grace(
    positives: list[dict[str, Any]], grace: dict[str, Any]
) -> bool:
    confirmed = grace.get("actions")
    if not positives or not isinstance(confirmed, list):
        return False
    return all(
        any(
            isinstance(known, dict) and _action_matches(action, known)
            for known in confirmed
        )
        for action in positives
    )


def _grace_timing(grace: dict[str, Any]) -> tuple[int | None, int | None]:
    now = dt_util.utcnow()
    confirmed_at = dt_util.parse_datetime(str(grace.get("confirmed_at") or ""))
    expires_at = dt_util.parse_datetime(str(grace.get("expires_at") or ""))
    age = (
        max(0, int((now - dt_util.as_utc(confirmed_at)).total_seconds()))
        if confirmed_at is not None
        else None
    )
    remaining = (
        max(0, int((dt_util.as_utc(expires_at) - now).total_seconds()))
        if expires_at is not None
        else None
    )
    return age, remaining


async def async_execute_confirmed_plan(
    hass: HomeAssistant, pending: dict[str, Any]
) -> dict[str, Any]:
    """Delegate explicit execution, then remember config writes that were sent."""
    assert _BASE_EXECUTE is not None
    result = await _BASE_EXECUTE(hass, pending)
    if result.get("supervised_confirmation_consumed"):
        _store_grace(hass, pending, result)
    return result


async def async_apply_brewzilla_target_if_allowed(hass: HomeAssistant) -> dict[str, Any]:
    """Suppress only stale duplicate config increases from a just-confirmed plan."""
    assert _BASE_APPLY is not None

    grace = _active_grace(hass)
    if grace is None:
        return await _BASE_APPLY(hass)

    snapshot = base.build_orchestration_snapshot(hass)
    if snapshot.get("abort_lockout_active"):
        _clear_grace(hass)
        return await _BASE_APPLY(hass)

    if not _same_intent(snapshot, grace):
        _clear_grace(hass)
        return await _BASE_APPLY(hass)

    positives = supervised._positive_actions(snapshot)
    if not positives:
        return await _BASE_APPLY(hass)

    if not _covered_by_grace(positives, grace):
        _clear_grace(hass)
        return await _BASE_APPLY(hass)

    # The same configuration increase was already explicitly confirmed and sent.
    # Do not write it again and do not recreate a pending plan. Safe-down and
    # explicitly operator-owned Manual actions may still pass through immediately.
    direct_actions = await supervised._apply_nonpositive_or_manual_actions(hass, snapshot)
    clear_pending_action_from_source(hass, supervised.SOURCE)
    age, remaining = _grace_timing(grace)
    result = {
        **snapshot,
        "applied": bool(direct_actions),
        "apply_result": "confirmed_plan_readback_grace",
        "actions": direct_actions,
        "has_pending_action": False,
        "pending_action": None,
        "pending_summary": None,
        "supervised_runtime_plan_pending": False,
        "supervised_readback_grace_active": True,
        "supervised_readback_grace_plan_id": grace.get("plan_id"),
        "supervised_readback_grace_age_seconds": age,
        "supervised_readback_grace_remaining_seconds": remaining,
        "supervised_readback_grace_actions": grace.get("actions"),
        "executed_at": dt_util.utcnow().isoformat(),
    }
    _data(hass)["brewzilla_last_apply_result"] = result
    await base.async_record_brewday_audit_tick(hass, brewzilla_result=result)
    return result


def install_supervised_readback_grace() -> None:
    """Install after the Supervised Apply guard so its executor can be wrapped."""
    global _BASE_APPLY, _BASE_EXECUTE, _INSTALLED
    if _INSTALLED:
        return
    _BASE_APPLY = base.async_apply_brewzilla_target_if_allowed
    _BASE_EXECUTE = supervised.async_execute_confirmed_plan
    register_supervised_executor(supervised.SOURCE, supervised.KIND, async_execute_confirmed_plan)
    base.async_apply_brewzilla_target_if_allowed = async_apply_brewzilla_target_if_allowed
    _INSTALLED = True
