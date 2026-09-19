"""Executable regressions for the Sep 19 water-only Mash-In defect.

Extract the interlock functions with AST so tests run without a Home Assistant
installation, then exercise real function bodies with deterministic HA doubles.
"""
from __future__ import annotations

import ast
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_physical_mash_interlock.py"
INIT = ROOT / "custom_components/brewassistant/brewzilla/__init__.py"
BRIDGE = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_mash_in_complete_safe_down_guard.py"


def _harness():
    tree = ast.parse(FILE.read_text(encoding="utf-8"))
    names = {"_num", "_store", "_elapsed", "_tick", "_runtime", "_decorate", "_result", "_circulation"}
    body = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names]
    code = compile(ast.Module(body=body, type_ignores=[]), str(FILE), "exec")
    clock = SimpleNamespace(now=datetime(2026, 9, 19, 9, 0, tzinfo=timezone.utc))
    dt = SimpleNamespace(
        utcnow=lambda: clock.now,
        parse_datetime=datetime.fromisoformat,
        as_utc=lambda d: d.astimezone(timezone.utc),
    )
    opts = {"settle_s": 600, "ramp_s": 300, "low": 25, "normal": 50}
    gate_store = {"active_key": "batch-1", "completed_once": True, "effective_target": 66}
    base = SimpleNamespace(
        BREWZILLA_PUMP_UTILIZATION="number.brewzilla_pump_utilization",
        BREWZILLA_PUMP_SWITCH="switch.brewzilla_pump",
    )
    state = {}
    hass = SimpleNamespace(data={"brewassistant": {"brewzilla_physical_mash_interlock": state}}, states={})
    for entity, value in ((base.BREWZILLA_PUMP_SWITCH, "off"), (base.BREWZILLA_PUMP_UTILIZATION, "0"), ("sensor.mash", "66")):
        hass.states[entity] = SimpleNamespace(state=value, last_reported=clock.now)
    commands = []

    async def set_number(h, entity, value):
        commands.append((entity, value))
        h.states[entity].state = str(value)
        h.states[entity].last_reported = clock.now
        return True

    async def call_switch(h, action, entity):
        commands.append((entity, action))
        h.states[entity].state = "on" if action == "on" else "off"
        h.states[entity].last_reported = clock.now

    base._set_number = set_number
    base._call_switch = call_switch
    gate = SimpleNamespace(_gate_store=lambda h: gate_store)
    ledger = {"active": None, "history": []}
    timing = SimpleNamespace(
        TARGET_TOLERANCE_C=0.3,
        _store=lambda h: ledger,
        build_brewday_physical_timing_snapshot=lambda h: {"current_temperature": 66, "temperature_entity": "sensor.mash"},
    )
    namespace = {
        "Any": Any, "DOMAIN": "brewassistant", "DATA_KEY": "brewzilla_physical_mash_interlock",
        "ACTIVE": {"settling", "recirculation_ready", "low_flow_pending", "low_flow", "normal_ready", "normal_pending", "normal", "blocked", "recovery_required"},
        "dt_util": dt, "_options": lambda h: opts, "base": base, "gate": gate, "timing": timing,
        "brewday_operator_abort_active": lambda h: False, "clear_pending_action_from_source": lambda *args: commands.append(("clear_pending",)),
        "supervised": SimpleNamespace(SOURCE="brewzilla_orchestration"),
        "_ORIGINAL_RUNTIME": lambda h: {"source": "Brewfather Brew Tracker", "runtime_state": "running", "stage": "Mash", "step": "Ramp to 72°C", "resolved_step_index": 4, "target_temperature": 72},
    }
    exec(code, namespace)
    namespace["_state_num"] = lambda h, e: namespace["_num"](h.states[e].state) if e in h.states else None
    namespace["_on"] = lambda h, e: e in h.states and h.states[e].state == "on"
    namespace["_fresh"] = lambda h, e: e in h.states and (clock.now - h.states[e].last_reported).total_seconds() <= 90
    return namespace, hass, clock, commands, state, gate_store, ledger


def _complete(n, hass):
    return asyncio.run(n["_circulation"](hass, {
        "brewday_state": "running", "runtime_source": "Brewfather Brew Tracker",
        "connected": True, "process_temperature_entity": "sensor.mash",
    }, action_name="mash_in_complete"))


