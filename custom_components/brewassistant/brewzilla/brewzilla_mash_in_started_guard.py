"""Guard/apply bridge for the two-step BrewZilla mash-in flow."""

from __future__ import annotations

from typing import Any

from homeassistant.util import dt as dt_util

from . import brewzilla_orchestration as base

_BASE_APPLY = None
_INSTALLED = False

MAX_MASH_IN_STARTED_HEAT_UTILIZATION = 15.0


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _allowed(snapshot: dict[str, Any]) -> bool:
    """Return true when the mash-in-started anti-drop flow may apply."""
    state = str(snapshot.get("brewday_state") or "idle").lower()
    if state not in {"live", "running", "paused", "awaiting_snapshot", "prepared", "awaiting_confirm"}:
        return False
    if not snapshot.get("mash_in_started_hold_active"):
        return False
    if snapshot.get("completed_runtime") or snapshot.get("abort_lockout_active"):
        return False
    if snapshot.get("no_positive_control_gate_active") or snapshot.get("rcl_freshness_guard_blocking"):
        return False
    if snapshot.get("boil_stage"):
        return False

    target = _num(snapshot.get("requested_target"))
    current = _num(snapshot.get("current_temperature"))
    if target is None or current is None:
        return False

    desired_heat = _num(snapshot.get("desired_heat_utilization"))
    desired_pump = _num(snapshot.get("desired_pump_utilization"))
    if desired_heat is not None and desired_heat > MAX_MASH_IN_STARTED_HEAT_UTILIZATION:
        return False
    if desired_pump is not None and desired_pump > base.UTILIZATION_TOLERANCE:
        return False
    if snapshot.get("desired_pump_on") is True:
        return False

    return bool(
        snapshot.get("target_sync_needed")
        or snapshot.get("heater_action_needed")
        or snapshot.get("heater_stop_needed")
        or snapshot.get("pump_stop_needed")
        or snapshot.get("heat_utilization_action_needed")
        or snapshot.get("pump_utilization_action_needed")
    )


async def _apply_mash_in_started(hass, snapshot: dict[str, Any]) -> dict[str, Any]:
    actions: list[str] = []
    target_changed = False
    requested = _num(snapshot.get("requested_target"))
    if snapshot.get("target_sync_needed") and requested is not None:
        target_value = round(requested, 1)
        if await base._set_number(hass, base.BREWZILLA_TARGET_NUMBER, target_value):
            target_changed = True
            actions.append(f"mash_in_started_set_target:{target_value}")

    heat_utilization_changed = False
    desired_heat = _num(snapshot.get("desired_heat_utilization"))
    if snapshot.get("heat_utilization_action_needed") and desired_heat is not None:
        heat_value = round(min(desired_heat, MAX_MASH_IN_STARTED_HEAT_UTILIZATION), 1)
        if await base._set_number(hass, base.BREWZILLA_HEAT_UTILIZATION, heat_value):
            heat_utilization_changed = True
            actions.append(f"mash_in_started_set_heat_utilization:{heat_value}")

    pump_utilization_changed = False
    desired_pump = _num(snapshot.get("desired_pump_utilization"))
    if snapshot.get("pump_utilization_action_needed") and desired_pump is not None:
        pump_value = round(desired_pump, 1)
        if await base._set_number(hass, base.BREWZILLA_PUMP_UTILIZATION, pump_value):
            pump_utilization_changed = True
            actions.append(f"mash_in_started_set_pump_utilization:{pump_value}")

    heater_started = False
    if snapshot.get("heater_action_needed") and snapshot.get("desired_heater_on") is True:
        await base._call_switch(hass, "on", base.BREWZILLA_HEATER_SWITCH)
        heater_started = True
        actions.append("mash_in_started_heater_on")

    heater_stopped = False
    if snapshot.get("heater_stop_needed") and snapshot.get("desired_heater_on") is False:
        await base._call_switch(hass, "off", base.BREWZILLA_HEATER_SWITCH)
        heater_stopped = True
        actions.append("mash_in_started_heater_off")

    pump_stopped = False
    if snapshot.get("pump_stop_needed") and snapshot.get("desired_pump_on") is False:
        await base._call_switch(hass, "off", base.BREWZILLA_PUMP_SWITCH)
        pump_stopped = True
        actions.append("mash_in_started_pump_off")

    result = {
        **snapshot,
        "applied": bool(actions),
        "apply_result": "mash_in_started_hold_applied" if actions else "mash_in_started_hold_already_ok",
        "actions": actions,
        "target_changed": target_changed,
        "heat_utilization_changed": heat_utilization_changed,
        "pump_utilization_changed": pump_utilization_changed,
        "heater_started": heater_started,
        "heater_stopped": heater_stopped,
        "pump_started": False,
        "pump_stopped": pump_stopped,
        "executed_at": dt_util.utcnow().isoformat(),
    }
    hass.data.setdefault("brewassistant", {})["brewzilla_last_apply_result"] = result
    await base.async_record_brewday_audit_tick(hass, brewzilla_result=result)
    return result


async def async_apply_brewzilla_target_if_allowed(hass) -> dict[str, Any]:
    assert _BASE_APPLY is not None
    snapshot = base.build_orchestration_snapshot(hass)
    if _allowed(snapshot):
        return await _apply_mash_in_started(hass, snapshot)
    return await _BASE_APPLY(hass)


def install_mash_in_started_guard() -> None:
    global _BASE_APPLY, _INSTALLED
    if _INSTALLED:
        return
    _BASE_APPLY = base.async_apply_brewzilla_target_if_allowed
    base.async_apply_brewzilla_target_if_allowed = async_apply_brewzilla_target_if_allowed
    _INSTALLED = True
