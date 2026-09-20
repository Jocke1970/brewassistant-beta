"""Combined mock-dispatch regression tests for observation-only BrewZilla mode.

These execute the real function bodies extracted from their repository modules,
with a fake hardware service recorder. They are NOT a Home Assistant or physical
BrewZilla end-to-end test, nor do they prove already-dispatched calls can stop.
"""

from __future__ import annotations

import ast
import asyncio
from collections.abc import Mapping
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1] / "custom_components/brewassistant"
OBS = ROOT / "brewzilla/brewzilla_observe_only.py"
DISPATCH = ROOT / "brewzilla/brewzilla_observe_only_dispatch_guard.py"
SOURCE = ROOT / "brewzilla/brewzilla_source_authority_runtime.py"
FALLBACK = ROOT / "brewzilla/brewzilla_supervised_fallback_guard.py"

PROTECTED = frozenset({
    "number.brewzilla_target_temperature", "number.brewzilla_heat_utilization",
    "number.brewzilla_pump_utilization", "switch.brewzilla_heater",
    "switch.brewzilla_pump",
})


class Authority:
    def __init__(self, mode, may_write_brewzilla, reason):
        self.mode = mode
        self.may_write_brewzilla = may_write_brewzilla
        self.reason = reason


class RemoveRelativeImports(ast.NodeTransformer):
    def visit_ImportFrom(self, node):
        return None if node.level else node


def load_functions(path, *names, env=None):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    bodies = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
              and node.name in names]
    assert {node.name for node in bodies} == set(names)
    future = ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)
    result = ast.fix_missing_locations(RemoveRelativeImports().visit(
        ast.Module(body=[future, *bodies], type_ignores=[])))
    namespace = dict(env or {})
    exec(compile(result, str(path), "exec"), namespace)
    return namespace


def fixture_bundle():
    hass = SimpleNamespace(data={})
    hardware_calls = []
    policy_calls = []
    rapts = []
    learning_calls = []
    observer = load_functions(
        OBS, "_store", "observation_required", "observation_reason",
        "_live_authority", "_safe_off_allowed", "_protected", "_policy_execute", "_rapt_call",
        env={"HotSideAuthority": Authority, "Mapping": Mapping,
             "DOMAIN": "brewassistant", "DATA_KEY": "brewzilla_observe_only_runtime"},
    )
    observer["authority"] = SimpleNamespace(BREWZILLA_ENTITIES=PROTECTED)
    observer["base"] = SimpleNamespace(BREWZILLA_MAIN_SWITCH="switch.brewzilla")
    observer["_PREVIOUS_AUTHORITY"] = lambda h: (Authority("rapt_controller", True, "valid"), {})
    observer["_PREVIOUS_SAFE_OFF"] = lambda decision, context: True

    async def policy_previous(h, action):
        policy_calls.append(action)
        return {"status": "executed"}

    async def rapt_previous(*args):
        rapts.append(args)

    observer["_PREVIOUS_POLICY_EXECUTE"] = policy_previous
    observer["_PREVIOUS_RAPT_CALL"] = rapt_previous
    observer["control_policy"] = SimpleNamespace(_store_policy_result=lambda h, result: result)

    dispatch = load_functions(
        DISPATCH, "_action_is_brewzilla", "_request_action", "_write_allowed",
        env={"control_policy": SimpleNamespace(SOURCE_MANUAL="manual")},
    )
    dispatch["observer"] = SimpleNamespace(
        observation_required=observer["observation_required"],
        _protected=observer["_protected"],
    )
    dispatch["_PREVIOUS_WRITE_ALLOWED"] = lambda *args, **kwargs: True

    async def set_previous(h, entity, value):
        hardware_calls.append(("number", entity, value))
        return True

    async def switch_previous(h, action, entity):
        hardware_calls.append(("switch", entity, action))

    async def safe_previous(h, result, *, action_prefix, force=False):
        hardware_calls.append(("safe_state", action_prefix, force))

    async def learning_previous(h):
        learning_calls.append("apply")
        return {"applied": True}

    source = load_functions(
        SOURCE, "_set_number", "_call_switch", "_safe_state", "_learning_apply",
    )
    source.update(
        _live_authority=observer["_live_authority"],
        _safe_off_allowed=observer["_safe_off_allowed"],
        _write_allowed=dispatch["_write_allowed"],
        _PREVIOUS_SET=set_previous,
        _PREVIOUS_SWITCH=switch_previous,
        _PREVIOUS_SAFE_STATE=safe_previous,
        _PREVIOUS_LEARNING_APPLY=learning_previous,
    )
    return hass, observer, dispatch, source, hardware_calls, policy_calls, rapts, learning_calls


