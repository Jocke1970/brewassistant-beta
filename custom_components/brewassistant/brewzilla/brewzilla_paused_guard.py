"""Paused runtime guard for BrewZilla."""

from __future__ import annotations

from typing import Any

from homeassistant.util import dt as dt_util

from . import brewzilla_orchestration as base

_BASE_APPLY = None
_INSTALLED = False

PAUSED_HOLD_MAINTAIN_MAX_HEAT_UTILIZATION = 15.0
PAUSED_HOLD_MAINTAIN_MAX_PUMP_UTILIZATION = 80.0
PAUSED_HOLD_MAINTAIN_MAX_BELOW_TARGET_C = 2.0


def _paused(s: dict[str, Any]) -> bool:
    return str(s.get("brewday_state") or "idle").lower() == "paused"


def _num(v: Any) -> float | None:
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


def _zero(v: Any) -> bool:
    n = _num(v)
    return bool(n is not None and n <= base.UTILIZATION_TOLERANCE)


def _positive(v: Any) -> bool:
    n = _num(v)
    return bool(n is not None and n > base.UTILIZATION_TOLERANCE)


def _needed(s: dict[str, Any]) -> bool:
    if not _paused(s) or s.get("completed_runtime"):
        return False
    return bool(
        s.get("heater_stop_needed")
        or s.get("pump_stop_needed")
        or (s.get("heat_utilization_action_needed") and _zero(s.get("desired_heat_utilization")))
        or (s.get("pump_utilization_action_needed") and _zero(s.get("desired_pump_utilization")))
    )


def _paused_hold_maintenance_allowed(s: dict[str, Any]) -> bool:
    """Allow narrow temperature maintenance during paused Brewfather mash holds.

    Brewfather can report a mash hold as paused while the brewer still wants the
    kettle to maintain the already-applied hold target.  Full positive control is
    still blocked while paused; this exception only permits small hold/recovery
    utilization changes and circulation when the target is already synced.
    """
    if not _paused(s) or s.get("completed_runtime") or s.get("abort_lockout_active"):
        return False
    if s.get("rcl_freshness_guard_blocking"):
        return False
    if s.get("target_sync_needed") or s.get("paused_target_rewind_blocked"):
        return False
    if s.get("mash_in_heat_strategy_active") or s.get("boil_stage"):
        return False
    if not s.get("mash_hold_strategy_active"):
        return False
    if s.get("mash_in_gate_pending") or s.get("mash_in_gate_latched"):
        return False

    requested = _num(s.get("requested_target"))
    applied = _num(s.get("applied_target"))
    current = _num(s.get("current_temperature"))
    if requested is None or applied is None:
        return False
    if abs(requested - applied) > base.TARGET_SYNC_TOLERANCE:
        return False

    desired_heat = _num(s.get("desired_heat_utilization"))
    desired_pump = _num(s.get("desired_pump_utilization"))
    if desired_heat is not None and desired_heat > PAUSED_HOLD_MAINTAIN_MAX_HEAT_UTILIZATION:
        return False
    if desired_pump is not None and desired_pump > PAUSED_HOLD_MAINTAIN_MAX_PUMP_UTILIZATION:
        return False

    if _positive(desired_heat):
        if current is None:
            return False
        if requested - current > PAUSED_HOLD_MAINTAIN_MAX_BELOW_TARGET_C:
            return False

    return bool(
        s.get("heater_action_needed")
        or s.get("pump_action_needed")
        or s.get("heater_stop_needed")
        or s.get("pump_stop_needed")
        or s.get("heat_utilization_action_needed")
        or s.get("pump_utilization_action_needed")
    )


async def _apply(hass, s: dict[str, Any]) -> dict[str, Any]:
    actions: list[str] = []
    if s.get("heat_utilization_action_needed") and _zero(s.get("desired_heat_utilization")):
        if await base._set_number(hass, base.BREWZILLA_HEAT_UTILIZATION, 0):
            actions.append("paused_heat_zero")
    if s.get("heater_stop_needed"):
        await base._call_switch(hass, "off", base.BREWZILLA_HEATER_SWITCH)
        actions.append("paused_heater_off")
    if s.get("pump_utilization_action_needed") and _zero(s.get("desired_pump_utilization")):
        if await base._set_number(hass, base.BREWZILLA_PUMP_UTILIZATION, 0):
            actions.append("paused_pump_zero")
    if s.get("pump_stop_needed"):
        await base._call_switch(hass, "off", base.BREWZILLA_PUMP_SWITCH)
        actions.append("paused_pump_off")
    result = {
        **s,
        "applied": bool(actions),
        "apply_result": "paused_down_applied" if actions else "paused_down_already_ok",
        "actions": actions,
        "target_changed": False,
        "heater_started": False,
        "pump_started": False,
        "paused_down_control_allowed": True,
        "paused_up_control_blocked": True,
        "executed_at": dt_util.utcnow().isoformat(),
    }
    hass.data.setdefault("brewassistant", {})["brewzilla_last_apply_result"] = result
    await base.async_record_brewday_audit_tick(hass, brewzilla_result=result)
    return result


