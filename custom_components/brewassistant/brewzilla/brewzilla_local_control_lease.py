"""BrewZilla local-control lease.

BrewZilla is a local temperature controller. BA should normally send a target and
a profile once per Brewfather step, then let BrewZilla regulate locally while BA
observes. This wrapper prevents BA from re-commanding heat/pump every tick while
the same step/target profile is already leased to BrewZilla.
"""

from __future__ import annotations

from typing import Any

from homeassistant.util import dt as dt_util

from . import brewzilla_orchestration as base

_BASE_BUILD = None
_BASE_APPLY = None
_INSTALLED = False
STORE = "brewzilla_local_control_lease"
LEASE_MAX_AGE_SECONDS = 4 * 60 * 60

_SETUP_ACTION_PREFIXES = (
    "set_target:",
    "set_heat_utilization:",
    "set_pump_utilization:",
    "heater_on",
    "pump_on",
    "ba_owned_reassert_heat_utilization:",
    "ba_owned_reassert_pump_utilization:",
)
_CLEAR_ACTION_PREFIXES = (
    "abort_",
    "abort_lockout_",
    "no_positive_gate_",
    "stale_rcl_",
)


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _store(hass) -> dict[str, Any]:
    return hass.data.setdefault("brewassistant", {}).setdefault(STORE, {})


def _age_seconds(raw: Any) -> int | None:
    if not raw:
        return None
    parsed = dt_util.parse_datetime(str(raw))
    if parsed is None:
        return None
    return max(0, int((dt_util.utcnow() - dt_util.as_utc(parsed)).total_seconds()))


def _runtime_active(snapshot: dict[str, Any]) -> bool:
    return bool(
        base._runtime_active(str(snapshot.get("brewday_state") or "idle"))
        and not snapshot.get("completed_runtime")
        and not snapshot.get("abort_lockout_active")
    )


def _step_signature(snapshot: dict[str, Any]) -> str:
    target = _num(snapshot.get("requested_target"))
    target_text = "none" if target is None else f"{target:.1f}"
    return "|".join(
        str(part or "")
        for part in (
            snapshot.get("runtime_source"),
            snapshot.get("runtime_stage"),
            snapshot.get("runtime_step"),
            snapshot.get("runtime_raw_step_name"),
            snapshot.get("runtime_resolved_step_index"),
            target_text,
        )
    )


def _lease_active(hass, snapshot: dict[str, Any]) -> tuple[dict[str, Any] | None, int | None, bool]:
    lease = _store(hass).get("lease")
    if not isinstance(lease, dict):
        return None, None, False
    age = _age_seconds(lease.get("created_at"))
    requested = _num(snapshot.get("requested_target"))
    target = _num(lease.get("target"))
    active = bool(
        _runtime_active(snapshot)
        and age is not None
        and age <= LEASE_MAX_AGE_SECONDS
        and requested is not None
        and target is not None
        and abs(requested - target) <= base.TARGET_SYNC_TOLERANCE
        and lease.get("step_signature") == _step_signature(snapshot)
    )
    return lease, age, active


def _has_prefix(actions: list[Any], prefixes: tuple[str, ...]) -> bool:
    for action in actions:
        text = str(action)
        if any(text.startswith(prefix) for prefix in prefixes):
            return True
    return False


def _action_needed(snapshot: dict[str, Any]) -> bool:
    return bool(
        snapshot.get("target_sync_needed")
        or snapshot.get("heater_action_needed")
        or snapshot.get("heater_stop_needed")
        or snapshot.get("pump_action_needed")
        or snapshot.get("pump_stop_needed")
        or snapshot.get("heat_utilization_action_needed")
        or snapshot.get("pump_utilization_action_needed")
        or snapshot.get("completion_stop_needed")
        or snapshot.get("completion_pump_stop_needed")
    )


def _apply_lease(hass, snapshot: dict[str, Any]) -> dict[str, Any]:
    out = dict(snapshot)
    lease, age, active = _lease_active(hass, out)
    out.update(
        {
            "local_control_lease_active": active,
            "local_control_lease_age_seconds": age,
            "local_control_lease_max_age_seconds": LEASE_MAX_AGE_SECONDS,
            "local_control_lease_step_signature": lease.get("step_signature") if lease else None,
            "local_control_lease_target": lease.get("target") if lease else None,
            "local_control_lease_heat_utilization": lease.get("heat_utilization") if lease else None,
            "local_control_lease_pump_utilization": lease.get("pump_utilization") if lease else None,
        }
    )

    if not active:
        return out

    # BrewZilla has already received the target/profile for this step. During the
    # lease BA observes instead of repeatedly toggling the same command surface.
    out.update(
        {
            "target_sync_needed": False,
            "heater_action_needed": False,
            "heater_stop_needed": False,
            "pump_action_needed": False,
            "pump_stop_needed": False,
            "heat_utilization_action_needed": False,
            "pump_utilization_action_needed": False,
            "ba_owned_reassert_action_needed": False,
            "can_apply_target": False,
            "orchestration_mode": "local-control",
            "control_reason": (
                "BrewZilla local-control lease active; target/profile already sent. "
                "BA is observing while BrewZilla regulates locally."
            ),
        }
    )
    return out


def build_orchestration_snapshot(hass) -> dict[str, Any]:
    assert _BASE_BUILD is not None
    return _apply_lease(hass, _BASE_BUILD(hass))


async def async_apply_brewzilla_target_if_allowed(hass) -> dict[str, Any]:
    assert _BASE_APPLY is not None
    result = await _BASE_APPLY(hass)
    actions = list(result.get("actions") or [])
    store = _store(hass)

    if (
        not _runtime_active(result)
        or result.get("completed_runtime")
        or result.get("abort_lockout_active")
        or _has_prefix(actions, _CLEAR_ACTION_PREFIXES)
    ):
        if store.get("lease"):
            store["previous_lease"] = store.get("lease")
        store["lease"] = None
        store["cleared_at"] = dt_util.utcnow().isoformat()
        store["clear_reason"] = result.get("apply_result") or "runtime_not_active"
        return result

    if result.get("applied") and _has_prefix(actions, _SETUP_ACTION_PREFIXES):
        target = _num(result.get("applied_target_value") or result.get("requested_target"))
        lease = {
            "created_at": dt_util.utcnow().isoformat(),
            "updated_at": dt_util.utcnow().isoformat(),
            "step_signature": _step_signature(result),
            "target": target,
            "heat_utilization": result.get("desired_heat_utilization"),
            "pump_utilization": result.get("desired_pump_utilization"),
            "desired_heater_on": result.get("desired_heater_on"),
            "desired_pump_on": result.get("desired_pump_on"),
            "runtime_stage": result.get("runtime_stage"),
            "runtime_step": result.get("runtime_step"),
            "runtime_resolved_step_index": result.get("runtime_resolved_step_index"),
            "actions": actions,
            "apply_result": result.get("apply_result"),
        }
        store["lease"] = lease
        result["local_control_lease_created"] = True
        result["local_control_lease_target"] = target
        result["local_control_lease_step_signature"] = lease["step_signature"]

    return result


def install_local_control_lease() -> None:
    global _BASE_BUILD, _BASE_APPLY, _INSTALLED
    if _INSTALLED:
        return
    _BASE_BUILD = base.build_orchestration_snapshot
    _BASE_APPLY = base.async_apply_brewzilla_target_if_allowed
    base.build_orchestration_snapshot = build_orchestration_snapshot
    base.async_apply_brewzilla_target_if_allowed = async_apply_brewzilla_target_if_allowed
    _INSTALLED = True
