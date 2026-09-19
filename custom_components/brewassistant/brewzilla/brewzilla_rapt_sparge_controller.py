"""RAPT Sparge operator-gated hot-side control for BrewAssistant.

RAPT supplies the manual process step; BA controls physical outputs. An
operator must confirm the lifted malt pipe and wort coverage before preheating.
The 95 C preboil target is a conservative ceiling, never a Boil transition.
Hardware control remains unapproved until supervised water-only validation.
"""

from __future__ import annotations

from homeassistant.util import dt as dt_util

from ..brewday import brewday_runtime, rapt_profile_runtime
from ..brewday.brewday_operator_abort import brewday_operator_abort_active
from ..const import DOMAIN
from ..supervised_apply import clear_pending_action_from_source
from . import brewzilla_orchestration as base
from . import brewzilla_phase_authority as phase_authority
from . import brewzilla_rapt_profile_control_bridge as bridge
from . import brewzilla_supervised_runtime_guard as supervised
from . import brewzilla_rapt_sparge_state as state_machine

_INSTALLED = False
_PREVIOUS_BUILD = None
_PREVIOUS_SUPERVISED_BUILD = None
_PREVIOUS_SEMANTICS = None
_PREVIOUS_PHASE_AUTHORITY = None
_PREVIOUS_PLAN_POLICY = None
STORE_KEY = "rapt_sparge_interlock"
PREBOIL_TARGET_C = 95.0
PROFILE_MAX_AGE_SECONDS = 90
OUTPUT_MAX_AGE_SECONDS = 90


def _store(hass):
    return hass.data.setdefault(DOMAIN, {})


def _readback(hass, entity_id):
    item = hass.states.get(entity_id)
    if item is None or str(item.state).strip().lower() in {"unknown", "unavailable", "none", ""}:
        return None, False
    reported = getattr(item, "last_reported", None) or getattr(item, "last_updated", None)
    if reported is None:
        return None, False
    age = (dt_util.utcnow() - dt_util.as_utc(reported)).total_seconds()
    return str(item.state).strip().lower(), 0 <= age <= OUTPUT_MAX_AGE_SECONDS


def _num(value):
    try:
        return float(value) if value is not None else None
    except (ValueError, TypeError):
        return None


def _observe(hass):
    runtime = brewday_runtime.build_brewday_runtime_snapshot(hass)
    profile = rapt_profile_runtime._profile_state(hass)
    previous = _store(hass).get(STORE_KEY)
    if not isinstance(previous, state_machine.SpargeState):
        previous = state_machine.SpargeState()  # No authorization after restart.
    reported = (getattr(profile, "last_reported", None) or getattr(profile, "last_updated", None)) if profile is not None else None
    age = (dt_util.utcnow() - dt_util.as_utc(reported)).total_seconds() if reported is not None else None
    valid = bool(profile is not None and rapt_profile_runtime._active_contract(profile)
                 and profile.attributes.get("profile_contract_complete") is True)
    current = state_machine.observe(
        previous, source=runtime.get("source"),
        profile_active=bool(profile is not None and rapt_profile_runtime._active_contract(profile)),
        contract_valid=valid,
        telemetry_fresh=bool(age is not None and 0 <= age <= PROFILE_MAX_AGE_SECONDS),
        session_id=runtime.get("profile_session_id"),
        step_id=runtime.get("profile_step_id"),
        step_number=runtime.get("profile_step_number"),
        raw_step_name=runtime.get("raw_step_name"),
        operator_abort=brewday_operator_abort_active(hass),
    )
    if current != previous:
        clear_pending_action_from_source(hass, supervised.SOURCE)
    _store(hass)[STORE_KEY] = current
    return current


