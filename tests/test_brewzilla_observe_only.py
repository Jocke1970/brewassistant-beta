"""Executable fail-passive acceptance checks for operator observation-only mode."""

from __future__ import annotations

import ast
import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_observe_only.py"
SOURCE = MODULE.read_text(encoding="utf-8")
PACKAGE = ROOT / "custom_components/brewassistant/brewzilla/__init__.py"
SWITCH_PLATFORM = ROOT / "custom_components/brewassistant/switch.py"
UI = ROOT / "dashboard/cards/brewzilla_observe_only_sv.yaml"


class Authority:
    def __init__(self, mode, may_write_brewzilla, reason):
        self.mode = mode
        self.may_write_brewzilla = may_write_brewzilla
        self.reason = reason


class HomeAssistantError(Exception):
    pass


class StripRelativeImports(ast.NodeTransformer):
    def visit_ImportFrom(self, node):
        return None if node.level else node


def _load(*names):
    tree = ast.parse(SOURCE)
    functions = [node for node in tree.body
                 if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                 and node.name in names]
    assert {node.name for node in functions} == set(names)
    module = StripRelativeImports().visit(ast.Module(body=functions, type_ignores=[]))
    ast.fix_missing_locations(module)
    env = {"DOMAIN": "brewassistant", "DATA_KEY": "brewzilla_observe_only_runtime",
           "HotSideAuthority": Authority, "HomeAssistantError": HomeAssistantError,
           "MAX_REARM_AGE_SECONDS": 90, "REARM_SERVICE": "brewzilla_rearm_after_observe"}
    exec(compile(module, str(MODULE), "exec"), env)
    return env


def _hass():
    return SimpleNamespace(data={}, states=SimpleNamespace(get=lambda entity: None),
                           services=SimpleNamespace())


def test_missing_state_and_restored_off_fail_closed_without_rearm():
    env = _load("_store", "observation_required", "observation_reason")
    hass = _hass()
    assert env["observation_required"](hass) is True
    assert env["observation_reason"](hass) == "operator_observe_only"
    store = env["_store"](hass)
    store.update(enabled=False, rearmed=False)
    assert env["observation_required"](hass) is True
    assert env["observation_reason"](hass) == "operator_rearm_required"
    store["rearmed"] = True
    assert env["observation_required"](hass) is False
    store["enabled"] = True
    assert env["observation_required"](hass) is True


def test_final_authority_and_safe_down_both_denied_in_observation():
    env = _load("_store", "observation_required", "observation_reason",
                "_live_authority", "_safe_off_allowed")
    hass = _hass()
    env["_PREVIOUS_AUTHORITY"] = lambda h: (Authority("rapt_controller", True, "verified"), {})
    env["_PREVIOUS_SAFE_OFF"] = lambda decision, context: True
    decision, context = env["_live_authority"](hass)
    assert decision.mode == "blocked" and decision.may_write_brewzilla is False
    assert env["_safe_off_allowed"](decision, context) is False
    env["_store"](hass).update(enabled=False, rearmed=True)
    decision, context = env["_live_authority"](hass)
    assert decision.mode == "rapt_controller" and decision.may_write_brewzilla is True
    assert env["_safe_off_allowed"](decision, context) is True


def test_actual_payload_and_aliases_protected_including_main_power():
    env = _load("_protected")
    env["authority"] = SimpleNamespace(BREWZILLA_ENTITIES=frozenset({
        "switch.brewzilla_heater", "switch.brewzilla_pump",
        "number.brewzilla_target_temperature", "number.brewzilla_heat_utilization",
        "number.brewzilla_pump_utilization"}))
    env["base"] = SimpleNamespace(BREWZILLA_MAIN_SWITCH="switch.brewzilla")
    protect = env["_protected"]
    assert protect("switch.brewzilla")
    assert protect("switch.brewzilla_heater")
    assert protect("switch.bryggeriet_brewzilla_heater")
    assert protect("number.bryggeriet_brewzilla_heat_utilization")
    assert protect(["switch.kegerator", "switch.brewzilla_pump"])
    assert not protect("switch.fermentation_heat_mat")


