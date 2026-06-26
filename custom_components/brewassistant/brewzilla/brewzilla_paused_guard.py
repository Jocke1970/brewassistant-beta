"""Paused runtime guard for BrewZilla."""

from __future__ import annotations

from typing import Any

from homeassistant.util import dt as dt_util

from . import brewzilla_orchestration as base

_BASE_APPLY = None
_INSTALLED = False


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


def _needed(s: dict[str, Any]) -> bool:
    if not _paused(s) or s.get("completed_runtime"):
        return False
    return bool(
        s.get("heater_stop_needed")
        or s.get("pump_stop_needed")
        or (s.get("heat_utilization_action_needed") and _zero(s.get("desired_heat_utilization")))
        or (s.get("pump_utilization_action_needed") and _zero(s.get("desired_pump_utilization")))
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


async def async_apply_brewzilla_target_if_allowed(hass) -> dict[str, Any]:
    assert _BASE_APPLY is not None
    snap = base.build_orchestration_snapshot(hass)
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
