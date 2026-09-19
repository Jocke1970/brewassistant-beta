"""Operator-gated mash settling and physical-hold authority (Brewfather v1).

The source schedule may advance, but never authorizes a later physical target.
No timer callback energizes the pump. HLT is simulation-only and untouched.
"""
from __future__ import annotations

from typing import Any
from homeassistant.util import dt as dt_util

from ..brewday import brewday_physical_timing as timing
from ..brewday.brewday_operator_abort import brewday_operator_abort_active
from ..const import DOMAIN
from ..supervised_apply import clear_pending_action_from_source
from . import brewzilla_orchestration as base
from . import brewzilla_mash_in_gate as gate
from . import brewzilla_mash_in_complete_safe_down_guard as bridge
from . import brewzilla_supervised_runtime_guard as supervised

DATA_KEY = "brewzilla_physical_mash_interlock"
SETTLE_MINUTES = 10
RAMP_MINUTES = 5
LOW_FLOW_PCT = 25.0
NORMAL_FLOW_PCT = 50.0
ACTIVE = {"settling", "recirculation_ready", "low_flow_pending", "low_flow", "normal_ready", "normal_pending", "normal", "blocked", "recovery_required"}
_INSTALLED = False
_ORIGINAL_RUNTIME = None
_ORIGINAL_BUILD = None
_ORIGINAL_SUPERVISED_BUILD = None
_ORIGINAL_BRIDGE_CIRCULATION = None


def _num(value: Any) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def _store(hass) -> dict[str, Any]:
    return hass.data.setdefault(DOMAIN, {}).setdefault(DATA_KEY, {})


def _elapsed(value, now) -> float:
    stamp = dt_util.parse_datetime(str(value)) if value else None
    return max(0.0, (now - dt_util.as_utc(stamp)).total_seconds()) if stamp else 0.0


def _options(hass):
    entries = hass.config_entries.async_entries(DOMAIN)
    options = entries[0].options if entries else {}
    def bounded(key, default, lo, hi):
        value = _num(options.get(key))
        return float(default if value is None or not lo <= value <= hi else value)
    return {
        "settle_s": 60 * bounded("mash_settle_minutes", SETTLE_MINUTES, 1, 60),
        "ramp_s": 60 * bounded("recirculation_ramp_minutes", RAMP_MINUTES, 1, 30),
        "low": bounded("recirculation_initial_utilization", LOW_FLOW_PCT, 1, 40),
        "normal": bounded("recirculation_normal_utilization", NORMAL_FLOW_PCT, 1, 100),
    }


def _state_num(hass, entity):
    value = hass.states.get(entity)
    return _num(value.state) if value and str(value.state).lower() not in {"unknown", "unavailable"} else None


def _on(hass, entity):
    value = hass.states.get(entity)
    return value is not None and str(value.state).lower() == "on"


def _fresh(hass, entity):
    value = hass.states.get(entity) if isinstance(entity, str) else None
    if value is None or str(value.state).lower() in {"unknown", "unavailable", "none", ""}:
        return False
    stamp = getattr(value, "last_reported", None) or getattr(value, "last_updated", None)
    age = (dt_util.utcnow() - dt_util.as_utc(stamp)).total_seconds() if stamp else None
    return age is not None and 0 <= age <= 90


