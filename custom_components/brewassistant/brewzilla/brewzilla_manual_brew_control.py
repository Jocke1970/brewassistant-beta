"""Manual Brew operator control guard for BrewZilla.

Manual Brew is operator-led. Existing BrewAssistant control switches become
real ownership gates while the normalized runtime source is ``Manual Brewday``:

* Manual target override ON -> the operator owns BrewZilla target temperature.
* Allow heater control OFF -> BA must not touch heater or heat utilization.
* Allow pump control OFF -> BA must not touch pump or pump utilization.

This guard is installed before the safety/freshness guards so safety logic may
still stop hardware when required.
"""

from __future__ import annotations

from typing import Any

from . import brewzilla_orchestration as base

_BASE_BUILD = None
_BASE_APPLY = None
_INSTALLED = False

MANUAL_TARGET_OVERRIDE = "switch.brewassistant_brewzilla_manual_target_override"
ALLOW_HEATER_CONTROL = "switch.brewassistant_brewzilla_allow_heater_control"
ALLOW_PUMP_CONTROL = "switch.brewassistant_brewzilla_allow_pump_control"


def _state(hass, entity_id: str):
    direct = hass.states.get(entity_id)
    if direct is not None:
        return direct
    if "." not in entity_id:
        return None
    domain, object_id = entity_id.split(".", 1)
    suffix = f"_{object_id}"
    for candidate in hass.states.async_all(domain):
        candidate_object_id = candidate.entity_id.split(".", 1)[1]
        if candidate_object_id == object_id or candidate_object_id.endswith(suffix):
            return candidate
    return None


def _switch_on(hass, entity_id: str, default: bool = False) -> bool:
    state = _state(hass, entity_id)
    if state is None:
        return default
    return str(state.state).lower() == "on"


def _manual_runtime_active(snapshot: dict[str, Any]) -> bool:
    return bool(
        snapshot.get("runtime_source") == "Manual Brewday"
        and base._runtime_active(str(snapshot.get("brewday_state") or "idle"))
        and not snapshot.get("completed_runtime")
        and not snapshot.get("abort_lockout_active")
    )


def _remaining_action_needed(snapshot: dict[str, Any]) -> bool:
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


def _apply_manual_policy(hass, snapshot: dict[str, Any]) -> dict[str, Any]:
    out = dict(snapshot)
    active = _manual_runtime_active(out)
    target_override = active and _switch_on(hass, MANUAL_TARGET_OVERRIDE, False)
    heater_auto = _switch_on(hass, ALLOW_HEATER_CONTROL, False) if active else True
    pump_auto = _switch_on(hass, ALLOW_PUMP_CONTROL, False) if active else True

    out.update(
        {
            "manual_brew_control_active": active,
            "manual_target_override_active": target_override,
            "manual_heater_auto_allowed": heater_auto,
            "manual_pump_auto_allowed": pump_auto,
            "manual_heat_override_active": bool(active and not heater_auto),
            "manual_pump_override_active": bool(active and not pump_auto),
            "manual_control_target_entity": base.BREWZILLA_TARGET_NUMBER,
            "manual_control_heat_utilization_entity": base.BREWZILLA_HEAT_UTILIZATION,
            "manual_control_pump_utilization_entity": base.BREWZILLA_PUMP_UTILIZATION,
        }
    )

    if not active:
        return out

    # Target override is resolved in manual_brewday_adapter before the base
    # orchestration strategy is calculated. Suppress any residual target sync
    # here so BA cannot write the number back on the same coordinator tick.
    if target_override:
        out["target_sync_needed"] = False
        out["target_delta"] = 0.0
        out["requested_target_source"] = "manual_operator_override"

    # "Allow ... control" are real ownership gates in Manual Brew. When OFF,
    # the corresponding raw RCL/BrewZilla entities are operator-owned and BA is
    # deliberately hands-off. Later safety guards may still stop hardware.
    if not heater_auto:
        out["desired_heat_utilization"] = out.get("heat_utilization")
        out["heat_utilization_action_needed"] = False
        out["heater_action_needed"] = False
        out["heater_stop_needed"] = False
        out["ba_owned_desired_heat_utilization"] = None

    if not pump_auto:
        out["desired_pump_utilization"] = out.get("pump_utilization")
        out["pump_utilization_action_needed"] = False
        out["pump_action_needed"] = False
        out["pump_stop_needed"] = False
        out["ba_owned_desired_pump_utilization"] = None

    if not heater_auto or not pump_auto:
        out["ba_owned_reassert_action_needed"] = False

    action_needed = _remaining_action_needed(out)
    blocked = str(out.get("orchestration_mode") or "") == "blocked"
    out["can_apply_target"] = bool(not blocked and action_needed)

    if not action_needed and not blocked:
        out["orchestration_mode"] = "manual-control"
        out["control_reason"] = "Manual Brew operator owns selected BrewZilla controls; BA is observing."
    elif not blocked and (target_override or not heater_auto or not pump_auto):
        out["control_reason"] = "Manual Brew mixed control: operator overrides selected channels; BA controls remaining allowed channels."

    return out


def build_orchestration_snapshot(hass) -> dict[str, Any]:
    assert _BASE_BUILD is not None
    return _apply_manual_policy(hass, _BASE_BUILD(hass))


async def async_apply_brewzilla_target_if_allowed(hass) -> dict[str, Any]:
    assert _BASE_APPLY is not None
    return await _BASE_APPLY(hass)


def install_manual_brew_control_guard() -> None:
    global _BASE_BUILD, _BASE_APPLY, _INSTALLED
    if _INSTALLED:
        return
    _BASE_BUILD = base.build_orchestration_snapshot
    _BASE_APPLY = base.async_apply_brewzilla_target_if_allowed
    base.build_orchestration_snapshot = build_orchestration_snapshot
    base.async_apply_brewzilla_target_if_allowed = async_apply_brewzilla_target_if_allowed
    _INSTALLED = True
