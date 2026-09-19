"""Check source authority on the actual policy service destination, not metadata."""

from __future__ import annotations

import asyncio
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_policy_payload_guard.py"
IDENTITY = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_rapt_identity_guard.py"


@pytest.fixture
def rig(monkeypatch):
    for name in ("payload_contract", "payload_contract.brewassistant",
                 "payload_contract.brewassistant.brewzilla"):
        package = ModuleType(name)
        package.__path__ = []
        monkeypatch.setitem(sys.modules, name, package)
    calls, denials = [], []
    modes = {"current": "rapt_controller"}

    async def original(hass, action):
        calls.append(action)
        return {"status": "executed"}

    policy = ModuleType("payload_contract.brewassistant.control_policy")
    policy.execute_action = original
    policy._store_policy_result = lambda hass, result: denials.append(result) or result
    monkeypatch.setitem(sys.modules, policy.__name__, policy)

    authority = ModuleType("payload_contract.brewassistant.brewzilla.brewzilla_source_authority_runtime")
    authority.BREWZILLA_ENTITIES = frozenset({
        "number.brewzilla_target_temperature", "number.brewzilla_heat_utilization",
        "number.brewzilla_pump_utilization", "switch.brewzilla_heater", "switch.brewzilla_pump",
    })
    authority._live_authority = lambda hass: (SimpleNamespace(mode=modes["current"]), {})
    monkeypatch.setitem(sys.modules, authority.__name__, authority)

    name = "payload_contract.brewassistant.brewzilla.brewzilla_policy_payload_guard"
    spec = spec_from_file_location(name, SOURCE)
    guard = module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, guard)
    spec.loader.exec_module(guard)
    guard.install_policy_payload_guard()
    guard.install_policy_payload_guard()
    assert guard._PREVIOUS_EXECUTE is original
    return SimpleNamespace(policy=policy, modes=modes, calls=calls, denials=denials)


def _action(advertised, destination):
    return {"entity_id": advertised, "domain": "number", "service": "set_value",
            "service_data": {"entity_id": destination, "value": 95}}


def test_hidden_payload_and_aliases_never_reach_policy_dispatch(rig):
    for mode in ("rapt_controller", "brewfather_observer", "blocked"):
        rig.modes["current"] = mode
        for advertised, payload in (
            ("switch.kegerator_fan", "number.brewzilla_target_temperature"),
            (None, "number.brewzilla_target_temperature"),
            ("number.brewzilla_target_temperature", "switch.brewzilla_heater"),
            ("number.bryggeriet_brewzilla_target_temperature", "number.bryggeriet_brewzilla_target_temperature"),
            ("switch.brewzilla", "switch.brewzilla"),
            ("switch.kegerator_fan", ["switch.kegerator_fan", "switch.brewzilla_pump"]),
        ):
            result = asyncio.run(rig.policy.execute_action(None, _action(advertised, payload)))
            assert result["status"] == "source_authority_denied"
    assert rig.calls == []
    assert len(rig.denials) == 18


def test_canonical_actions_still_use_existing_authority_gate(rig):
    action = _action("number.brewzilla_target_temperature", "number.brewzilla_target_temperature")
    result = asyncio.run(rig.policy.execute_action(None, action))
    assert result["status"] == "executed"
    assert rig.calls == [action]  # Source/Sparge checks remain inside old execute.


def test_manual_and_unrelated_actions_preserve_original_dispatch(rig):
    rig.modes["current"] = "manual_legacy_unresolved"
    manual = _action("switch.brewzilla", "switch.brewzilla")
    result = asyncio.run(rig.policy.execute_action(None, manual))
    assert result["status"] == "executed"
    rig.modes["current"] = "rapt_controller"
    unrelated = _action("switch.kegerator_fan", "switch.kegerator_fan")
    result = asyncio.run(rig.policy.execute_action(None, unrelated))
    assert result["status"] == "executed"
    assert rig.calls == [manual, unrelated]


def test_policy_guard_installed_without_removing_existing_guard():
    text = IDENTITY.read_text(encoding="utf-8")
    assert "brewzilla_supervised_fallback_guard.install_supervised_fallback_guard()" in text
    assert "brewzilla_policy_payload_guard.install_policy_payload_guard()" in text