def build_sparge_snapshot(hass):
    """Status is observation, never proof of physical safety without readback."""
    state = _observe(hass)
    heater, heater_fresh = _readback(hass, base.BREWZILLA_HEATER_SWITCH)
    pump, pump_fresh = _readback(hass, base.BREWZILLA_PUMP_SWITCH)
    heat, heat_fresh = _readback(hass, base.BREWZILLA_HEAT_UTILIZATION)
    pump_util, pump_util_fresh = _readback(hass, base.BREWZILLA_PUMP_UTILIZATION)
    heat_num, pump_num = _num(heat), _num(pump_util)
    safe = bool(heater == "off" and pump == "off" and heat_num is not None
                and pump_num is not None and 0 <= heat_num <= 0.1
                and 0 <= pump_num <= 0.1
                and all((heater_fresh, pump_fresh, heat_fresh, pump_util_fresh)))
    return {
        "phase": state.phase, "reason": state.reason,
        "session_id": state.session_id, "step_id": state.step_id,
        "step_number": state.step_number, "lift_confirmed": state.lift_confirmed,
        "heater_readback": heater, "pump_readback": pump,
        "heat_utilization_readback": heat_num, "pump_utilization_readback": pump_num,
        "outputs_confirmed_off": safe,
        "operator_confirmation_available": state.phase == "awaiting_lift" and safe,
        "preboil_target_c": PREBOIL_TARGET_C,
        "physical_lift_is_not_automatically_verifiable": True,
    }


def _pump_safe_for_preboil(hass):
    """Unknown/stale pump switch OR utilization is unsafe for positive heat."""
    pump, pump_fresh = _readback(hass, base.BREWZILLA_PUMP_SWITCH)
    utilization, util_fresh = _readback(hass, base.BREWZILLA_PUMP_UTILIZATION)
    parsed = _num(utilization)
    return bool(pump_fresh and util_fresh and pump == "off"
                and parsed is not None and 0 <= parsed <= 0.1)


def _preboil_temperature(hass):
    """Use current, fresh BrewZilla kettle temperature for preboil decisions."""
    raw, fresh = _readback(hass, base.BREWZILLA_TEMP_SENSOR)
    return _num(raw) if fresh else None