def test_policy_router_never_dispatches_positive_or_negative_observe_commands():
    env = _load("_store", "observation_required", "_protected", "_policy_execute")
    env["authority"] = SimpleNamespace(BREWZILLA_ENTITIES=frozenset({
        "switch.brewzilla_heater", "switch.brewzilla_pump", "number.brewzilla_target_temperature",
        "number.brewzilla_heat_utilization", "number.brewzilla_pump_utilization"}))
    env["base"] = SimpleNamespace(BREWZILLA_MAIN_SWITCH="switch.brewzilla")
    calls = []
    async def previous(hass, action):
        calls.append(action)
        return {"status": "executed"}
    env["_PREVIOUS_POLICY_EXECUTE"] = previous
    env["control_policy"] = SimpleNamespace(_store_policy_result=lambda hass, data: data)
    hass = _hass()
    for service, target, value in (
        ("turn_on", "switch.brewzilla_heater", None),
        ("turn_off", "switch.brewzilla_pump", None),
        ("set_value", "number.brewzilla_heat_utilization", 0),
        ("set_value", "number.bryggeriet_brewzilla_target_temperature", 40),
        ("turn_off", "switch.brewzilla", None),
    ):
        action = {"entity_id": "switch.unrelated", "service": service,
                  "service_data": {"entity_id": target, "value": value}}
        assert asyncio.run(env["_policy_execute"](hass, action))["status"] == "observe_only_denied"
    assert calls == []
    assert asyncio.run(env["_policy_execute"](hass, {
        "entity_id": "switch.kegerator", "service_data": {"entity_id": "switch.kegerator"},
    }))["status"] == "executed"
    assert len(calls) == 1


def test_transition_revokes_pending_and_lease_without_actuator_calls():
    env = _load("_invalidate")
    cleared = []
    lease = {"lease": {"target": 40}}
    env.update(clear_pending_action=lambda h, reason: cleared.append(("pending", reason)),
               clear_owned_control=lambda h, reason: cleared.append(("owned", reason)),
               local_lease=SimpleNamespace(_store=lambda h: lease),
               dt_util=SimpleNamespace(utcnow=lambda: SimpleNamespace(isoformat=lambda: "now")))
    hass = _hass()
    env["_invalidate"](hass, "observe_only_enabled")
    assert lease["lease"] is None and lease["previous_lease"]["target"] == 40
    assert cleared == [("pending", "observe_only_enabled"), ("owned", "observe_only_enabled")]
    # No hass.services is even present as a callable in this fixture.


def test_existing_snapshot_is_observation_not_false_physical_off():
    env = _load("_store", "observation_required", "observation_reason", "_build")
    env["_PREVIOUS_BUILD"] = lambda hass: {"heater_on": True, "heat_utilization": 0,
                                          "pump_on": False, "can_apply_target": True}
    def observer(snapshot, authority):
        return {**snapshot, "hot_side_actuator_writes_allowed": False,
                "hot_side_outputs_physically_off_verified": False,
                "can_apply_target": False}
    env["authority"] = SimpleNamespace(_observer_snapshot=observer)
    result = env["_build"](_hass())
    assert result["orchestration_mode"] == "observe-only"
    assert result["heater_on"] is True
    assert result["hot_side_outputs_physically_off_verified"] is False
    assert result["hot_side_actuator_writes_allowed"] is False


def test_legacy_rapt_output_path_stays_passive():
    env = _load("_store", "observation_required", "_rapt_call")
    calls = []
    async def previous(*args):
        calls.append(args)
    env["_PREVIOUS_RAPT_CALL"] = previous
    hass = _hass()
    with pytest.raises(PermissionError):
        asyncio.run(env["_rapt_call"](hass, "switch", "turn_off", "switch.brewzilla_heater"))
    assert calls == []


def test_explicit_rearm_denies_missing_or_unverified_source():
    env = _load("_store", "async_rearm")
    hass = _hass()
    with pytest.raises(HomeAssistantError):
        asyncio.run(env["async_rearm"](hass))
    env["_store"](hass).update(enabled=False, rearmed=False)
    env["_PREVIOUS_AUTHORITY"] = lambda h: (Authority("blocked", False, "stale"), {})
    with pytest.raises(HomeAssistantError):
        asyncio.run(env["async_rearm"](hass))
    assert env["_store"](hass)["rearmed"] is False


def test_platform_installs_final_guard_and_real_switch_and_ui():
    package = PACKAGE.read_text(encoding="utf-8")
    assert package.index("_rapt_identity_guard.install_rapt_identity_guard()") < package.index(
        "_observe_only.install_observe_only_guard()")
    assert "BrewAssistantBrewZillaObserveOnlySwitch(coordinator)" in SWITCH_PLATFORM.read_text(encoding="utf-8")
    card = UI.read_text(encoding="utf-8")
    assert "switch.brewassistant_brewzilla_observe_only" in card
    assert "brewassistant.brewzilla_rearm_after_observe" in card
    # The ON handler must never write to any physical output or call safe-down.
    tree = ast.parse(SOURCE)
    switch = next(n for n in tree.body if isinstance(n, ast.ClassDef)
                  and n.name == "BrewAssistantBrewZillaObserveOnlySwitch")
    on = next(n for n in switch.body if isinstance(n, ast.AsyncFunctionDef)
              and n.name == "async_turn_on")
    text = ast.unparse(on)
    for forbidden in ("async_call(", "_set_number(", "_call_switch(", "_safe_state("):
        assert forbidden not in text