def _tick(hass, runtime=None):
    state = _store(hass)
    if state.get("phase") not in ACTIVE:
        return state
    if brewday_operator_abort_active(hass):
        state.update(phase="blocked", reason="operator_abort")
        return state
    if runtime is not None and runtime.get("source") != state.get("source"):
        state.update(phase="blocked", reason="source_changed")
        return state
    now, opts = dt_util.utcnow(), _options(hass)
    if state["phase"] == "settling" and _elapsed(state.get("settling_at"), now) >= opts["settle_s"]:
        state["phase"] = "recirculation_ready"
    if state["phase"] == "low_flow_pending":
        pct = _state_num(hass, base.BREWZILLA_PUMP_UTILIZATION)
        if _on(hass, base.BREWZILLA_PUMP_SWITCH) and pct is not None and abs(pct - opts["low"]) < 1 and _fresh(hass, state.get("temperature_entity")):
            state.update(phase="low_flow", low_at=now.isoformat())
    if state["phase"] == "low_flow" and _elapsed(state.get("low_at"), now) >= opts["ramp_s"]:
        state["phase"] = "normal_ready"
    if state["phase"] == "normal_pending":
        pct = _state_num(hass, base.BREWZILLA_PUMP_UTILIZATION)
        if _on(hass, base.BREWZILLA_PUMP_SWITCH) and pct is not None and abs(pct - opts["normal"]) < 1 and _fresh(hass, state.get("temperature_entity")):
            state.update(phase="normal", normal_at=now.isoformat())
    if state["phase"] in {"low_flow_pending", "normal_pending"} and _elapsed(state.get("commanded_at"), now) > 120:
        state.update(phase="blocked", reason="pump_readback_timeout")
        return state
    if state.get("source") == "Brewfather Brew Tracker" and not state.get("hold_completed"):
        physical = timing.build_brewday_physical_timing_snapshot(hass)
        ledger = timing._store(hass)
        active = ledger.get("active")
        target = _num(state.get("hold_target"))
        current = _num(physical.get("current_temperature"))
        live_hold = (isinstance(active, dict) and active.get("kind") == "hold" and target is not None
                     and _num(active.get("target")) is not None
                     and abs(float(active["target"]) - target) <= timing.TARGET_TOLERANCE_C
                     and active.get("timer_started_at") and active.get("completed"))
        completed_history = any(
            row.get("kind") == "hold" and target is not None and _num(row.get("target_temperature")) is not None
            and abs(float(row["target_temperature"]) - target) <= timing.TARGET_TOLERANCE_C
            and row.get("completed_at") and state.get("settling_at")
            and dt_util.as_utc(dt_util.parse_datetime(row["completed_at"])) >= dt_util.as_utc(dt_util.parse_datetime(state["settling_at"]))
            for row in ledger.get("history", [])
        )
        if ((live_hold or completed_history) and target is not None and current is not None
                and abs(current - target) <= timing.TARGET_TOLERANCE_C
                and _fresh(hass, physical.get("temperature_entity"))):
            state.update(hold_completed=True, hold_completed_at=now.isoformat())
    return state


def _runtime(hass):
    assert _ORIGINAL_RUNTIME is not None
    runtime = _ORIGINAL_RUNTIME(hass)
    state = _tick(hass, runtime)
    if (not state and runtime.get("source") == "Brewfather Brew Tracker" and
            str(runtime.get("stage") or "").lower() == "mash" and
            str(runtime.get("runtime_state") or "").lower() in {"live", "running", "paused"} and
            (_num(runtime.get("resolved_step_index")) or 0) >= 3 and
            not gate._gate_store(hass).get("completed_once")):
        # A restarted HA must never infer an operator confirmation from BF.
        state.update(phase="recovery_required", reason="lost_mash_authority_after_restart", source=runtime.get("source"))
    if state.get("phase") not in ACTIVE or state["phase"] in {"blocked", "recovery_required"}:
        return runtime
    if runtime.get("source") != "Brewfather Brew Tracker" or state.get("source") != runtime.get("source"):
        return runtime
    target = _num(state.get("hold_target"))
    if target is None:
        state.update(phase="blocked", reason="unknown_hold_target")
        return runtime
    if state["phase"] == "normal" and state.get("hold_completed"):
        state["phase"] = "released"
        return runtime
    return {**runtime, "target_temperature": target,
            "target_temperature_source": "physical_mash_hold_interlock",
            "physical_mash_source_step": runtime.get("step")}


def _decorate(hass, snapshot):
    state = _tick(hass)
    phase = state.get("phase")
    if phase not in ACTIVE:
        return {**snapshot, "physical_mash_interlock_active": False}
    opts, now = _options(hass), dt_util.utcnow()
    fields = {
        "physical_mash_interlock_active": True,
        "mash_recirculation_phase": phase,
        "mash_settle_remaining_seconds": max(0, round(opts["settle_s"] - _elapsed(state.get("settling_at"), now))) if phase == "settling" else 0,
        "mash_recirculation_ramp_remaining_seconds": max(0, round(opts["ramp_s"] - _elapsed(state.get("low_at"), now))) if phase == "low_flow" else 0,
        "mash_physical_hold_target": state.get("hold_target"),
        "mash_physical_hold_complete": bool(state.get("hold_completed")),
        "mash_recirculation_operator_required": phase in {"recirculation_ready", "normal_ready"},
        "mash_interlock_reason": state.get("reason"),
    }
    out = {**snapshot, **fields}
    if snapshot.get("abort_lockout_active") or snapshot.get("fail_passive_active") or brewday_operator_abort_active(hass):
        return out
    if phase in {"blocked", "recovery_required"}:
        out.update(can_apply_target=False, orchestration_mode="blocked", target_sync_needed=False,
                   heater_action_needed=False, heater_stop_needed=False, heat_utilization_action_needed=False,
                   pump_action_needed=False, pump_stop_needed=False, pump_utilization_action_needed=False,
                   control_reason="Physical mash authority unknown; ABORT or operator recovery required; no BA writes.")
        return out
    if phase in {"settling", "recirculation_ready"}:
        actual = _state_num(hass, base.BREWZILLA_PUMP_UTILIZATION)
        out.update(pump_recommended=False, desired_pump_on=False, desired_pump_utilization=0.0,
                   pump_action_needed=False, pump_stop_needed=bool(out.get("pump_on")),
                   pump_utilization_action_needed=actual is not None and actual > 0.1,
                   can_apply_target=bool(out.get("can_apply_target") or out.get("pump_on") or (actual is not None and actual > 0.1)))
    elif phase in {"low_flow_pending", "low_flow", "normal_ready", "normal_pending", "normal"}:
        ceiling = opts["normal"] if phase in {"normal_pending", "normal"} else opts["low"]
        actual = _state_num(hass, base.BREWZILLA_PUMP_UTILIZATION)
        out.update(pump_action_needed=False, desired_pump_on=bool(out.get("pump_on")),
                   desired_pump_utilization=min(ceiling, _num(out.get("desired_pump_utilization")) or ceiling),
                   pump_utilization_action_needed=actual is not None and actual > ceiling + 0.1)
    target, requested = _num(state.get("hold_target")), _num(out.get("requested_target"))
    if target is not None and (requested is None or requested > target + 0.1):
        applied = _num(out.get("applied_target"))
        out.update(requested_target=target, requested_target_source="physical_mash_hold_interlock",
                   target_sync_needed=applied is not None and applied > target + 0.1,
                   target_delta=None if applied is None else round(target - applied, 2))
    out["control_reason"] = f"{out.get('control_reason') or ''}; physical mash {phase}, operator-gated pump and hold."
    return out


