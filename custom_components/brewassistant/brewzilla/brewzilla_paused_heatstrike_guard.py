"""Paused heat-strike maintenance guard for BrewZilla.

The generic paused guard is intentionally conservative: while Brewfather is
paused it blocks positive BrewZilla control and only allows safe-down.  The
pre-mash-in strike-water pause is a special supervised state.  BrewAssistant has
already latched a strike target and must be allowed to maintain it while the
operator is preparing mash-in.

This patch sits after the generic paused guard and re-opens only that narrow
case.  If the RAPT Cloud Link command surface is degraded, positive control stays
blocked.
"""

from __future__ import annotations

from typing import Any

from . import brewzilla_orchestration as base

_BASE_BUILD = None
_INSTALLED = False
UTILIZATION_TOLERANCE = 0.1


def _state(snapshot: dict[str, Any]) -> str:
    return str(snapshot.get("brewday_state") or "idle").strip().lower()


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _utilization_action_needed(current: float | None, desired: float | None) -> bool:
    return desired is not None and (current is None or abs(float(desired) - float(current)) > UTILIZATION_TOLERANCE)


def _rcl_degraded(snapshot: dict[str, Any]) -> bool:
    return bool(snapshot.get("rcl_degraded") or snapshot.get("heat_strike_rcl_degraded"))


def _paused_heat_strike_allowed(snapshot: dict[str, Any]) -> bool:
    return bool(
        _state(snapshot) == "paused"
        and snapshot.get("heat_strike_latch_active")
        and snapshot.get("paused_heat_strike_maintenance_allowed")
        and not _rcl_degraded(snapshot)
        and _num(snapshot.get("heat_strike_target")) is not None
    )


def _safe_target_sync(snapshot: dict[str, Any]) -> bool:
    if not snapshot.get("target_sync_needed"):
        return False
    requested = _num(snapshot.get("requested_target"))
    target_delta = _num(snapshot.get("target_delta"))
    strike_target = _num(snapshot.get("heat_strike_target"))
    if requested is None or target_delta is None:
        return False
    if strike_target is None:
        return target_delta >= 0
    return bool(target_delta >= 0 or requested >= strike_target - base.TARGET_SYNC_TOLERANCE)


def _apply_paused_heatstrike_guard(snapshot: dict[str, Any]) -> dict[str, Any]:
    out = dict(snapshot)

    if _state(out) != "paused" or out.get("completed_runtime"):
        out["paused_heatstrike_guard_active"] = False
        return out

    out["paused_heatstrike_guard_active"] = True

    if _rcl_degraded(out):
        out.update(
            {
                "paused_heatstrike_guard_mode": "rcl_degraded_block",
                "target_sync_needed": False,
                "heating_needed": False,
                "heater_action_needed": False,
                "pump_action_needed": False,
                "heat_utilization_action_needed": False,
                "pump_utilization_action_needed": False,
                "can_apply_target": False,
                "orchestration_mode": "blocked",
                "control_reason": "Paused heat-strike guard: RCL degraded; positive control blocked. " + str(out.get("control_reason") or ""),
            }
        )
        return out

    if not _paused_heat_strike_allowed(out):
        out["paused_heatstrike_guard_mode"] = "not_heatstrike"
        return out

    desired_heat = _num(out.get("desired_heat_utilization"))
    desired_pump = _num(out.get("desired_pump_utilization"))
    heat = _num(out.get("heat_utilization"))
    pump = _num(out.get("pump_utilization"))
    heater_on = bool(out.get("heater_on"))
    pump_on = bool(out.get("pump_on"))
    desired_heater_on = bool(out.get("desired_heater_on"))
    desired_pump_on = bool(out.get("desired_pump_on"))

    heat_util_needed = _utilization_action_needed(heat, desired_heat)
    pump_util_needed = _utilization_action_needed(pump, desired_pump)
    heater_action_needed = bool(desired_heater_on and not heater_on)
    heater_stop_needed = bool(desired_heater_on is False and heater_on)
    pump_action_needed = bool(desired_pump_on and not pump_on)
    pump_stop_needed = bool(desired_pump_on is False and pump_on)
    target_sync_needed = _safe_target_sync(out)
    action_needed = bool(
        target_sync_needed
        or heat_util_needed
        or pump_util_needed
        or heater_action_needed
        or heater_stop_needed
        or pump_action_needed
        or pump_stop_needed
    )

    out.update(
        {
            "paused_heatstrike_guard_mode": "maintenance_allowed",
            "target_sync_needed": target_sync_needed,
            "heat_utilization_action_needed": heat_util_needed,
            "pump_utilization_action_needed": pump_util_needed,
            "heater_action_needed": heater_action_needed,
            "heater_stop_needed": heater_stop_needed,
            "pump_action_needed": pump_action_needed,
            "pump_stop_needed": pump_stop_needed,
            "can_apply_target": bool(out.get("connected") and action_needed and not out.get("abort_lockout_active")),
            "orchestration_mode": "direct-control" if action_needed else "monitor",
            "control_reason": "Paused heat-strike guard: allowing latched pre-mash-in strike maintenance. " + str(out.get("control_reason") or ""),
        }
    )
    return out


def build_orchestration_snapshot(hass) -> dict[str, Any]:
    assert _BASE_BUILD is not None
    return _apply_paused_heatstrike_guard(_BASE_BUILD(hass))


def install_paused_heatstrike_guard() -> None:
    global _BASE_BUILD, _INSTALLED
    if _INSTALLED:
        return
    _BASE_BUILD = base.build_orchestration_snapshot
    base.build_orchestration_snapshot = build_orchestration_snapshot
    _INSTALLED = True
