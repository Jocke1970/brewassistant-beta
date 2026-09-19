"""Source-scoped BrewZilla actuator boundary for BA hot-side operation.

Brewfather brewing is observer-only. Active RAPT process intent authorizes BA
control, constrained by Sparge phase and supervised operator confirmation.
A blocked command never proves outputs are physically OFF. Manual is unchanged
pending a separate audit; retain draft status until end-to-end hardware tests.
"""

from __future__ import annotations

from typing import Any

from homeassistant.util import dt as dt_util

from .. import control_policy
from ..brewday import brewday_runtime, rapt_profile_runtime
from ..brewday.brewday_operator_abort import brewday_operator_abort_snapshot
from ..const import DOMAIN
from ..supervised_apply import clear_pending_action_from_source
from . import brewzilla_learning as learning
from . import brewzilla_orchestration as base
from . import brewzilla_rapt_sparge_controller as sparge
from . import brewzilla_supervised_runtime_guard as supervised
from .brewzilla_source_authority_contract import HotSideAuthority, resolve_hot_side_authority

_INSTALLED = False
_PREVIOUS_BUILD = None
_PREVIOUS_APPLY = None
_PREVIOUS_SET = None
_PREVIOUS_SWITCH = None
_PREVIOUS_SAFE_STATE = None
_PREVIOUS_POLICY_EXECUTE = None
_PREVIOUS_LEARNING_APPLY = None
_PREVIOUS_STOP = None
_PREVIOUS_SUPERVISED_BUILD = None
FRESH_SECONDS = 90
BREWZILLA_ENTITIES = frozenset({
    base.BREWZILLA_TARGET_NUMBER, base.BREWZILLA_HEATER_SWITCH,
    base.BREWZILLA_PUMP_SWITCH, base.BREWZILLA_HEAT_UTILIZATION,
    base.BREWZILLA_PUMP_UTILIZATION,
})


def _live_authority(hass) -> tuple[HotSideAuthority, dict[str, Any]]:
    runtime = brewday_runtime.build_brewday_runtime_snapshot(hass)
    profile = rapt_profile_runtime._profile_state(hass)
    age = None
    if profile is not None:
        reported = getattr(profile, "last_reported", None) or getattr(profile, "last_updated", None)
        if reported is not None:
            age = (dt_util.utcnow() - dt_util.as_utc(reported)).total_seconds()
    valid = bool(
        profile is not None and rapt_profile_runtime._active_contract(profile)
        and profile.attributes.get("profile_contract_complete") is True
    )
    session = profile.attributes.get("profile_session_id") if profile is not None else None
    operator = brewday_operator_abort_snapshot(hass)
    authority = resolve_hot_side_authority(
        runtime.get("source"), rapt_contract_valid=valid,
        rapt_profile_active=bool(profile is not None and rapt_profile_runtime._active_contract(profile)),
        rapt_session_id=str(session).strip() if session is not None else None,
        telemetry_fresh=bool(age is not None and 0 <= age <= FRESH_SECONDS),
        operator_abort=bool(operator.get("active")),
    )
    return authority, {"runtime": runtime, "operator": operator, "age": age}


def _safe_off_allowed(authority: HotSideAuthority, context: dict[str, Any]) -> bool:
    """Only an RAPT-owned STOP or operator ABORT may bypass positive lockout."""
    runtime = context["runtime"]
    operator = context["operator"]
    rapt_stop = bool(
        runtime.get("source") == "RAPT BrewZilla Profile"
        and runtime.get("profile_stop_confirmed")
        and runtime.get("profile_stop_guard_active")
    )
    rapt_abort = bool(operator.get("active") and operator.get("source") == "RAPT BrewZilla Profile")
    return bool(rapt_stop or rapt_abort)


def _sparge_write_allowed(hass, entity: str, *, switch_action: str | None, value: float | None) -> bool:
    """Never permit a stale direct path to bypass awaiting-lift or pump safety.

    This boundary does not grant supervised approval by itself; it only rejects
    writes outside the physical phase. Direct policy-router writes are denied
    separately while Sparge is active.
    """
    state = sparge._observe(hass)
    if state.phase == "inactive":
        return True
    if entity in {base.BREWZILLA_PUMP_SWITCH, base.BREWZILLA_HEATER_SWITCH} and switch_action == "off":
        return True
    if entity in {base.BREWZILLA_HEAT_UTILIZATION, base.BREWZILLA_PUMP_UTILIZATION} and value == 0:
        return True
    if state.phase != "heat_to_boil" or not state.lift_confirmed:
        return False
    if entity == base.BREWZILLA_PUMP_SWITCH or entity == base.BREWZILLA_PUMP_UTILIZATION:
        return False  # No pump restart during Sparge, including manual/direct paths.
    if not sparge._pump_safe_for_preboil(hass) or sparge._preboil_temperature(hass) is None:
        return False
    heater, fresh = sparge._readback(hass, base.BREWZILLA_HEATER_SWITCH)
    if not fresh or heater not in {"on", "off"}:
        return False
    if entity == base.BREWZILLA_TARGET_NUMBER:
        return value is not None and 0 <= value <= sparge.PREBOIL_TARGET_C
    if entity == base.BREWZILLA_HEAT_UTILIZATION:
        return value is not None and 0 <= value <= 100
    return entity == base.BREWZILLA_HEATER_SWITCH and switch_action == "on"


