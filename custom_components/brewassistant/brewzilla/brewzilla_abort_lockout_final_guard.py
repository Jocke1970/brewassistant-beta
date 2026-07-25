"""Final ABORT lockout guard for BrewZilla positive actions.

This guard sits at the end of the BrewZilla monkey-patch chain and performs a
fresh ABORT-lockout check immediately before operator/runtime actions are allowed
to reach BrewZilla.  It is intentionally narrow: ABORT must win over delayed
mash-in auto-complete, circulation starts and any late orchestration tick.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import brewzilla_mash_in_gate as mash_in_gate
from . import brewzilla_orchestration as base

_INSTALLED = False
_ORIGINAL_APPLY: Callable[[HomeAssistant], Awaitable[dict[str, Any]]] | None = None
_ORIGINAL_START_MASH_CIRCULATION = None
_ORIGINAL_CALL_SWITCH = None
_ORIGINAL_SET_NUMBER = None

_POSITIVE_ACTION_MARKERS = (
    "set_target:",
    "set_heat_utilization:",
    "set_pump_utilization:",
    "heater_on",
    "pump_on",
    "ba_owned_reassert_heat_utilization:",
    "ba_owned_reassert_pump_utilization:",
)
_POSITIVE_SWITCH_SERVICES = {"on"}
_POSITIVE_NUMBER_ENTITIES = {
    base.BREWZILLA_TARGET_NUMBER,
    base.BREWZILLA_HEAT_UTILIZATION,
    base.BREWZILLA_PUMP_UTILIZATION,
}


def _abort_active(hass: HomeAssistant) -> dict[str, Any] | None:
    return base._abort_lockout(hass)  # type: ignore[attr-defined]


def _action_is_positive(action: Any) -> bool:
    text = str(action)
    return any(text.startswith(marker) for marker in _POSITIVE_ACTION_MARKERS)


def _has_positive_action(result: dict[str, Any]) -> bool:
    return any(_action_is_positive(action) for action in (result.get("actions") or []))


def _sanitize_positive_actions(actions: list[Any]) -> list[str]:
    return [
        f"suppressed_after_abort:{action}" if _action_is_positive(action) else str(action)
        for action in actions
    ]


def _positive_number_blocked(entity_id: str, value: float) -> bool:
    if entity_id not in _POSITIVE_NUMBER_ENTITIES:
        return False
    if entity_id == base.BREWZILLA_TARGET_NUMBER:
        return True
    try:
        return float(value) > base.UTILIZATION_TOLERANCE
    except (TypeError, ValueError):
        return True


def _record_suppressed_low_level_action(
    hass: HomeAssistant,
    *,
    action: str,
    abort: dict[str, Any],
) -> None:
    data = hass.data.setdefault("brewassistant", {})
    data["brewzilla_abort_lockout_suppressed_positive_action"] = {
        "action": action,
        "suppressed_at": dt_util.utcnow().isoformat(),
        "abort_remaining_seconds": abort.get("remaining_seconds"),
        "abort_reason": abort.get("reason"),
    }


def _blocked_result(
    snapshot: dict[str, Any],
    *,
    action_name: str,
    abort: dict[str, Any],
) -> dict[str, Any]:
    reason = str(abort.get("reason") or "BrewZilla ABORT lockout active")
    return {
        **snapshot,
        "source": "brewzilla_abort_lockout_final_guard",
        "applied": False,
        "apply_result": f"{action_name}_blocked:abort_lockout_active",
        "actions": [f"{action_name}_blocked:abort_lockout_active"],
        "target_changed": False,
        "heat_utilization_changed": False,
        "pump_utilization_changed": False,
        "heater_started": False,
        "heater_stopped": False,
        "pump_started": False,
        "pump_stopped": False,
        "pump_action_needed": False,
        "heater_action_needed": False,
        "heat_utilization_action_needed": False,
        "pump_utilization_action_needed": False,
        "can_apply_target": False,
        "orchestration_mode": "blocked",
        "abort_lockout_active": True,
        "abort_lockout_remaining_seconds": abort.get("remaining_seconds"),
        "abort_lockout_final_guard_active": True,
        "abort_lockout_blocked_action": action_name,
        "mash_in_resume_allowed": False,
        "desired_pump_on": False,
        "desired_pump_utilization": 0.0,
        "control_reason": f"{reason}; final guard blocked {action_name} before any positive BrewZilla action.",
        "executed_at": dt_util.utcnow().isoformat(),
    }


async def _block_and_enforce(
    hass: HomeAssistant,
    snapshot: dict[str, Any],
    *,
    action_name: str,
    abort: dict[str, Any],
) -> dict[str, Any]:
    result = _blocked_result(snapshot, action_name=action_name, abort=abort)
    await base._enforce_brewzilla_safe_state(  # type: ignore[attr-defined]
        hass,
        result,
        action_prefix="abort_lockout_final",
        force=False,
    )
    if len(result.get("actions") or []) > 1:
        result["applied"] = True
        result["apply_result"] = f"{action_name}_blocked_abort_lockout_enforced"
    hass.data.setdefault("brewassistant", {})["brewzilla_last_apply_result"] = result
    return result


async def _patched_call_switch(hass: HomeAssistant, service_suffix: str, entity_id: str) -> None:
    assert _ORIGINAL_CALL_SWITCH is not None
    abort = _abort_active(hass)
    if abort is not None and service_suffix in _POSITIVE_SWITCH_SERVICES:
        _record_suppressed_low_level_action(
            hass,
            action=f"switch.turn_{service_suffix}:{entity_id}",
            abort=abort,
        )
        return None
    await _ORIGINAL_CALL_SWITCH(hass, service_suffix, entity_id)


async def _patched_set_number(hass: HomeAssistant, entity_id: str, value: float) -> bool:
    assert _ORIGINAL_SET_NUMBER is not None
    abort = _abort_active(hass)
    if abort is not None and _positive_number_blocked(entity_id, value):
        _record_suppressed_low_level_action(
            hass,
            action=f"number.set_value:{entity_id}:{value}",
            abort=abort,
        )
        return False
    return await _ORIGINAL_SET_NUMBER(hass, entity_id, value)


async def _patched_apply(hass: HomeAssistant) -> dict[str, Any]:
    assert _ORIGINAL_APPLY is not None

    abort = _abort_active(hass)
    if abort is not None:
        snapshot = base.build_orchestration_snapshot(hass)
        result = await _block_and_enforce(
            hass,
            snapshot,
            action_name="orchestration_apply",
            abort=abort,
        )
        await base.async_record_brewday_audit_tick(hass, brewzilla_result=result)
        return result

    result = await _ORIGINAL_APPLY(hass)

    # A user ABORT can race with an already-running orchestration tick.  If that
    # happens, immediately reassert safe state and annotate the result so the log
    # explains why a safe-down followed the original action.  Low-level wrappers
    # above also suppress positive calls that have not yet reached HA services.
    abort = _abort_active(hass)
    if abort is not None and _has_positive_action(result):
        result = {
            **result,
            "actions": _sanitize_positive_actions(result.get("actions") or []),
            "abort_lockout_final_guard_active": True,
            "abort_lockout_race_detected": True,
            "abort_lockout_positive_actions_suppressed": True,
            "control_reason": (
                f"{result.get('control_reason') or 'Direct production flow active'}; "
                "ABORT lockout became active during this action, so BrewAssistant suppressed remaining positive actions and reasserted BrewZilla safe state."
            ),
        }
        await base._enforce_brewzilla_safe_state(  # type: ignore[attr-defined]
            hass,
            result,
            action_prefix="abort_lockout_final_race",
            force=False,
        )
        hass.data.setdefault("brewassistant", {})["brewzilla_last_apply_result"] = result
        await base.async_record_brewday_audit_tick(hass, brewzilla_result=result)
    return result


async def _patched_start_mash_circulation(
    hass: HomeAssistant,
    snapshot: dict[str, Any],
    *,
    action_name: str,
) -> dict[str, Any]:
    assert _ORIGINAL_START_MASH_CIRCULATION is not None

    abort = _abort_active(hass)
    if abort is not None:
        return await _block_and_enforce(
            hass,
            snapshot,
            action_name=action_name,
            abort=abort,
        )

    result = await _ORIGINAL_START_MASH_CIRCULATION(hass, snapshot, action_name=action_name)
    abort = _abort_active(hass)
    if abort is not None and _has_positive_action(result):
        result = {
            **result,
            "actions": _sanitize_positive_actions(result.get("actions") or []),
            "abort_lockout_final_guard_active": True,
            "abort_lockout_race_detected": True,
            "abort_lockout_positive_actions_suppressed": True,
            "mash_in_resume_allowed": False,
            "control_reason": (
                f"{result.get('control_reason') or 'Operator action'}; "
                "ABORT lockout became active during mash circulation start, so BrewAssistant suppressed remaining positive actions and reasserted safe state."
            ),
        }
        await base._enforce_brewzilla_safe_state(  # type: ignore[attr-defined]
            hass,
            result,
            action_prefix="abort_lockout_final_race",
            force=False,
        )
        hass.data.setdefault("brewassistant", {})["brewzilla_last_apply_result"] = result
    return result


def install_abort_lockout_final_guard() -> None:
    """Install final ABORT lockout checks after other BrewZilla guards."""
    global _INSTALLED, _ORIGINAL_APPLY, _ORIGINAL_START_MASH_CIRCULATION, _ORIGINAL_CALL_SWITCH, _ORIGINAL_SET_NUMBER
    if _INSTALLED:
        return

    _ORIGINAL_APPLY = base.async_apply_brewzilla_target_if_allowed
    _ORIGINAL_START_MASH_CIRCULATION = mash_in_gate._start_mash_circulation
    _ORIGINAL_CALL_SWITCH = base._call_switch  # type: ignore[attr-defined]
    _ORIGINAL_SET_NUMBER = base._set_number  # type: ignore[attr-defined]
    base.async_apply_brewzilla_target_if_allowed = _patched_apply
    mash_in_gate._start_mash_circulation = _patched_start_mash_circulation
    base._call_switch = _patched_call_switch  # type: ignore[attr-defined]
    base._set_number = _patched_set_number  # type: ignore[attr-defined]
    _INSTALLED = True