def _build(hass):
    assert _ORIGINAL_BUILD is not None
    return _decorate(hass, _ORIGINAL_BUILD(hass))


def _supervised_build(hass):
    assert _ORIGINAL_SUPERVISED_BUILD is not None
    return _decorate(hass, _ORIGINAL_SUPERVISED_BUILD(hass))


def _result(hass, snapshot, action, status, actions=()):
    result = {**snapshot, "source": "brewzilla_physical_mash_interlock", "applied": bool(actions),
              "apply_result": status, "actions": list(actions), "pump_started": "pump_on" in actions,
              "mash_in_gate_confirmed": action in {"mash_in_complete", "mash_in_complete_brewfather_resume"},
              "mash_in_resume_allowed": status == "mash_settling_started",
              "mash_in_gate_state": "mash_in_complete", "executed_at": dt_util.utcnow().isoformat()}
    hass.data.setdefault(DOMAIN, {})["brewzilla_last_apply_result"] = result
    return result


async def _circulation(hass, snapshot, *, action_name):
    state = _store(hass)
    if (snapshot.get("abort_lockout_active") or brewday_operator_abort_active(hass) or
            not snapshot.get("connected", True) or snapshot.get("fail_passive_active") or
            str(snapshot.get("brewday_state") or "").lower() not in {"live", "running", "paused", "awaiting_snapshot"}):
        state.update(phase="blocked", reason="unsafe_transition_context")
        return _result(hass, snapshot, action_name, "mash_interlock_blocked:unsafe_transition_context")
    if action_name in {"mash_in_complete", "mash_in_complete_brewfather_resume"}:
        gate_store = gate._gate_store(hass)
        target = _num(gate_store.get("effective_target"))
        if target is None:
            state.update(phase="blocked", reason="missing_mash_target")
            return _result(hass, snapshot, action_name, "mash_interlock_blocked:missing_mash_target")
        state.update(phase="settling", source=snapshot.get("runtime_source"), session_key=gate_store.get("active_key"),
                     settling_at=dt_util.utcnow().isoformat(), hold_target=target, hold_completed=False,
                     temperature_entity=snapshot.get("process_temperature_entity") or "sensor.brewassistant_brewzilla_mash_temperature", reason=None)
        actions = [action_name]
        try:
            if hass.states.get(base.BREWZILLA_PUMP_SWITCH) is None or hass.states.get(base.BREWZILLA_PUMP_UTILIZATION) is None:
                raise RuntimeError("missing pump entity")
            if not await base._set_number(hass, base.BREWZILLA_PUMP_UTILIZATION, 0.0):
                raise RuntimeError("pump zero rejected")
            actions.append("set_pump_utilization:0.0")
            # Force OFF irrespective of stale switch readback.
            await base._call_switch(hass, "off", base.BREWZILLA_PUMP_SWITCH)
            actions.append("pump_off")
        except Exception:
            state.update(phase="blocked", reason="pump_safe_down_failed")
            return _result(hass, snapshot, action_name, "mash_interlock_blocked:pump_safe_down_failed", actions)
        if state.get("source") == "Brewfather Brew Tracker":
            timing.build_brewday_physical_timing_snapshot(hass)
        return _result(hass, snapshot, action_name, "mash_settling_started", actions)
    if action_name != "start_mash_circulation":
        return _result(hass, snapshot, action_name, "mash_interlock_blocked:unknown_action")
    state = _tick(hass)
    phase = state.get("phase")
    if phase not in {"recirculation_ready", "normal_ready"}:
        return _result(hass, snapshot, action_name, f"mash_interlock_blocked:{phase or 'not_ready'}")
    gate_store = gate._gate_store(hass)
    if gate_store.get("active_key") != state.get("session_key") or not gate_store.get("completed_once"):
        return _result(hass, snapshot, action_name, "mash_interlock_blocked:session_mismatch")
    if not _fresh(hass, state.get("temperature_entity")):
        return _result(hass, snapshot, action_name, "mash_interlock_blocked:temperature_stale")
    opts = _options(hass)
    target = opts["low"] if phase == "recirculation_ready" else opts["normal"]
    if phase == "recirculation_ready" and (_on(hass, base.BREWZILLA_PUMP_SWITCH) or (_state_num(hass, base.BREWZILLA_PUMP_UTILIZATION) or 0) > 0.1):
        return _result(hass, snapshot, action_name, "mash_interlock_blocked:pump_not_off")
    if phase == "normal_ready" and not _on(hass, base.BREWZILLA_PUMP_SWITCH):
        return _result(hass, snapshot, action_name, "mash_interlock_blocked:pump_not_running")
    try:
        if not await base._set_number(hass, base.BREWZILLA_PUMP_UTILIZATION, target):
            return _result(hass, snapshot, action_name, "mash_interlock_blocked:pump_number_missing")
        actions = [f"set_pump_utilization:{target}"]
        if phase == "recirculation_ready":
            if hass.states.get(base.BREWZILLA_PUMP_SWITCH) is None:
                state.update(phase="blocked", reason="pump_switch_missing")
                return _result(hass, snapshot, action_name, "mash_interlock_blocked:pump_switch_missing", actions)
            await base._call_switch(hass, "on", base.BREWZILLA_PUMP_SWITCH)
            actions.append("pump_on")
        state.update(phase="low_flow_pending" if phase == "recirculation_ready" else "normal_pending",
                     commanded_at=dt_util.utcnow().isoformat())
        clear_pending_action_from_source(hass, supervised.SOURCE)
        return _result(hass, snapshot, action_name, "mash_recirculation_command_sent_awaiting_readback", actions)
    except Exception:
        state.update(phase="blocked", reason="recirculation_command_failed")
        return _result(hass, snapshot, action_name, "mash_interlock_blocked:recirculation_command_failed")


