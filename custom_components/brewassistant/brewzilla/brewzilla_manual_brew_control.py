"""Manual Brew operator control guard for BrewZilla.

Manual Brew is operator-led. Existing BrewAssistant control switches become
real ownership gates while the normalized runtime source is ``Manual Brewday``:

* Manual target override ON -> the operator owns the desired target setpoint.
* Allow heater control OFF -> the operator owns heater state and heat utilization.
* Allow pump control OFF -> the operator owns pump state and pump utilization.

Operator-owned numeric values are BrewAssistant setpoints, separate from the
RAPT/BrewZilla readback entities. The normal orchestration layer transports and
reasserts those setpoints until device readback matches them.

The guard is installed last in the normal control-decision chain. It therefore
wins over automatic strategy/lease decisions, while an already blocked safety
state or ABORT remains untouched and may still force BrewZilla safe.
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

MANUAL_TARGET_SETPOINT = "number.brewassistant_brewzilla_manual_target_temperature"
MANUAL_HEAT_SETPOINT = "number.brewassistant_brewzilla_manual_heat_utilization"
MANUAL_PUMP_SETPOINT = "number.brewassistant_brewzilla_manual_pump_utilization"


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


def _float_state(hass, entity_id: str) -> float | None:
    state = _state(hass, entity_id)
    if state is None or str(state.state).lower() in {"unknown", "unavailable", "none", ""}:
        return None
    try:
        return float(str(state.state).replace(",", "."))
    except (TypeError, ValueError):
        return None


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

    manual_target = _float_state(hass, MANUAL_TARGET_SETPOINT)
    manual_heat = _float_state(hass, MANUAL_HEAT_SETPOINT)
    manual_pump = _float_state(hass, MANUAL_PUMP_SETPOINT)

    target_override = bool(
        active
        and _switch_on(hass, MANUAL_TARGET_OVERRIDE, False)
        and manual_target is not None
    )
    heater_auto = _switch_on(hass, ALLOW_HEATER_CONTROL, False) if active else True
    pump_auto = _switch_on(hass, ALLOW_PUMP_CONTROL, False) if active else True
    blocked = str(out.get("orchestration_mode") or "") == "blocked"

    out.update(
        {
            "manual_brew_control_active": active,
            "manual_target_override_active": target_override,
            "manual_heater_auto_allowed": heater_auto,
            "manual_pump_auto_allowed": pump_auto,
            "manual_heat_override_active": bool(active and not heater_auto),
            "manual_pump_override_active": bool(active and not pump_auto),
            "manual_control_safety_override_active": bool(active and blocked),
            "manual_target_setpoint": manual_target,
            "manual_heat_utilization_setpoint": manual_heat,
            "manual_pump_utilization_setpoint": manual_pump,
            "manual_control_target_entity": MANUAL_TARGET_SETPOINT,
            "manual_control_heat_utilization_entity": MANUAL_HEAT_SETPOINT,
            "manual_control_pump_utilization_entity": MANUAL_PUMP_SETPOINT,
            "manual_control_target_device_entity": base.BREWZILLA_TARGET_NUMBER,
            "manual_control_heat_utilization_device_entity": base.BREWZILLA_HEAT_UTILIZATION,
            "manual_control_pump_utilization_device_entity": base.BREWZILLA_PUMP_UTILIZATION,
        }
    )

    if not active:
        return out

    # Safety/freshness guards have already evaluated before this final operator
    # gate. A blocked snapshot is therefore deliberately left untouched.
    if blocked:
        return out

    # The Manual Brew adapter has already replaced requested_target with the
    # operator-owned BA setpoint. Recompute target reconciliation here, after
    # normal lease/advice guards, so those guards cannot erase operator intent.
    # Safety/ABORT still wins because blocked snapshots return above.
    if target_override:
        out["requested_target"] = manual_target
        out["requested_target_source"] = "manual_operator_setpoint"
        applied_target = out.get("applied_target")
        try:
            applied_target = float(applied_target) if applied_target is not None else None
        except (TypeError, ValueError):
            applied_target = None
        if applied_target is None:
            out["target_delta"] = None
            out["target_sync_needed"] = True
        else:
            target_delta = round(float(manual_target) - applied_target, 2)
            out["target_delta"] = target_delta
            out["target_sync_needed"] = abs(target_delta) > base.TARGET_SYNC_TOLERANCE

    # Manual heat/pump ownership means BA must not decide ON/OFF state, but the
    # orchestration transport still applies and reasserts the operator's numeric
    # utilization setpoint against RAPT/BrewZilla readback.
    if not heater_auto:
        out["desired_heat_utilization"] = manual_heat
        out["heat_utilization_action_needed"] = base._utilization_action_needed(
            out.get("heat_utilization"),
            manual_heat,
        )
        out["heater_action_needed"] = False
        out["heater_stop_needed"] = False
        out["ba_owned_desired_heat_utilization"] = None

    if not pump_auto:
        out["desired_pump_utilization"] = manual_pump
        out["pump_utilization_action_needed"] = base._utilization_action_needed(
            out.get("pump_utilization"),
            manual_pump,
        )
        out["pump_action_needed"] = False
        out["pump_stop_needed"] = False
        out["ba_owned_desired_pump_utilization"] = None

    # Recalculate the advice-owned reassert diagnostic after operator channels
    # have been removed from BA automation ownership.
    out["ba_owned_reassert_action_needed"] = bool(
        out.get("ba_owned_control_active")
        and (
            (
                heater_auto
                and out.get("ba_owned_desired_heat_utilization") is not None
                and out.get("heat_utilization_action_needed")
            )
            or (
                pump_auto
                and out.get("ba_owned_desired_pump_utilization") is not None
                and out.get("pump_utilization_action_needed")
            )
        )
    )

    action_needed = _remaining_action_needed(out)
    out["can_apply_target"] = action_needed

    if not action_needed:
        out["orchestration_mode"] = "manual-control"
        out["control_reason"] = (
            "Manual Brew operator setpoints match BrewZilla; BA is observing."
        )
    elif target_override or not heater_auto or not pump_auto:
        out["orchestration_mode"] = "direct-control"
        out["control_reason"] = (
            "Manual Brew operator owns selected setpoints; BA is transporting "
            "and reasserting them to BrewZilla."
        )

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