def _decorate(hass, snapshot):
    state = _observe(hass)
    if state.phase == "inactive":
        return {**snapshot, "rapt_sparge_active": False, "rapt_sparge_phase": None}
    out = dict(snapshot)
    out.update(rapt_sparge_active=True, rapt_sparge_phase=state.phase,
               rapt_sparge_lift_confirmed=state.lift_confirmed,
               rapt_sparge_session_id=state.session_id,
               rapt_sparge_step_id=state.step_id,
               rapt_sparge_step_number=state.step_number,
               rapt_sparge_preboil_target_c=PREBOIL_TARGET_C,
               boil_stage=False, boil_target_fallback_active=False,
               pump_recommended=False, desired_pump_on=False,
               desired_pump_utilization=0.0, pump_action_needed=False,
               completion_stop_needed=False, completion_pump_stop_needed=False,
               ba_owned_reassert_action_needed=False)
    if out.get("abort_lockout_active") or out.get("fail_passive_active") or not out.get("connected"):
        out.update(target_sync_needed=False, heating_needed=False,
                   heater_action_needed=False, heater_stop_needed=False,
                   pump_action_needed=False, pump_stop_needed=False,
                   heat_utilization_action_needed=False, pump_utilization_action_needed=False,
                   can_apply_target=False,
                   control_reason="Sparge interlock: ABORT, disconnection or fail-passive; verify outputs locally.")
        return out

    # Readback missing/unknown is NOT proof of OFF; request a safe-down if its
    # entity exists but never permit positive preboil until fresh OFF/zero.
    heater, _ = _readback(hass, base.BREWZILLA_HEATER_SWITCH)
    pump, _ = _readback(hass, base.BREWZILLA_PUMP_SWITCH)
    heat, _ = _readback(hass, base.BREWZILLA_HEAT_UTILIZATION)
    pump_pct, _ = _readback(hass, base.BREWZILLA_PUMP_UTILIZATION)
    pump_stop = pump != "off" and hass.states.get(base.BREWZILLA_PUMP_SWITCH) is not None
    pump_zero = (_num(pump_pct) is None or _num(pump_pct) > 0.1) and hass.states.get(base.BREWZILLA_PUMP_UTILIZATION) is not None
    out.update(pump_stop_needed=pump_stop, pump_utilization_action_needed=pump_zero,
               heat_utilization_action_needed=False)

    if state.phase == "awaiting_lift":
        heater_stop = heater != "off" and hass.states.get(base.BREWZILLA_HEATER_SWITCH) is not None
        heat_zero = (_num(heat) is None or _num(heat) > 0.1) and hass.states.get(base.BREWZILLA_HEAT_UTILIZATION) is not None
        pending = heater_stop or heat_zero or pump_stop or pump_zero
        out.update(requested_target=None, requested_target_source="sparge_safe_down",
                   target_sync_needed=False, heating_needed=False,
                   desired_heater_on=False, desired_heat_utilization=0.0,
                   heater_action_needed=False, heater_stop_needed=heater_stop,
                   heat_utilization_action_needed=heat_zero,
                   can_apply_target=pending, orchestration_mode="sparge-awaiting-lift",
                   control_reason="Sparge: stop heat/pump; verify OFF and zero utilization, then lift and explicitly confirm wort coverage.")
        return out

    # Confirmation only authorizes a subsequent supervised plan. Recheck the
    # pump, heater and kettle temperature on EVERY snapshot and confirmation.
    pump_safe = _pump_safe_for_preboil(hass)
    current_temp = _preboil_temperature(hass)
    heater_readback, heater_fresh = _readback(hass, base.BREWZILLA_HEATER_SWITCH)
    heat_pct = _num(heat)
    applied = _num(out.get("applied_target"))
    if not pump_safe or current_temp is None or not heater_fresh:
        heater_stop = heater != "off" and hass.states.get(base.BREWZILLA_HEATER_SWITCH) is not None
        heat_zero = (heat_pct is None or heat_pct > 0.1) and hass.states.get(base.BREWZILLA_HEAT_UTILIZATION) is not None
        pending = heater_stop or heat_zero or pump_stop or pump_zero
        out.update(requested_target=None, requested_target_source="sparge_positive_blocked",
                   target_sync_needed=False, heating_needed=False,
                   desired_heater_on=False, desired_heat_utilization=0.0,
                   heater_action_needed=False, heater_stop_needed=heater_stop,
                   heat_utilization_action_needed=heat_zero,
                   can_apply_target=pending, orchestration_mode="sparge-preboil-blocked",
                   control_reason="Sparge preboil blocked: pump OFF/zero, fresh heater and kettle telemetry required; only safe-down allowed.")
        return out

    heat_needed = current_temp < PREBOIL_TARGET_C - 0.5
    heater_start = heat_needed and heater_readback == "off"
    heater_stop = not heat_needed and heater_readback != "off" and hass.states.get(base.BREWZILLA_HEATER_SWITCH) is not None
    desired_heat = 100.0 if heat_needed else 0.0
    heat_adjust = heat_pct is None or abs(heat_pct - desired_heat) > base.UTILIZATION_TOLERANCE
    target_adjust = applied is None or abs(applied - PREBOIL_TARGET_C) > base.TARGET_SYNC_TOLERANCE
    pending = bool(heater_start or heater_stop or heat_adjust or target_adjust or pump_stop or pump_zero)
    out.update(requested_target=PREBOIL_TARGET_C,
               requested_target_source="rapt_sparge_operator_confirmed_preboil",
               target_delta=None if applied is None else round(PREBOIL_TARGET_C - applied, 2),
               target_sync_needed=target_adjust,
               heating_needed=heat_needed, desired_heater_on=heat_needed,
               desired_heat_utilization=desired_heat,
               heater_action_needed=heater_start, heater_stop_needed=heater_stop,
               heat_utilization_action_needed=heat_adjust,
               can_apply_target=pending,
               orchestration_mode="sparge-preboil-supervised" if pending else "sparge-preboil-hold",
               control_reason="Operator-confirmed lift; BA preheats to max 95 C, pump OFF. RAPT remains responsible for manual Boil transition.")
    return out


