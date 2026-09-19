"""Generic Supervised Apply must never bypass BrewZilla source authority.

Compile the original confirmation function and exercise its real synchronous
grant -> HA service-call seam with fake HA services. The test is not proof of
physical OFF or a complete Home Assistant installation.
"""

from __future__ import annotations

import ast
import asyncio
from copy import deepcopy
from datetime import datetime, timezone
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_supervised_fallback_guard.py"
SUPERVISED = ROOT / "custom_components/brewassistant/supervised_apply.py"
IDENTITY = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_rapt_identity_guard.py"
PROTECTED = frozenset({
    "number.brewzilla_target_temperature", "number.brewzilla_heat_utilization",
    "number.brewzilla_pump_utilization", "switch.brewzilla_heater", "switch.brewzilla_pump",
})


@pytest.fixture
def rig(monkeypatch):
    for name in ("fallback_contract", "fallback_contract.brewassistant",
                 "fallback_contract.brewassistant.brewzilla"):
        package = ModuleType(name)
        package.__path__ = []
        monkeypatch.setitem(sys.modules, name, package)
    calls = []
    modes = {"current": "rapt_controller"}
    fake_supervised = ModuleType("fallback_contract.brewassistant.supervised_apply")

    def original_issue(hass, pending):
        calls.append(("grant", pending.get("id")))
        hass.data["grant"] = {"id": pending.get("id")}
        return hass.data["grant"]

    fake_supervised._issue_execution_grant = original_issue
    monkeypatch.setitem(sys.modules, fake_supervised.__name__, fake_supervised)
    fake_source = ModuleType("fallback_contract.brewassistant.brewzilla.brewzilla_source_authority_runtime")
    fake_source.BREWZILLA_ENTITIES = PROTECTED
    fake_source._live_authority = lambda hass: (SimpleNamespace(mode=modes["current"]), {})
    monkeypatch.setitem(sys.modules, fake_source.__name__, fake_source)
    name = "fallback_contract.brewassistant.brewzilla.brewzilla_supervised_fallback_guard"
    spec = spec_from_file_location(name, GUARD)
    module = module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    module.install_supervised_fallback_guard()
    module.install_supervised_fallback_guard()
    assert module._PREVIOUS_ISSUE_GRANT is original_issue
    return SimpleNamespace(guard=module, supervised=fake_supervised, calls=calls, modes=modes)


def _action(entity_id, *, metadata_entity=None):
    return {"id": "old-plan", "source": "brewassistant_policy_router", "kind": "set_target_temperature",
            "domain": "number", "service": "set_value",
            "entity_id": metadata_entity if metadata_entity is not None else entity_id,
            "service_data": {"entity_id": entity_id, "value": 95}}


def test_all_source_modes_deny_direct_fallback_after_old_confirmation(rig):
    for mode in ("rapt_controller", "brewfather_observer", "blocked"):
        rig.modes["current"] = mode
        with pytest.raises(PermissionError, match="Generic Supervised Apply"):
            rig.supervised._issue_execution_grant(None, _action("number.brewzilla_target_temperature"))
    assert rig.calls == []


def test_guard_checks_payload_alias_lists_and_main_power(rig):
    for target in ("number.bryggeriet_brewzilla_target_temperature", "switch.brewzilla",
                   "switch.bryggeriet_brewzilla_heater",
                   ["switch.kegerator_fan", "switch.brewzilla_pump"]):
        with pytest.raises(PermissionError):
            rig.supervised._issue_execution_grant(None, _action(target, metadata_entity="switch.kegerator_fan"))
    assert rig.calls == []


def test_manual_and_unrelated_actions_keep_existing_grant(rig):
    rig.modes["current"] = "manual_legacy_unresolved"
    hass = SimpleNamespace(data={})
    rig.supervised._issue_execution_grant(hass, _action("number.brewzilla_target_temperature"))
    rig.modes["current"] = "rapt_controller"
    rig.supervised._issue_execution_grant(hass, _action("switch.kegerator_fan"))
    assert rig.calls == [("grant", "old-plan"), ("grant", "old-plan")]


def _actual_generic_confirm(rig, pending):
    source = ast.parse(SUPERVISED.read_text(encoding="utf-8"))
    selected = [node for node in source.body
                if isinstance(node, ast.AsyncFunctionDef) and node.name == "async_confirm_pending_action"]
    assert len(selected) == 1
    store = {"pending": pending}
    calls = []

    async def record(*args, **kwargs):
        return None

    async def service_call(domain, service, data, blocking):
        calls.append((domain, service, deepcopy(data)))
        store.pop("grant", None)

    hass = SimpleNamespace(data=store, services=SimpleNamespace(async_call=service_call))
    env = {
        "HomeAssistant": object, "Any": object, "deepcopy": deepcopy,
        "dt_util": SimpleNamespace(utcnow=lambda: datetime(2026, 9, 19, tzinfo=timezone.utc)),
        "_runtime_data": lambda hass: hass.data,
        "get_pending_action": lambda hass: hass.data.get("pending"),
        "_record_supervised_event": record,
        "_executor_for": lambda pending: None,
        "_schedule_pending_sensor_refresh": lambda hass: None,
        "_issue_execution_grant": rig.supervised._issue_execution_grant,
        "get_execution_grant": lambda hass: hass.data.get("grant"),
        "PENDING_KEY": "pending", "LAST_RESULT_KEY": "last", "EXECUTION_GRANT_KEY": "grant",
        "CANCELLED_KEY": "cancelled",
    }
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(SUPERVISED), "exec"), env)
    return asyncio.run(env["async_confirm_pending_action"](hass)), calls


def test_actual_confirmation_blocks_rapt_bt_allows_manual_and_unrelated(rig):
    for mode in ("rapt_controller", "brewfather_observer", "blocked"):
        rig.modes["current"] = mode
        outcome, service_calls = _actual_generic_confirm(rig, _action("number.brewzilla_target_temperature"))
        assert outcome["status"] == "error"
        assert service_calls == []
    rig.modes["current"] = "manual_legacy_unresolved"
    outcome, service_calls = _actual_generic_confirm(rig, _action("number.brewzilla_target_temperature"))
    assert outcome["status"] == "executed"
    assert len(service_calls) == 1
    rig.modes["current"] = "rapt_controller"
    outcome, service_calls = _actual_generic_confirm(rig, _action("switch.kegerator_fan"))
    assert outcome["status"] == "executed"
    assert len(service_calls) == 1


def test_guard_installs_after_identity_without_changing_registered_executors():
    text = IDENTITY.read_text(encoding="utf-8")
    assert "brewzilla_supervised_fallback_guard.install_supervised_fallback_guard()" in text
    source = GUARD.read_text(encoding="utf-8")
    assert "supervised_apply._issue_execution_grant = _issue_checked_grant" in source
    assert "register_supervised_executor" not in source