def _write_allowed(hass, entity: str, *, switch_action: str | None = None, value: float | None = None) -> bool:
    if entity not in BREWZILLA_ENTITIES:
        return True
    authority, context = _live_authority(hass)
    if authority.may_write_brewzilla is True:
        return _sparge_write_allowed(hass, entity, switch_action=switch_action, value=value)
    if authority.may_write_brewzilla is None:
        return True  # Existing Manual mode; separate audit required.
    if not _safe_off_allowed(authority, context):
        return False
    if entity in {base.BREWZILLA_HEATER_SWITCH, base.BREWZILLA_PUMP_SWITCH}:
        return switch_action == "off"
    return entity in {base.BREWZILLA_HEAT_UTILIZATION, base.BREWZILLA_PUMP_UTILIZATION} and value == 0


def _observer_snapshot(snapshot: dict[str, Any], authority: HotSideAuthority) -> dict[str, Any]:
    out = dict(snapshot)
    out.update(
        hot_side_source_authority=authority.mode,
        hot_side_source_authority_reason=authority.reason,
        hot_side_actuator_writes_allowed=False,
        hot_side_outputs_physically_off_verified=False,
        target_sync_needed=False, heating_needed=False,
        heater_action_needed=False, heater_stop_needed=False,
        pump_action_needed=False, pump_stop_needed=False,
        heat_utilization_action_needed=False, pump_utilization_action_needed=False,
        completion_stop_needed=False, completion_pump_stop_needed=False,
        ba_owned_reassert_action_needed=False, can_apply_target=False,
        orchestration_mode="source-observer",
        has_pending_action=False, pending_action=None, pending_summary=None,
        control_reason=f"No BA BrewZilla commands: {authority.reason}. Device outputs are not certified OFF.",
    )
    return out


def _build(hass):
    assert _PREVIOUS_BUILD is not None
    out = _PREVIOUS_BUILD(hass)
    authority, _ = _live_authority(hass)
    if authority.may_write_brewzilla is False:
        clear_pending_action_from_source(hass, supervised.SOURCE)
        return _observer_snapshot(out, authority)
    return {**out, "hot_side_source_authority": authority.mode,
            "hot_side_source_authority_reason": authority.reason,
            "hot_side_actuator_writes_allowed": authority.may_write_brewzilla}


def _supervised_build(hass):
    assert _PREVIOUS_SUPERVISED_BUILD is not None
    out = _PREVIOUS_SUPERVISED_BUILD(hass)
    authority, _ = _live_authority(hass)
    return _observer_snapshot(out, authority) if authority.may_write_brewzilla is False else out


async def _apply(hass):
    assert _PREVIOUS_APPLY is not None
    authority, _ = _live_authority(hass)
    if authority.may_write_brewzilla is not False:
        return await _PREVIOUS_APPLY(hass)
    clear_pending_action_from_source(hass, supervised.SOURCE)
    result = {**_observer_snapshot(_PREVIOUS_BUILD(hass), authority),
              "applied": False, "apply_result": "source_authority_no_writes", "actions": []}
    hass.data.setdefault(DOMAIN, {})["brewzilla_last_apply_result"] = result
    return result


async def _set_number(hass, entity_id: str, value: float) -> bool:
    assert _PREVIOUS_SET is not None
    if not _write_allowed(hass, entity_id, value=value):
        raise PermissionError(f"BA BrewZilla number write blocked by brewing source: {entity_id}")
    return await _PREVIOUS_SET(hass, entity_id, value)


async def _call_switch(hass, service_suffix: str, entity_id: str) -> None:
    assert _PREVIOUS_SWITCH is not None
    if not _write_allowed(hass, entity_id, switch_action=service_suffix):
        raise PermissionError(f"BA BrewZilla switch write blocked by brewing source: {entity_id}")
    await _PREVIOUS_SWITCH(hass, service_suffix, entity_id)


