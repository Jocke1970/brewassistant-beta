"""Source-authority regression tests for three-mode Brewday / RCL Assist."""

from __future__ import annotations

import ast
import asyncio
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_source_authority_runtime.py"
SOURCE = GATE.read_text(encoding="utf-8")


def _load(*names):
    tree = ast.parse(SOURCE)
    funcs = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names]
    assert {node.name for node in funcs} == set(names)
    env = {}
    exec(compile(ast.Module(body=funcs, type_ignores=[]), str(GATE), "exec"), env)
    return env


FN = _load("_write_allowed", "_safe_off_allowed", "_sparge_write_allowed",
           "_rcl_assist_write_allowed", "_observer_snapshot", "_rcl_assist_snapshot",
           "_learning_apply")
ENTITIES = frozenset({
    "number.brewzilla_target_temperature", "number.brewzilla_heat_utilization",
    "number.brewzilla_pump_utilization", "switch.brewzilla_heater", "switch.brewzilla_pump",
})
BASE = SimpleNamespace(
    BREWZILLA_TARGET_NUMBER="number.brewzilla_target_temperature",
    BREWZILLA_HEATER_SWITCH="switch.brewzilla_heater",
    BREWZILLA_PUMP_SWITCH="switch.brewzilla_pump",
    BREWZILLA_HEAT_UTILIZATION="number.brewzilla_heat_utilization",
    BREWZILLA_PUMP_UTILIZATION="number.brewzilla_pump_utilization",
)


def _allowed(mode, may_write, scope="none", *, rapt_stop=False,
             entity="switch.brewzilla_heater", switch_action="on", value=None):
    authority = SimpleNamespace(mode=mode, may_write_brewzilla=may_write,
                                reason=mode, write_scope=scope)
    context = {
        "runtime": {
            "source": "RAPT BrewZilla Profile" if rapt_stop else "Brewfather Brew Tracker",
            "profile_stop_confirmed": rapt_stop,
            "profile_stop_guard_active": rapt_stop,
        },
        "operator": {"active": False, "source": None},
    }
    ns = FN["_write_allowed"].__globals__
    ns.update(
        base=BASE, BREWZILLA_ENTITIES=ENTITIES,
        RCL_ASSIST_SCOPE="rcl_assist", FULL_SCOPE="full",
        _live_authority=lambda hass: (authority, context),
        _safe_off_allowed=FN["_safe_off_allowed"],
        _sparge_write_allowed=FN["_sparge_write_allowed"],
        _rcl_assist_write_allowed=FN["_rcl_assist_write_allowed"],
        sparge=SimpleNamespace(_observe=lambda hass: SimpleNamespace(phase="inactive")),
    )
    return FN["_write_allowed"](None, entity, switch_action=switch_action, value=value)


def test_brewfather_full_scope_allows_existing_hot_side_path():
    for entity in ENTITIES:
        assert _allowed("brewfather_observer", True, "full",
                        entity=entity, switch_action="on", value=100)


def test_rcl_assist_denies_target_and_heater_but_allows_learning_heat_and_pump():
    assert not _allowed("rapt_controller", True, "rcl_assist",
                        entity=BASE.BREWZILLA_TARGET_NUMBER, value=66)
    assert not _allowed("rapt_controller", True, "rcl_assist",
                        entity=BASE.BREWZILLA_HEATER_SWITCH, switch_action="on")
    assert not _allowed("rapt_controller", True, "rcl_assist",
                        entity=BASE.BREWZILLA_HEATER_SWITCH, switch_action="off")
    assert _allowed("rapt_controller", True, "rcl_assist",
                    entity=BASE.BREWZILLA_HEAT_UTILIZATION, value=55)
    assert _allowed("rapt_controller", True, "rcl_assist",
                    entity=BASE.BREWZILLA_PUMP_SWITCH, switch_action="on")
    assert _allowed("rapt_controller", True, "rcl_assist",
                    entity=BASE.BREWZILLA_PUMP_SWITCH, switch_action="off")
    assert _allowed("rapt_controller", True, "rcl_assist",
                    entity=BASE.BREWZILLA_PUMP_UTILIZATION, value=45)


def test_confirmed_rapt_stop_can_safe_down_only_when_normal_authority_is_blocked():
    for entity in (BASE.BREWZILLA_HEATER_SWITCH, BASE.BREWZILLA_PUMP_SWITCH):
        assert _allowed("blocked", False, rapt_stop=True, entity=entity, switch_action="off")
        assert not _allowed("blocked", False, rapt_stop=True, entity=entity, switch_action="on")
    for entity in (BASE.BREWZILLA_HEAT_UTILIZATION, BASE.BREWZILLA_PUMP_UTILIZATION):
        assert _allowed("blocked", False, rapt_stop=True, entity=entity, value=0)
        assert not _allowed("blocked", False, rapt_stop=True, entity=entity, value=25)
    assert not _allowed("blocked", False, rapt_stop=True,
                        entity=BASE.BREWZILLA_TARGET_NUMBER, value=95)


def test_rcl_assist_snapshot_removes_target_and_heater_actions_only():
    authority = SimpleNamespace(mode="rapt_controller", reason="ok", write_scope="rcl_assist")
    ns = FN["_rcl_assist_snapshot"].__globals__
    ns["RCL_ASSIST_SCOPE"] = "rcl_assist"
    snapshot = {
        "can_apply_target": True,
        "target_sync_needed": True,
        "heater_action_needed": True,
        "heater_stop_needed": True,
        "completion_stop_needed": True,
        "heat_utilization_action_needed": True,
        "pump_action_needed": True,
        "pump_stop_needed": False,
        "pump_utilization_action_needed": True,
        "completion_pump_stop_needed": False,
    }
    out = FN["_rcl_assist_snapshot"](snapshot, authority)
    assert out["rcl_assist_active"] is True
    assert out["rcl_assist_auto_apply"] is True
    assert out["target_sync_needed"] is False
    assert out["heater_action_needed"] is False
    assert out["heater_stop_needed"] is False
    assert out["heat_utilization_action_needed"] is True
    assert out["pump_action_needed"] is True
    assert out["pump_utilization_action_needed"] is True
    assert out["can_apply_target"] is True


def test_learning_apply_button_cannot_bypass_source_bound_execution():
    ns = FN["_learning_apply"].__globals__
    count = []

    async def previous(hass):
        count.append("called")
        return {"applied": True}

    ns["_PREVIOUS_LEARNING_APPLY"] = previous
    for mode in ("brewfather_observer", "rapt_controller", "blocked"):
        ns["_live_authority"] = lambda hass, m=mode: (SimpleNamespace(mode=m), {})
        assert asyncio.run(FN["_learning_apply"](None))["applied"] is False
    assert not count
    ns["_live_authority"] = lambda hass: (SimpleNamespace(mode="manual_legacy_unresolved"), {})
    assert asyncio.run(FN["_learning_apply"](None))["applied"] is True


def test_installation_still_encloses_writer_entry_points():
    for token in (
        "base._set_number = _set_number",
        "base._call_switch = _call_switch",
        "base._enforce_brewzilla_safe_state = _safe_state",
        "base.async_apply_brewzilla_target_if_allowed = _apply",
        "control_policy.execute_action = _policy_execute",
        "supervised._BASE_BUILD = _supervised_build",
    ):
        assert token in SOURCE