async def _apply_hold_maintenance(hass, s: dict[str, Any]) -> dict[str, Any]:
    actions: list[str] = []
    desired_heat = _num(s.get("desired_heat_utilization"))
    desired_pump = _num(s.get("desired_pump_utilization"))

    heat_utilization_changed = False
    if s.get("heat_utilization_action_needed") and desired_heat is not None:
        heat_value = round(min(desired_heat, PAUSED_HOLD_MAINTAIN_MAX_HEAT_UTILIZATION), 1)
        if await base._set_number(hass, base.BREWZILLA_HEAT_UTILIZATION, heat_value):
            heat_utilization_changed = True
            actions.append(f"paused_hold_set_heat_utilization:{heat_value}")

    pump_utilization_changed = False
    if s.get("pump_utilization_action_needed") and desired_pump is not None:
        pump_value = round(min(desired_pump, PAUSED_HOLD_MAINTAIN_MAX_PUMP_UTILIZATION), 1)
        if await base._set_number(hass, base.BREWZILLA_PUMP_UTILIZATION, pump_value):
            pump_utilization_changed = True
            actions.append(f"paused_hold_set_pump_utilization:{pump_value}")

    heater_started = False
    if s.get("heater_action_needed") and s.get("desired_heater_on") is True:
        await base._call_switch(hass, "on", base.BREWZILLA_HEATER_SWITCH)
        heater_started = True
        actions.append("paused_hold_heater_on")

    heater_stopped = False
    if s.get("heater_stop_needed") and s.get("desired_heater_on") is False:
        await base._call_switch(hass, "off", base.BREWZILLA_HEATER_SWITCH)
        heater_stopped = True
        actions.append("paused_hold_heater_off")

    pump_started = False
    if s.get("pump_action_needed") and s.get("desired_pump_on") is True:
        await base._call_switch(hass, "on", base.BREWZILLA_PUMP_SWITCH)
        pump_started = True
        actions.append("paused_hold_pump_on")

    pump_stopped = False
    if s.get("pump_stop_needed") and s.get("desired_pump_on") is False:
        await base._call_switch(hass, "off", base.BREWZILLA_PUMP_SWITCH)
        pump_stopped = True
        actions.append("paused_hold_pump_off")

    result = {
        **s,
        "applied": bool(actions),
        "apply_result": "paused_hold_maintenance_applied" if actions else "paused_hold_maintenance_already_ok",
        "actions": actions,
        "target_changed": False,
        "heat_utilization_changed": heat_utilization_changed,
        "pump_utilization_changed": pump_utilization_changed,
        "heater_started": heater_started,
        "heater_stopped": heater_stopped,
        "pump_started": pump_started,
        "pump_stopped": pump_stopped,
        "paused_hold_maintenance_allowed": True,
        "paused_hold_maintenance_max_heat_utilization": PAUSED_HOLD_MAINTAIN_MAX_HEAT_UTILIZATION,
        "paused_hold_maintenance_max_pump_utilization": PAUSED_HOLD_MAINTAIN_MAX_PUMP_UTILIZATION,
        "paused_hold_maintenance_max_below_target_c": PAUSED_HOLD_MAINTAIN_MAX_BELOW_TARGET_C,
        "paused_up_control_blocked": False,
        "executed_at": dt_util.utcnow().isoformat(),
    }
    hass.data.setdefault("brewassistant", {})["brewzilla_last_apply_result"] = result
    await base.async_record_brewday_audit_tick(hass, brewzilla_result=result)
    return result


async def async_apply_brewzilla_target_if_allowed(hass) -> dict[str, Any]:
    assert _BASE_APPLY is not None
    snap = base.build_orchestration_snapshot(hass)
    if _paused_hold_maintenance_allowed(snap):
        return await _apply_hold_maintenance(hass, snap)
    if _needed(snap):
        return await _apply(hass, snap)
    return await _BASE_APPLY(hass)


def install_paused_guard() -> None:
    global _BASE_APPLY, _INSTALLED
    if _INSTALLED:
        return
    _BASE_APPLY = base.async_apply_brewzilla_target_if_allowed
    base.async_apply_brewzilla_target_if_allowed = async_apply_brewzilla_target_if_allowed
    _INSTALLED = True
