"""BA-owned BrewZilla utilization overlay for orchestration."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from ..brewday.brewday_audit import async_record_brewday_audit_tick
from . import brewzilla_orchestration as _base
from .brewzilla_owned_control import clear_owned_control, get_owned_control

_BASE_BUILD_ORCHESTRATION_SNAPSHOT = _base.build_orchestration_snapshot
_BASE_APPLY_BREWZILLA_TARGET_IF_ALLOWED = _base.async_apply_brewzilla_target_if_allowed

BREWZILLA_HEAT_UTILIZATION = _base.BREWZILLA_HEAT_UTILIZATION
BREWZILLA_PUMP_UTILIZATION = _base.BREWZILLA_PUMP_UTILIZATION
UTILIZATION_TOLERANCE = _base.UTILIZATION_TOLERANCE

_INSTALLED = False


def _utilization_action_needed(current: float | None, desired: float | None) -> bool:
    if desired is None:
        return False
    if current is None:
        return True
    return abs(float(desired) - float(current)) > UTILIZATION_TOLERANCE


def _owned_control_overlay(hass: HomeAssistant, snapshot: dict[str, Any]) -> dict[str, Any]:
    runtime_state = str(snapshot.get("brewday_state") or "idle")
    runtime_active = _base._runtime_active(runtime_state)
    completed_runtime = bool(snapshot.get("completed_runtime"))
    abort_lockout_active = bool(snapshot.get("abort_lockout_active"))

    if abort_lockout_active:
        owned = clear_owned_control(hass, reason="abort_lockout")
    elif completed_runtime:
        owned = clear_owned_control(hass, reason="completed_runtime")
    else:
        owned = get_owned_control(hass)

    owned_active = bool(
        owned.get("active")
        and runtime_active
        and not completed_runtime
        and not abort_lockout_active
    )
    owned_heat = owned.get("desired_heat_utilization") if owned_active else None
    owned_pump = owned.get("desired_pump_utilization") if owned_active else None

    desired_heat = owned_heat if owned_heat is not None else snapshot.get("desired_heat_utilization")
    desired_pump = owned_pump if owned_pump is not None else snapshot.get("desired_pump_utilization")

    heat_needed = _utilization_action_needed(snapshot.get("heat_utilization"), desired_heat)
    pump_needed = _utilization_action_needed(snapshot.get("pump_utilization"), desired_pump)
    owned_action_needed = bool(owned_active and (heat_needed or pump_needed))
    can_reassert = bool(
        snapshot.get("connected")
        and runtime_active
        and not completed_runtime
        and not abort_lockout_active
    )

    overlaid = {
        **snapshot,
        "desired_heat_utilization": desired_heat,
        "desired_pump_utilization": desired_pump,
        "ba_owned_control_active": owned_active,
        "ba_owned_control_source": owned.get("source"),
        "ba_owned_control_recommendation_id": owned.get("recommendation_id"),
        "ba_owned_desired_heat_utilization": owned_heat,
        "ba_owned_desired_pump_utilization": owned_pump,
        "ba_owned_control_created_at": owned.get("created_at"),
        "ba_owned_control_updated_at": owned.get("updated_at"),
        "ba_owned_control_cleared_at": owned.get("cleared_at"),
        "ba_owned_control_clear_reason": owned.get("clear_reason"),
        "ba_owned_reassert_action_needed": owned_action_needed,
        "heat_utilization_action_needed": bool(
            snapshot.get("heat_utilization_action_needed") or heat_needed
        ),
        "pump_utilization_action_needed": bool(
            snapshot.get("pump_utilization_action_needed") or pump_needed
        ),
    }

    if owned_action_needed and can_reassert:
        overlaid["can_apply_target"] = True
        overlaid["orchestration_mode"] = "direct-control"
        overlaid["control_reason"] = "BA-owned Brewday Advice utilization should be reasserted"
        overlaid["rapt_critical_refresh_recommended"] = True
    elif owned_action_needed:
        overlaid["control_reason"] = (
            "BA-owned Brewday Advice utilization waiting for safe reassert conditions"
        )

    return overlaid


def build_orchestration_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    return _owned_control_overlay(hass, _BASE_BUILD_ORCHESTRATION_SNAPSHOT(hass))


async def _call_base_apply_without_overlay(hass: HomeAssistant) -> dict[str, Any]:
    current_build = _base.build_orchestration_snapshot
    _base.build_orchestration_snapshot = _BASE_BUILD_ORCHESTRATION_SNAPSHOT
    try:
        return await _BASE_APPLY_BREWZILLA_TARGET_IF_ALLOWED(hass)
    finally:
        _base.build_orchestration_snapshot = current_build


async def _set_owned_utilization_if_needed(
    hass: HomeAssistant,
    *,
    snapshot: dict[str, Any],
    entity_id: str,
    kind: str,
    desired_value: Any,
    actions: list[str],
) -> bool:
    if desired_value is None:
        return False
    current = snapshot.get(f"{kind}_utilization")
    if not _utilization_action_needed(current, float(desired_value)):
        return False

    value = round(float(desired_value), 1)
    if await _base._set_number(hass, entity_id, value):
        actions.append(f"ba_owned_reassert_{kind}_utilization:{value}")
        return True
    actions.append(f"ba_owned_reassert_{kind}_utilization_missing:{entity_id}")
    return False


async def async_apply_brewzilla_target_if_allowed(hass: HomeAssistant) -> dict[str, Any]:
    snapshot = build_orchestration_snapshot(hass)
    if not snapshot.get("ba_owned_reassert_action_needed"):
        return await _call_base_apply_without_overlay(hass)

    base_result = await _call_base_apply_without_overlay(hass)
    actions = list(base_result.get("actions") or [])

    heat_changed = await _set_owned_utilization_if_needed(
        hass,
        snapshot=snapshot,
        entity_id=BREWZILLA_HEAT_UTILIZATION,
        kind="heat",
        desired_value=snapshot.get("ba_owned_desired_heat_utilization"),
        actions=actions,
    )
    pump_changed = await _set_owned_utilization_if_needed(
        hass,
        snapshot=snapshot,
        entity_id=BREWZILLA_PUMP_UTILIZATION,
        kind="pump",
        desired_value=snapshot.get("ba_owned_desired_pump_utilization"),
        actions=actions,
    )

    applied = bool(base_result.get("applied") or heat_changed or pump_changed)
    result = {
        **base_result,
        **snapshot,
        "applied": applied,
        "apply_result": "direct_applied" if applied else "no_action_needed",
        "heat_utilization_changed": bool(base_result.get("heat_utilization_changed") or heat_changed),
        "pump_utilization_changed": bool(base_result.get("pump_utilization_changed") or pump_changed),
        "actions": actions,
        "executed_at": dt_util.utcnow().isoformat(),
    }
    hass.data.setdefault("brewassistant", {})["brewzilla_last_apply_result"] = result
    await async_record_brewday_audit_tick(hass, brewzilla_result=result)
    return result


def install_owned_orchestration_patch() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _base.build_orchestration_snapshot = build_orchestration_snapshot
    _base.async_apply_brewzilla_target_if_allowed = async_apply_brewzilla_target_if_allowed
    _INSTALLED = True
