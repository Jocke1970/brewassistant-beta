"""Executable fail-passive checks for BA's single read-only switch."""

from __future__ import annotations

import ast
import asyncio
from collections.abc import Mapping
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
        self.mode, self.may_write_brewzilla, self.reason = mode, may_write_brewzilla, reason


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
           "MAX_REARM_AGE_SECONDS": 90, "REARM_SERVICE": "brewzilla_rearm_after_observe",
           "Mapping": Mapping}
    exec(compile(module, str(MODULE), "exec"), env)
    return env


def _hass():
    return SimpleNamespace(data={}, states=SimpleNamespace(get=lambda entity: None),
                           services=SimpleNamespace())


def test_missing_state_and_unverified_off_fail_closed():
    env = _load("_store", "observation_required", "observation_reason")
    hass = _hass()
    assert env["observation_required"](hass)
    store = env["_store"](hass)
    store.update(enabled=False, rearmed=False)
    assert env["observation_required"](hass)
    assert env["observation_reason"](hass) == "operator_rearm_required"
    store["rearmed"] = True
    assert not env["observation_required"](hass)
    store["enabled"] = True
    assert env["observation_required"](hass)


def test_final_authority_and_ordinary_safe_down_denied_in_observation():
    env = _load("_store", "observation_required", "observation_reason",
                "_live_authority", "_safe_off_allowed")
    hass = _hass()
    env["_PREVIOUS_AUTHORITY"] = lambda h: (Authority("rapt_controller", True, "verified"), {})
    env["_PREVIOUS_SAFE_OFF"] = lambda decision, context: True
    decision, context = env["_live_authority"](hass)
    assert decision.mode == "blocked" and decision.may_write_brewzilla is False
    assert not env["_safe_off_allowed"](decision, context)
    env["_store"](hass).update(enabled=False, rearmed=True)
    decision, context = env["_live_authority"](hass)
    assert decision.mode == "rapt_controller" and env["_safe_off_allowed"](decision, context)


def test_actual_payload_and_aliases_protected_including_main_power():
    env = _load("_protected")
    env["authority"] = SimpleNamespace(BREWZILLA_ENTITIES=frozenset({
        "switch.brewzilla_heater", "switch.brewzilla_pump", "number.brewzilla_target_temperature",
        "number.brewzilla_heat_utilization", "number.brewzilla_pump_utilization"}))
    env["base"] = SimpleNamespace(BREWZILLA_MAIN_SWITCH="switch.brewzilla")
    check = env["_protected"]
    for item in ("switch.brewzilla", "switch.brewzilla_heater", "switch.bryggeriet_brewzilla_heater",
                 "number.bryggeriet_brewzilla_heat_utilization", ["switch.kegerator", "switch.brewzilla_pump"]):
        assert check(item)
    assert not check("switch.fermentation_heat_mat")


def test_policy_router_denies_on_off_zero_and_hidden_targets():
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
    for service, target in (("turn_on", "switch.brewzilla_heater"),
                            ("turn_off", "switch.brewzilla_pump"),
                            ("set_value", "number.brewzilla_heat_utilization"),
                            ("set_value", "number.bryggeriet_brewzilla_target_temperature"),
                            ("turn_off", "switch.brewzilla")):
        action = {"entity_id": "switch.unrelated", "service": service,
                  "service_data": {"entity_id": target, "value": 0}}
        assert asyncio.run(env["_policy_execute"](hass, action))["status"] == "observe_only_denied"
    assert not calls
    assert asyncio.run(env["_policy_execute"](hass, {
        "entity_id": "switch.kegerator", "service_data": {"entity_id": "switch.kegerator"},
    }))["status"] == "executed"
    assert len(calls) == 1