def test_completion_stops_pump_and_timer_never_energizes_it():
    n, hass, clock, commands, state, _, _ = _harness()
    result = _complete(n, hass)
    assert result["apply_result"] == "mash_settling_started"
    assert ("number.brewzilla_pump_utilization", 0.0) in commands
    assert ("switch.brewzilla_pump", "off") in commands
    assert ("switch.brewzilla_pump", "on") not in commands
    assert state["phase"] == "settling"
    clock.now += timedelta(minutes=11)
    before = list(commands)
    assert n["_tick"](hass)["phase"] == "recirculation_ready"
    assert commands == before, "a timer must only offer an operator action"


def test_pump_rejects_early_stale_and_requires_two_distinct_operator_actions():
    n, hass, clock, commands, state, _, _ = _harness()
    _complete(n, hass)
    action = {"brewday_state": "running", "connected": True}
    early = asyncio.run(n["_circulation"](hass, action, action_name="start_mash_circulation"))
    assert "blocked:settling" in early["apply_result"]
    assert ("switch.brewzilla_pump", "on") not in commands
    clock.now += timedelta(minutes=10)
    stale = asyncio.run(n["_circulation"](hass, action, action_name="start_mash_circulation"))
    assert "blocked:temperature_stale" in stale["apply_result"]
    assert ("switch.brewzilla_pump", "on") not in commands
    hass.states["sensor.mash"].last_reported = clock.now
    low = asyncio.run(n["_circulation"](hass, action, action_name="start_mash_circulation"))
    assert low["pump_started"] is True
    assert ("number.brewzilla_pump_utilization", 25) in commands
    assert state["phase"] == "low_flow_pending"
    assert n["_tick"](hass)["phase"] == "low_flow"
    clock.now += timedelta(minutes=5)
    before = list(commands)
    assert n["_tick"](hass)["phase"] == "normal_ready"
    assert commands == before
    hass.states["sensor.mash"].last_reported = clock.now
    normal = asyncio.run(n["_circulation"](hass, action, action_name="start_mash_circulation"))
    assert "awaiting_readback" in normal["apply_result"]
    assert ("number.brewzilla_pump_utilization", 50) in commands
    assert n["_tick"](hass)["phase"] == "normal"


def test_brewfather_next_target_waits_for_both_physical_hold_and_normal_flow():
    n, hass, _, _, state, _, _ = _harness()
    state.update(phase="settling", source="Brewfather Brew Tracker", hold_target=66,
                 hold_completed=True, settling_at="2026-09-19T09:00:00+00:00")
    assert n["_runtime"](hass)["target_temperature"] == 66
    pending = {"requested_target": 72, "applied_target": 66, "desired_pump_utilization": 85,
               "pump_on": False, "can_apply_target": True}
    limited = n["_decorate"](hass, pending)
    assert limited["requested_target"] == 66
    assert limited["desired_pump_utilization"] == 0
    assert limited["pump_action_needed"] is False
    state["phase"] = "normal"
    assert n["_runtime"](hass)["target_temperature"] == 72
    assert state["phase"] == "released"


def test_restart_requires_recovery_and_does_not_replay_positive_actions():
    n, hass, _, _, state, _, _ = _harness()
    state.clear()
    n["gate"] = SimpleNamespace(_gate_store=lambda h: {"completed_once": False})
    assert n["_runtime"](hass)["target_temperature"] == 72
    assert state["phase"] == "recovery_required"
    blocked = n["_decorate"](hass, {"can_apply_target": True, "heater_action_needed": True,
                                    "pump_action_needed": True, "target_sync_needed": True})
    assert blocked["can_apply_target"] is False
    assert blocked["heater_action_needed"] is False
    assert blocked["pump_action_needed"] is False
    assert blocked["target_sync_needed"] is False


def test_interlock_is_wired_outside_existing_safety_and_preserves_brewfather_edge():
    init = INIT.read_text(encoding="utf-8")
    bridge = BRIDGE.read_text(encoding="utf-8")
    source = FILE.read_text(encoding="utf-8")
    assert init.index("_fail_passive_guard.install_fail_passive_guard()") < init.index("_physical_mash_interlock.install_physical_mash_interlock()")
    assert "bridge._ORIGINAL_START_MASH_CIRCULATION = _circulation" in source
    assert "bridge._patched_start_mash_circulation = _bridge_circulation" in source
    assert "supervised._BASE_BUILD = _supervised_build" in source
    assert "waiting_for_brewfather_pause_after_mash_in_started" in bridge
    assert "hass.services.async_call" not in source
    assert "asyncio.sleep" not in source