async def _bridge_circulation(hass, snapshot, *, action_name):
    assert _ORIGINAL_BRIDGE_CIRCULATION is not None
    result = await _ORIGINAL_BRIDGE_CIRCULATION(hass, snapshot, action_name=action_name)
    if action_name in {"mash_in_complete", "mash_in_complete_brewfather_resume"}:
        settled = _store(hass).get("phase") == "settling"
        result.update(apply_result="mash_settling_started" if settled else "mash_interlock_blocked",
                      pump_started=False, desired_pump_on=False, desired_pump_utilization=0.0,
                      mash_in_resume_allowed=settled,
                      control_reason="Mash-In Complete: pump OFF; settling before operator-gated recirculation.")
        hass.data.setdefault(DOMAIN, {})["brewzilla_last_apply_result"] = result
    return result


def install_physical_mash_interlock():
    """Install after fail-passive and supervised guards; no branch or HLT changes."""
    global _INSTALLED, _ORIGINAL_RUNTIME, _ORIGINAL_BUILD, _ORIGINAL_SUPERVISED_BUILD, _ORIGINAL_BRIDGE_CIRCULATION
    if _INSTALLED:
        return
    _ORIGINAL_RUNTIME = base.build_brewday_runtime_snapshot
    _ORIGINAL_BUILD = base.build_orchestration_snapshot
    _ORIGINAL_SUPERVISED_BUILD = supervised._BASE_BUILD
    _ORIGINAL_BRIDGE_CIRCULATION = bridge._patched_start_mash_circulation
    if _ORIGINAL_SUPERVISED_BUILD is None or bridge._ORIGINAL_START_MASH_CIRCULATION is None:
        raise RuntimeError("Mash interlock must install after supervised and mash-in bridges")
    base.build_brewday_runtime_snapshot = _runtime
    base.build_orchestration_snapshot = _build
    supervised._BASE_BUILD = _supervised_build
    bridge._ORIGINAL_START_MASH_CIRCULATION = _circulation
    bridge._patched_start_mash_circulation = _bridge_circulation
    gate._start_mash_circulation = _bridge_circulation
    _INSTALLED = True