def test_transition_discards_intent_and_lease_without_actuator_calls():
    env = _load("_invalidate")
    cleared = []
    lease = {"lease": {"target": 40}}
    env.update(clear_pending_action=lambda h, reason: cleared.append(("pending", reason)),
               clear_owned_control=lambda h, reason: cleared.append(("owned", reason)),
               local_lease=SimpleNamespace(_store=lambda h: lease),
               dt_util=SimpleNamespace(utcnow=lambda: SimpleNamespace(isoformat=lambda: "now")))
    env["_invalidate"](_hass(), "observe_only_enabled")
    assert lease["lease"] is None and lease["previous_lease"]["target"] == 40
    assert cleared == [("pending", "observe_only_enabled"), ("owned", "observe_only_enabled")]


def test_observer_snapshot_never_claims_physically_off():
    env = _load("_store", "observation_required", "observation_reason", "_build")
    env["_PREVIOUS_BUILD"] = lambda h: {"heater_on": True, "pump_on": False, "can_apply_target": True}
    env["authority"] = SimpleNamespace(_observer_snapshot=lambda snapshot, authority: {
        **snapshot, "hot_side_actuator_writes_allowed": False,
        "hot_side_outputs_physically_off_verified": False, "can_apply_target": False})
    result = env["_build"](_hass())
    assert result["orchestration_mode"] == "observe-only" and result["heater_on"] is True
    assert result["hot_side_outputs_physically_off_verified"] is False
    assert result["hot_side_actuator_writes_allowed"] is False
    assert result["emergency_abort_always_available"] is True


def test_ordinary_legacy_rapt_output_path_remains_passive():
    env = _load("_store", "observation_required", "_rapt_call")
    calls = []
    async def previous(*args):
        calls.append(args)
    env["_PREVIOUS_RAPT_CALL"] = previous
    with pytest.raises(PermissionError):
        asyncio.run(env["_rapt_call"](_hass(), "switch", "turn_off", "switch.brewzilla_heater"))
    assert not calls


def test_rearm_denies_missing_source_and_abort():
    env = _load("_store", "async_rearm")
    hass = _hass()
    with pytest.raises(HomeAssistantError):
        asyncio.run(env["async_rearm"](hass))
    env["_store"](hass).update(enabled=False, rearmed=False)
    env["_PREVIOUS_AUTHORITY"] = lambda h: (Authority("blocked", False, "stale"), {})
    env["brewday_operator_abort_active"] = lambda h: False
    with pytest.raises((HomeAssistantError, ImportError)):
        asyncio.run(env["async_rearm"](hass))
    assert env["_store"](hass)["rearmed"] is False


def test_registration_one_switch_emergency_and_on_path_without_output():
    package = PACKAGE.read_text(encoding="utf-8")
    assert package.index("_rapt_identity_guard.install_rapt_identity_guard()") < package.index(
        "_observe_only.install_observe_only_guard()")
    assert package.index("_observe_dispatch.install_observe_only_dispatch_guard()") < package.index(
        "_emergency_abort.install_emergency_abort()")
    assert "BrewAssistantBrewZillaObserveOnlySwitch(coordinator)" in SWITCH_PLATFORM.read_text(encoding="utf-8")
    card = UI.read_text(encoding="utf-8")
    assert card.count("entity: switch.brewassistant_brewzilla_observe_only") >= 1
    assert "brewassistant.abort_brewzilla" in card
    assert "brewassistant.brewzilla_rearm_after_observe" not in card
    assert "number.brewzilla_target_temperature" in card
    assert "sensor.brewassistant_brewday_runtime_source" in card
    tree = ast.parse(SOURCE)
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef)
               and node.name == "BrewAssistantBrewZillaObserveOnlySwitch")
    on = next(node for node in cls.body if isinstance(node, ast.AsyncFunctionDef)
              and node.name == "async_turn_on")
    off = next(node for node in cls.body if isinstance(node, ast.AsyncFunctionDef)
               and node.name == "async_turn_off")
    restore = next(node for node in cls.body if isinstance(node, ast.AsyncFunctionDef)
                   and node.name == "async_added_to_hass")
    for forbidden in ("async_call(", "_set_number(", "_call_switch(", "_safe_state("):
        assert forbidden not in ast.unparse(on)
    assert "await async_rearm(self.hass)" in ast.unparse(off)
    assert 'self._attr_is_on = True' in ast.unparse(restore)
