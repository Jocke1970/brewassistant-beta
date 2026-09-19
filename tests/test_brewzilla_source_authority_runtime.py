"""Pure execution of production authority writer gate without HA/hardware."""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_source_authority_runtime.py"
SOURCE = GATE.read_text(encoding="utf-8")


def _load(*names):
    tree = ast.parse(SOURCE)
    funcs = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    assert {node.name for node in funcs} == set(names)
    env = {}
    exec(compile(ast.Module(body=funcs, type_ignores=[]), str(GATE), "exec"), env)
    return env


FN = _load("_write_allowed", "_safe_off_allowed", "_observer_snapshot")
ENTITIES = frozenset({
    "number.brewzilla_target_temperature", "number.brewzilla_heat_utilization",
    "number.brewzilla_pump_utilization", "switch.brewzilla_heater", "switch.brewzilla_pump",
})
BASE = SimpleNamespace(BREWZILLA_HEATER_SWITCH="switch.brewzilla_heater",
                       BREWZILLA_PUMP_SWITCH="switch.brewzilla_pump",
                       BREWZILLA_HEAT_UTILIZATION="number.brewzilla_heat_utilization",
                       BREWZILLA_PUMP_UTILIZATION="number.brewzilla_pump_utilization")


def _allowed(mode, may_write, reason="source_blocked", *, rapt_stop=False, rapt_abort=False,
             entity="switch.brewzilla_heater", switch_action="on", value=None):
    authority = SimpleNamespace(mode=mode, may_write_brewzilla=may_write, reason=reason)
    context = {"runtime": {"source": "RAPT BrewZilla Profile" if rapt_stop else "Brewfather Brew Tracker",
                           "profile_stop_confirmed": rapt_stop, "profile_stop_guard_active": rapt_stop},
               "operator": {"active": rapt_abort, "source": "RAPT BrewZilla Profile" if rapt_abort else None}}
    ns = FN["_write_allowed"].__globals__
    ns.update(base=BASE, BREWZILLA_ENTITIES=ENTITIES,
              _live_authority=lambda hass: (authority, context),
              _safe_off_allowed=FN["_safe_off_allowed"])
    return FN["_write_allowed"](None, entity, switch_action=switch_action, value=value)


def test_brewfather_observer_denies_all_hot_side_writes_even_off():
    for entity in ENTITIES:
        assert not _allowed("brewfather_observer", False, entity=entity, switch_action="on", value=100)
        assert not _allowed("brewfather_observer", False, entity=entity, switch_action="off", value=0)
    assert _allowed("brewfather_observer", False, entity="switch.fermentation_heat_mat")


def test_verified_rapt_and_existing_manual_are_distinct():
    assert _allowed("rapt_controller", True)
    assert _allowed("manual_legacy_unresolved", None)
    assert not _allowed("blocked", False)


def test_confirmed_rapt_stop_can_safe_down_only():
    for entity in (BASE.BREWZILLA_HEATER_SWITCH, BASE.BREWZILLA_PUMP_SWITCH):
        assert _allowed("blocked", False, rapt_stop=True, entity=entity, switch_action="off")
        assert not _allowed("blocked", False, rapt_stop=True, entity=entity, switch_action="on")
    for entity in (BASE.BREWZILLA_HEAT_UTILIZATION, BASE.BREWZILLA_PUMP_UTILIZATION):
        assert _allowed("blocked", False, rapt_stop=True, entity=entity, value=0)
        assert not _allowed("blocked", False, rapt_stop=True, entity=entity, value=25)
    assert not _allowed("blocked", False, rapt_stop=True,
                        entity="number.brewzilla_target_temperature", value=95)


def test_abort_safe_down_is_scoped_to_rapt_not_bf():
    assert _allowed("blocked", False, rapt_abort=True, switch_action="off")
    assert not _allowed("blocked", False, rapt_abort=True, switch_action="on")
    assert not _allowed("brewfather_observer", False, switch_action="off")


def test_observer_snapshot_makes_no_false_physical_off_claim():
    out = FN["_observer_snapshot"]({"can_apply_target": True, "pump_stop_needed": True,
            "heater_action_needed": True}, SimpleNamespace(mode="brewfather_observer", reason="BF"))
    assert out["hot_side_actuator_writes_allowed"] is False
    assert out["hot_side_outputs_physically_off_verified"] is False
    assert not out["can_apply_target"] and not out["pump_stop_needed"]
    assert not out["heater_action_needed"]


def test_installation_covers_base_transport_policy_supervised_and_rapt_stop():
    for token in (
        "base._set_number = _set_number", "base._call_switch = _call_switch",
        "base._enforce_brewzilla_safe_state = _safe_state",
        "base.async_apply_brewzilla_target_if_allowed = _apply",
        "control_policy.execute_action = _policy_execute",
        "rapt_profile_runtime._async_safe_off_after_profile_stop = _rapt_stop",
        "supervised._BASE_BUILD = _supervised_build",
    ):
        assert token in SOURCE