@pytest.mark.parametrize("target,command,value", [
    ("number.brewzilla_target_temperature", None, 40),
    ("number.brewzilla_heat_utilization", None, 0),
    ("number.brewzilla_pump_utilization", None, 70),
    ("switch.brewzilla_heater", "on", None),
    ("switch.brewzilla_heater", "off", None),
    ("switch.brewzilla_pump", "on", None),
    ("switch.brewzilla_pump", "off", None),
    ("switch.brewzilla", "off", None),
    ("switch.bryggeriet_brewzilla_pump", "off", None),
])
def test_observing_denies_positive_and_negative_writes_before_service(target, command, value):
    hass, observer, dispatch, source, hardware, *_ = fixture_bundle()
    assert observer["observation_required"](hass)
    assert dispatch["_write_allowed"](hass, target, switch_action=command, value=value) is False
    if target in PROTECTED:
        if command is None:
            with pytest.raises(PermissionError):
                asyncio.run(source["_set_number"](hass, target, value))
        else:
            with pytest.raises(PermissionError):
                asyncio.run(source["_call_switch"](hass, command, target))
    assert hardware == []


def test_observer_blocks_abort_safe_down_and_passive_learning_apply():
    hass, observer, dispatch, source, hardware, policy, rapts, learning = fixture_bundle()
    result = {}
    asyncio.run(source["_safe_state"](hass, result, action_prefix="abort_", force=True))
    assert result["safe_state_enforced"] is False
    assert result["safe_state_ok"] is False
    assert result["safe_state_heater_on"] is None
    assert result["safe_state_pump_on"] is None
    output = asyncio.run(source["_learning_apply"](hass))
    assert output["applied"] is False
    assert hardware == [] and learning == []


def test_observer_blocks_legacy_rapt_command_and_policy_router_even_off_zero():
    hass, observer, dispatch, source, hardware, policy, rapts, learning = fixture_bundle()
    with pytest.raises(PermissionError):
        asyncio.run(observer["_rapt_call"](hass, "switch", "turn_off", "switch.brewzilla_pump"))
    for target in ("switch.brewzilla", "switch.brewzilla_heater",
                   "number.bryggeriet_brewzilla_heat_utilization"):
        result = asyncio.run(observer["_policy_execute"](hass, {
            "entity_id": "switch.kegerator", "service_data": {"entity_id": target, "value": 0},
        }))
        assert result["status"] == "observe_only_denied"
    assert policy == [] and rapts == [] and hardware == []


def test_observer_denies_new_pending_policy_requests_and_generic_confirm_grants():
    hass, observer, dispatch, source, hardware, policy, rapts, learning = fixture_bundle()
    requested = []

    async def previous_request(h, **kwargs):
        requested.append(kwargs)
        return {"status": "pending_confirmation"}

    policy_api = SimpleNamespace(
        SOURCE_MANUAL="manual",
        build_action=lambda **kwargs: {
            "entity_id": "switch.unrelated",
            "service_data": {"entity_id": (
                "switch.brewzilla_heater" if kwargs["command"] == "heater_off"
                else "switch.kegerator_fan"
            )},
        },
        _store_policy_result=lambda h, result: result,
    )
    dispatch.update(control_policy=policy_api, _PREVIOUS_REQUEST=previous_request)
    rejected = asyncio.run(dispatch["_request_action"](
        hass, section="heater", command="heater_off"))
    assert rejected["status"] == "observe_only_denied"
    assert requested == []
    allowed = asyncio.run(dispatch["_request_action"](
        hass, section="fan", command="kegerator_fan_on"))
    assert allowed["status"] == "pending_confirmation" and len(requested) == 1

    issued = []
    fallback = load_functions(FALLBACK, "_brewzilla_action", "_issue_checked_grant")
    fallback["authority"] = SimpleNamespace(
        BREWZILLA_ENTITIES=PROTECTED,
        _live_authority=observer["_live_authority"],
    )
    fallback["_PREVIOUS_ISSUE_GRANT"] = lambda h, pending: issued.append(pending)
    with pytest.raises(PermissionError):
        fallback["_issue_checked_grant"](hass, {
            "entity_id": "switch.unrelated",
            "service_data": {"entity_id": ["switch.kegerator", "switch.brewzilla_heater"]},
        })
    assert issued == []


def test_off_switch_without_explicit_rearm_remains_blocked():
    hass, observer, dispatch, source, hardware, *_ = fixture_bundle()
    state = observer["_store"](hass)
    state.update(enabled=False, rearmed=False)
    assert observer["observation_required"](hass)
    assert dispatch["_write_allowed"](hass, "switch.brewzilla_heater", switch_action="on") is False
    state.update(rearmed=True)
    assert not observer["observation_required"](hass)
    assert dispatch["_write_allowed"](hass, "switch.brewzilla_heater", switch_action="on") is True
