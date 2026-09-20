"""Executable checks for the final observation-only request and writer boundary."""

from __future__ import annotations

import ast
import asyncio
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_observe_only_dispatch_guard.py"
PACKAGE = ROOT / "custom_components/brewassistant/brewzilla/__init__.py"


def _load(*names):
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    funcs = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
             and node.name in names]
    assert {node.name for node in funcs} == set(names)
    # AST extracts these functions without importing Home Assistant. Python
    # evaluates default argument expressions at function definition time.
    env = {"Any": object, "control_policy": SimpleNamespace(SOURCE_MANUAL="manual")}
    exec(compile(ast.Module(body=funcs, type_ignores=[]), str(MODULE), "exec"), env)
    return env


def test_observe_only_rejects_policy_request_before_creating_pending_plan():
    env = _load("_action_is_brewzilla", "_request_action")
    calls = []
    async def previous(hass, **kwargs):
        calls.append(kwargs)
        return {"status": "pending_confirmation"}
    def protected(value):
        return isinstance(value, str) and (value == "switch.brewzilla_heater"
            or value == "switch.brewzilla_pump")
    def build_action(**kwargs):
        return {"entity_id": "switch.unrelated", "service_data": {
            "entity_id": "switch.brewzilla_heater" if kwargs["command"] == "heater_on" else "switch.kegerator_fan"}}
    env.update(_PREVIOUS_REQUEST=previous,
        observer=SimpleNamespace(observation_required=lambda hass: True, _protected=protected),
        control_policy=SimpleNamespace(SOURCE_MANUAL="manual", build_action=build_action,
            _store_policy_result=lambda hass, result: result))
    denied = asyncio.run(env["_request_action"](None, section="heater", command="heater_on"))
    assert denied["status"] == "observe_only_denied"
    assert not calls
    allowed = asyncio.run(env["_request_action"](None, section="kegerator", command="fan_on"))
    assert allowed["status"] == "pending_confirmation" and len(calls) == 1


def test_final_writer_denies_main_switch_and_negative_commands_while_observing():
    env = _load("_write_allowed")
    calls = []
    def previous(hass, entity, *, switch_action=None, value=None):
        calls.append((entity, switch_action, value))
        return True
    protected = lambda entity: entity in {"switch.brewzilla", "switch.brewzilla_heater",
        "switch.bryggeriet_brewzilla_pump", "number.brewzilla_heat_utilization"}
    active = {"on": True}
    env.update(_PREVIOUS_WRITE_ALLOWED=previous,
               observer=SimpleNamespace(observation_required=lambda hass: active["on"],
                                        _protected=protected))
    for entity, action, value in (
        ("switch.brewzilla", "off", None),
        ("switch.brewzilla_heater", "off", None),
        ("switch.bryggeriet_brewzilla_pump", "on", None),
        ("number.brewzilla_heat_utilization", None, 0),
    ):
        assert env["_write_allowed"](None, entity, switch_action=action, value=value) is False
    assert not calls
    assert env["_write_allowed"](None, "switch.kegerator_fan", switch_action="on")
    active["on"] = False
    assert env["_write_allowed"](None, "switch.brewzilla", switch_action="off")
    assert len(calls) == 2


def test_final_dispatcher_is_installed_after_observer():
    package = PACKAGE.read_text(encoding="utf-8")
    assert package.index("_observe_only.install_observe_only_guard()") < package.index(
        "_observe_dispatch.install_observe_only_dispatch_guard()")
