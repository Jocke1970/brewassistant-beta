"""Execute production source/physical write guards without Home Assistant or BZ."""

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
           "_observer_snapshot", "_learning_apply")
ENTITIES = frozenset({
    "number.brewzilla_target_temperature", "number.brewzilla_heat_utilization",
    "number.brewzilla_pump_utilization", "switch.brewzilla_heater", "switch.brewzilla_pump",
})
BASE = SimpleNamespace(BREWZILLA_TARGET_NUMBER="number.brewzilla_target_temperature",
                       BREWZILLA_HEATER_SWITCH="switch.brewzilla_heater",
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
              _safe_off_allowed=FN["_safe_off_allowed"],
              _sparge_write_allowed=FN["_sparge_write_allowed"],
              sparge=SimpleNamespace(_observe=lambda hass: SimpleNamespace(phase="inactive")))
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
                        entity=BASE.BREWZILLA_TARGET_NUMBER, value=95)


def test_abort_safe_down_is_scoped_to_rapt_not_bf():
    assert _allowed("blocked", False, rapt_abort=True, switch_action="off")
    assert not _allowed("blocked", False, rapt_abort=True, switch_action="on")
    assert not _allowed("brewfather_observer", False, switch_action="off")


def test_sparge_physical_boundary_disallows_any_pump_restart_or_early_heat():
    ns = FN["_sparge_write_allowed"].__globals__
    ns["base"] = BASE
    physical = SimpleNamespace(phase="awaiting_lift", lift_confirmed=False)
    pump_ok = True
    temp = 80.0
    ns["sparge"] = SimpleNamespace(
        _observe=lambda hass: physical,
        _pump_safe_for_preboil=lambda hass: pump_ok,
        _preboil_temperature=lambda hass: temp,
        _readback=lambda hass, entity: ("off", True), PREBOIL_TARGET_C=95.0,
    )
    allowed = lambda entity, action=None, value=None: FN["_sparge_write_allowed"](
        None, entity, switch_action=action, value=value)
    assert allowed(BASE.BREWZILLA_HEATER_SWITCH, "off")
    assert allowed(BASE.BREWZILLA_PUMP_SWITCH, "off")
    assert allowed(BASE.BREWZILLA_HEAT_UTILIZATION, value=0)
    assert not allowed(BASE.BREWZILLA_HEATER_SWITCH, "on")
    assert not allowed(BASE.BREWZILLA_TARGET_NUMBER, value=95)
    physical.phase, physical.lift_confirmed = "heat_to_boil", True
    assert not allowed(BASE.BREWZILLA_PUMP_SWITCH, "on")
    assert not allowed(BASE.BREWZILLA_PUMP_UTILIZATION, value=25)
    assert not allowed(BASE.BREWZILLA_TARGET_NUMBER, value=100)
    assert allowed(BASE.BREWZILLA_TARGET_NUMBER, value=95)
    assert allowed(BASE.BREWZILLA_HEATER_SWITCH, "on")
    ns["sparge"]._pump_safe_for_preboil = lambda hass: False
    assert not allowed(BASE.BREWZILLA_HEATER_SWITCH, "on")
    assert not allowed(BASE.BREWZILLA_TARGET_NUMBER, value=95)


def test_learning_apply_denies_bf_and_rapt_direct_bypass():
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
    assert count == ["called"]


def test_observer_snapshot_makes_no_false_physical_off_claim():
    out = FN["_observer_snapshot"]({"can_apply_target": True, "pump_stop_needed": True,
            "heater_action_needed": True}, SimpleNamespace(mode="brewfather_observer", reason="BF"))
    assert out["hot_side_actuator_writes_allowed"] is False
    assert out["hot_side_outputs_physically_off_verified"] is False
    assert not out["can_apply_target"] and not out["pump_stop_needed"]
    assert not out["heater_action_needed"]


def test_installation_covers_base_policy_learning_supervised_and_rapt_stop():
    for token in (
        "base._set_number = _set_number", "base._call_switch = _call_switch",
        "base._enforce_brewzilla_safe_state = _safe_state",
        "base.async_apply_brewzilla_target_if_allowed = _apply",
        "control_policy.execute_action = _policy_execute",
        "learning.async_apply_brewzilla_learning_recommendation = _learning_apply",
        "rapt_profile_runtime._async_safe_off_after_profile_stop = _rapt_stop",
        "supervised._BASE_BUILD = _supervised_build",
    ):
        assert token in SOURCE
