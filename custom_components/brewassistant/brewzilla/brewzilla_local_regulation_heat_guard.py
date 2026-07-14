"""Preserve BrewZilla local heat regulation while a target is active.

BrewZilla has its own thermostat/control loop once a target temperature has been
written.  BA may still adjust targets, pump settings and request RCL refreshes,
but it should not use HA/RCL heat-off commands as the normal way to regulate
mash or heat-strike temperature.  Heat-off belongs to explicit abort/completion
paths, not stale RCL or target-hold regulation.
"""

from __future__ import annotations

from typing import Any

from . import brewzilla_orchestration as base

_BASE_BUILD = None
_INSTALLED = False

_ACTIVE_TARGET_STATES = {"live", "running", "paused", "awaiting_snapshot", "prepared", "awaiting_confirm"}


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _valid_target(value: Any) -> bool:
    target = _num(value)
    return bool(target is not None and base.MIN_TARGET_TEMP <= target <= base.MAX_TARGET_TEMP)


def _target_known(snapshot: dict[str, Any]) -> bool:
    return bool(
        _valid_target(snapshot.get("applied_target"))
        or _valid_target(snapshot.get("brewzilla_device_target"))
        or (
            not snapshot.get("target_sync_needed")
            and _valid_target(snapshot.get("requested_target"))
        )
    )


def _heat_zero_requested(snapshot: dict[str, Any]) -> bool:
    desired_heat = _num(snapshot.get("desired_heat_utilization"))
    return bool(
        snapshot.get("heater_stop_needed")
        or snapshot.get("desired_heater_on") is False
        or (
            snapshot.get("heat_utilization_action_needed")
            and desired_heat is not None
            and desired_heat <= base.UTILIZATION_TOLERANCE
        )
    )


def _scope_active(snapshot: dict[str, Any]) -> bool:
    state = str(snapshot.get("brewday_state") or "idle").lower()
    return bool(
        state in _ACTIVE_TARGET_STATES
        and not snapshot.get("completed_runtime")
        and not snapshot.get("abort_lockout_active")
        and not snapshot.get("completion_stop_needed")
        and _target_known(snapshot)
    )


def _action_needed(snapshot: dict[str, Any]) -> bool:
    return bool(
        snapshot.get("target_sync_needed")
        or snapshot.get("heater_action_needed")
        or snapshot.get("pump_action_needed")
        or snapshot.get("pump_stop_needed")
        or snapshot.get("pump_utilization_action_needed")
        or (
            snapshot.get("heat_utilization_action_needed")
            and _num(snapshot.get("desired_heat_utilization")) is not None
            and _num(snapshot.get("desired_heat_utilization")) > base.UTILIZATION_TOLERANCE
        )
        or snapshot.get("ba_owned_reassert_action_needed")
    )


def _apply_guard(snapshot: dict[str, Any]) -> dict[str, Any]:
    if not _scope_active(snapshot) or not _heat_zero_requested(snapshot):
        return snapshot

    guarded = dict(snapshot)
    previous_desired_heat = _num(guarded.get("desired_heat_utilization"))
    current_heat = _num(guarded.get("heat_utilization"))
    preserved_heat_value = current_heat if current_heat is not None else previous_desired_heat
    original_reason = str(guarded.get("control_reason") or "BrewZilla local target active.")

    # Keep positive heat changes/reassertions, but never translate regulation or
    # stale-RCL decisions into heat utilization 0 or heater OFF while a local
    # BrewZilla target is active.  BrewZilla's own thermostat will cycle heating.
    if previous_desired_heat is not None and previous_desired_heat <= base.UTILIZATION_TOLERANCE:
        guarded["desired_heat_utilization"] = preserved_heat_value
        guarded["heat_utilization_action_needed"] = False
    guarded["desired_heater_on"] = True if guarded.get("heater_on") else guarded.get("desired_heater_on")
    guarded["heater_stop_needed"] = False

    action_needed = _action_needed(guarded)
    connected = bool(guarded.get("connected"))
    guarded.update(
        {
            "brewzilla_local_heat_preserve_active": True,
            "brewzilla_local_heat_preserve_reason": "target_active_brewzilla_regulates_locally",
            "brewzilla_local_heat_preserve_original_desired_heat": previous_desired_heat,
            "brewzilla_local_heat_preserve_current_heat": current_heat,
            "brewzilla_local_heat_preserve_target": _num(guarded.get("applied_target"))
            or _num(guarded.get("brewzilla_device_target"))
            or _num(guarded.get("requested_target")),
            "can_apply_target": connected and action_needed,
            "orchestration_mode": "direct-control" if connected and action_needed else "local-control",
            "control_reason": (
                f"{original_reason} BrewZilla local heat preserve: active target is known, so BA does not send heat 0% "
                "or heater OFF; BrewZilla regulates locally against its target."
            ),
        }
    )
    return guarded


def build_orchestration_snapshot(hass) -> dict[str, Any]:
    assert _BASE_BUILD is not None
    return _apply_guard(_BASE_BUILD(hass))


def install_local_regulation_heat_guard() -> None:
    """Install final heat-preservation patch for active BrewZilla targets."""
    global _BASE_BUILD, _INSTALLED
    if _INSTALLED:
        return
    _BASE_BUILD = base.build_orchestration_snapshot
    base.build_orchestration_snapshot = build_orchestration_snapshot
    _INSTALLED = True