def _build(hass):
    assert _PREVIOUS_BUILD is not None
    return _decorate(hass, _PREVIOUS_BUILD(hass))


def _supervised_build(hass):
    assert _PREVIOUS_SUPERVISED_BUILD is not None
    return _decorate(hass, _PREVIOUS_SUPERVISED_BUILD(hass))


def _semantics(snapshot):
    assert _PREVIOUS_SEMANTICS is not None
    raw = snapshot.get("raw_step_name") or snapshot.get("step")
    if state_machine.is_sparge_step(raw):
        return "Sparge", "Sparge"
    return _PREVIOUS_SEMANTICS(snapshot)


def _phase_authority(hass, snapshot):
    assert _PREVIOUS_PHASE_AUTHORITY is not None
    if state_machine.is_sparge_step(snapshot.get("runtime_raw_step_name")):
        return False
    return _PREVIOUS_PHASE_AUTHORITY(hass, snapshot)


def _plan_policy(hass, snapshot, actions):
    assert _PREVIOUS_PLAN_POLICY is not None
    policy = _PREVIOUS_PLAN_POLICY(hass, snapshot, actions)
    if snapshot.get("rapt_sparge_active") and snapshot.get("rapt_sparge_phase") == "heat_to_boil":
        return "read_only" if policy == "read_only" else "confirm"
    return policy


async def async_confirm_sparge_lift(hass):
    """Operator attests that malt pipe is lifted and elements remain covered."""
    current = _observe(hass)
    status = build_sparge_snapshot(hass)
    if current.phase != "awaiting_lift" or not status["operator_confirmation_available"]:
        return {**status, "confirmed": False, "apply_result": "sparge_not_ready_for_lift_confirmation"}
    if current.session_id != status["session_id"] or current.step_id != status["step_id"]:
        return {**status, "confirmed": False, "apply_result": "sparge_session_changed_during_confirmation"}
    updated = state_machine.confirm_lift(
        current, heater_off=status["heater_readback"] == "off",
        pump_off=status["pump_readback"] == "off",
        heat_utilization=status["heat_utilization_readback"],
        pump_utilization=status["pump_utilization_readback"],
        output_telemetry_fresh=status["outputs_confirmed_off"],
        kettle_has_sufficient_wort=True, malt_pipe_safely_lifted=True,
    )
    _store(hass)[STORE_KEY] = updated
    clear_pending_action_from_source(hass, supervised.SOURCE)
    return {**build_sparge_snapshot(hass), "confirmed": updated.phase == "heat_to_boil",
            "apply_result": "sparge_lift_confirmed_requires_supervised_preboil" if updated.phase == "heat_to_boil" else "sparge_lift_refused"}


def install_rapt_sparge_controller():
    """Install after physical Mash interlock, before final source-write guard."""
    global _INSTALLED, _PREVIOUS_BUILD, _PREVIOUS_SUPERVISED_BUILD
    global _PREVIOUS_SEMANTICS, _PREVIOUS_PHASE_AUTHORITY, _PREVIOUS_PLAN_POLICY
    if _INSTALLED:
        return
    _PREVIOUS_BUILD = base.build_orchestration_snapshot
    _PREVIOUS_SUPERVISED_BUILD = supervised._BASE_BUILD
    _PREVIOUS_SEMANTICS = bridge._semantic_stage_step
    _PREVIOUS_PHASE_AUTHORITY = phase_authority._phase_authority_active
    _PREVIOUS_PLAN_POLICY = supervised._plan_policy
    if _PREVIOUS_SUPERVISED_BUILD is None:
        raise RuntimeError("Sparge must install after supervised guard")
    bridge._semantic_stage_step = _semantics
    phase_authority._phase_authority_active = _phase_authority
    supervised._plan_policy = _plan_policy
    base.build_orchestration_snapshot = _build
    supervised._BASE_BUILD = _supervised_build
    _INSTALLED = True