async def _safe_state(hass, result, *, action_prefix: str, force: bool = False):
    assert _PREVIOUS_SAFE_STATE is not None
    authority, context = _live_authority(hass)
    if authority.may_write_brewzilla is False and not _safe_off_allowed(authority, context):
        result.update(safe_state_enforced=False, safe_state_ok=False,
                      safe_state_blocked_reason=authority.reason,
                      safe_state_heater_on=None, safe_state_pump_on=None)
        return
    await _PREVIOUS_SAFE_STATE(hass, result, action_prefix=action_prefix, force=force)


async def _policy_execute(hass, action):
    assert _PREVIOUS_POLICY_EXECUTE is not None
    entity = action.get("entity_id")
    if entity in BREWZILLA_ENTITIES:
        service_data = action.get("service_data") or {}
        try:
            number = float(service_data["value"]) if "value" in service_data else None
        except (TypeError, ValueError):
            number = None
        switch_action = "off" if action.get("service") == "turn_off" else "on" if action.get("service") == "turn_on" else None
        authority, _ = _live_authority(hass)
        # No direct policy-router exception to Sparge's supervised heat plan.
        if authority.mode == "rapt_controller" and sparge._observe(hass).phase != "inactive":
            allowed = False
        else:
            allowed = _write_allowed(hass, entity, switch_action=switch_action, value=number)
        if not allowed:
            return control_policy._store_policy_result(hass, {
                **action, "status": "source_authority_denied",
                "summary": "BrewZilla command refused: source or Sparge phase has no direct write authority.",
            })
    return await _PREVIOUS_POLICY_EXECUTE(hass, action)


async def _learning_apply(hass):
    """Disable direct Learning APPLY in BF observer and RAPT supervised mode.

    Learning suggestions must be converted to a supervised source-bound plan
    before RAPT may execute them. Preserve existing Manual-only behavior.
    """
    assert _PREVIOUS_LEARNING_APPLY is not None
    authority, _ = _live_authority(hass)
    if authority.mode != "manual_legacy_unresolved":
        return {"applied": False, "apply_result": "learning_apply_requires_manual_or_supervised_authority",
                "hot_side_source_authority": authority.mode}
    return await _PREVIOUS_LEARNING_APPLY(hass)


async def _rapt_stop(hass, token):
    assert _PREVIOUS_STOP is not None
    authority, context = _live_authority(hass)
    if authority.may_write_brewzilla is False and not _safe_off_allowed(authority, context):
        rapt_profile_runtime._store(hass)["last_safe_off"] = {
            "token": token, "ok": False, "actions": [],
            "reason": "source_authority_denied_no_physical_off_claim",
        }
        return
    return await _PREVIOUS_STOP(hass, token)


def install_source_authority_runtime():
    """Install last in BrewZilla chain; preserve independent cold-side control."""
    global _INSTALLED, _PREVIOUS_BUILD, _PREVIOUS_APPLY, _PREVIOUS_SET
    global _PREVIOUS_SWITCH, _PREVIOUS_SAFE_STATE, _PREVIOUS_POLICY_EXECUTE
    global _PREVIOUS_LEARNING_APPLY, _PREVIOUS_STOP, _PREVIOUS_SUPERVISED_BUILD
    if _INSTALLED:
        return
    _PREVIOUS_BUILD = base.build_orchestration_snapshot
    _PREVIOUS_APPLY = base.async_apply_brewzilla_target_if_allowed
    _PREVIOUS_SET = base._set_number
    _PREVIOUS_SWITCH = base._call_switch
    _PREVIOUS_SAFE_STATE = base._enforce_brewzilla_safe_state
    _PREVIOUS_POLICY_EXECUTE = control_policy.execute_action
    _PREVIOUS_LEARNING_APPLY = learning.async_apply_brewzilla_learning_recommendation
    _PREVIOUS_STOP = rapt_profile_runtime._async_safe_off_after_profile_stop
    _PREVIOUS_SUPERVISED_BUILD = supervised._BASE_BUILD
    if _PREVIOUS_SUPERVISED_BUILD is None:
        raise RuntimeError("Source authority must install after supervised guard")
    base.build_orchestration_snapshot = _build
    base.async_apply_brewzilla_target_if_allowed = _apply
    base._set_number = _set_number
    base._call_switch = _call_switch
    base._enforce_brewzilla_safe_state = _safe_state
    control_policy.execute_action = _policy_execute
    learning.async_apply_brewzilla_learning_recommendation = _learning_apply
    rapt_profile_runtime._async_safe_off_after_profile_stop = _rapt_stop
    supervised._BASE_BUILD = _supervised_build
    _INSTALLED = True
