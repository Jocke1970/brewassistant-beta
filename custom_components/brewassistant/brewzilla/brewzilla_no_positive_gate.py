"""No-positive-control runtime gate for BrewZilla.

When Brewday Runtime is not in a trustworthy active step, BA may only drive the
BrewZilla command surface toward a neutral safe state. This prevents stale
Brewfather terminal/transition snapshots from starting a new target or changing
outputs upward after Mash has ended or while BA is awaiting a fresh snapshot.
"""

from __future__ import annotations

from typing import Any

from homeassistant.util import dt as dt_util

from . import brewzilla_orchestration as base

_BASE_BUILD = None
_BASE_APPLY = None
_INSTALLED = False
_NO_POSITIVE_STATES = {"", "idle", "inactive", "unknown", "unavailable", "none", "awaiting_snapshot"}


def _state(snapshot: dict[str, Any]) -> str:
    return str(snapshot.get("brewday_state") or "idle").lower()


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _util_needs_zero(value: Any) -> bool:
    num = _num(value)
    return bool(num is not None and num > base.UTILIZATION_TOLERANCE)


def _gate_active(snapshot: dict[str, Any]) -> bool:
    state = _state(snapshot)
    return bool(
        state in _NO_POSITIVE_STATES
        or str(snapshot.get("runtime_status") or "").lower() == "inactive"
        or snapshot.get("completed_runtime")
    )


def _apply_no_positive(snapshot: dict[str, Any]) -> dict[str, Any]:
    gated = dict(snapshot)
    if not _gate_active(gated) or gated.get("abort_lockout_active"):
        gated["no_positive_control_gate_active"] = False
        return gated

    heater_on = bool(gated.get("heater_on"))
    pump_on = bool(gated.get("pump_on"))
    heat_zero_needed = _util_needs_zero(gated.get("heat_utilization"))
    pump_zero_needed = _util_needs_zero(gated.get("pump_utilization"))
    safe_down_needed = bool(heater_on or pump_on or heat_zero_needed or pump_zero_needed)
    connected = bool(gated.get("connected"))

    gated.update(
        {
            "no_positive_control_gate_active": True,
            "no_positive_control_state": _state(gated),
            "no_positive_control_safe_down_needed": safe_down_needed,
            "target_sync_needed": False,
            "heating_needed": False,
            "pump_recommended": False,
            "desired_heat_utilization": 0.0,
            "desired_pump_utilization": 0.0,
            "desired_heater_on": False,
            "desired_pump_on": False,
            "heater_action_needed": False,
            "pump_action_needed": False,
            "heater_stop_needed": heater_on,
            "pump_stop_needed": pump_on,
            "heat_utilization_action_needed": heat_zero_needed,
            "pump_utilization_action_needed": pump_zero_needed,
            "ba_owned_reassert_action_needed": False,
            "can_apply_target": connected and safe_down_needed,
            "orchestration_mode": "direct-control" if connected and safe_down_needed else "blocked",
            "control_reason": (
                "No-positive-control gate active; Brewday Runtime is not in a trusted active control state. "
                "Only safe-down BrewZilla actions are allowed."
            ),
        }
    )
    return gated


def build_orchestration_snapshot(hass) -> dict[str, Any]:
    assert _BASE_BUILD is not None
    return _apply_no_positive(_BASE_BUILD(hass))


async def async_apply_brewzilla_target_if_allowed(hass) -> dict[str, Any]:
    assert _BASE_APPLY is not None
    snapshot = base.build_orchestration_snapshot(hass)
    if snapshot.get("no_positive_control_gate_active"):
        result: dict[str, Any] = {
            **snapshot,
            "applied": False,
            "apply_result": "no_positive_control_safe_down_check",
            "actions": [],
            "target_changed": False,
            "heater_started": False,
            "pump_started": False,
            "executed_at": dt_util.utcnow().isoformat(),
        }
        if snapshot.get("no_positive_control_safe_down_needed"):
            await base._enforce_brewzilla_safe_state(
                hass,
                result,
                action_prefix="no_positive_gate",
                force=True,
            )
            result["applied"] = bool(result.get("actions"))
            result["apply_result"] = (
                "no_positive_control_safe_down_applied"
                if result.get("actions")
                else "no_positive_control_already_safe"
            )
        else:
            result["apply_result"] = "no_positive_control_already_safe"

        hass.data.setdefault("brewassistant", {})["brewzilla_last_apply_result"] = result
        await base.async_record_brewday_audit_tick(hass, brewzilla_result=result)
        return result

    return await _BASE_APPLY(hass)


def install_no_positive_gate() -> None:
    global _BASE_BUILD, _BASE_APPLY, _INSTALLED
    if _INSTALLED:
        return
    _BASE_BUILD = base.build_orchestration_snapshot
    _BASE_APPLY = base.async_apply_brewzilla_target_if_allowed
    base.build_orchestration_snapshot = build_orchestration_snapshot
    base.async_apply_brewzilla_target_if_allowed = async_apply_brewzilla_target_if_allowed
    _INSTALLED = True
