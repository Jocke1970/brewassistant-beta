"""Alias checks for the direct writer, not just the generic policy router."""

from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_direct_entity_guard.py"
SOURCE = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_source_authority_runtime.py"
IDENTITY = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_rapt_identity_guard.py"
CANONICAL = frozenset({
    "number.brewzilla_target_temperature", "number.brewzilla_heat_utilization",
    "number.brewzilla_pump_utilization", "switch.brewzilla_heater",
    "switch.brewzilla_pump",
})


@pytest.fixture
def rig(monkeypatch):
    for name in ("direct_contract", "direct_contract.brewassistant",
                 "direct_contract.brewassistant.brewzilla"):
        package = ModuleType(name)
        package.__path__ = []
        monkeypatch.setitem(sys.modules, name, package)
    mode = {"value": "rapt_controller"}
    delegated = []
    source = ModuleType("direct_contract.brewassistant.brewzilla.brewzilla_source_authority_runtime")
    source.BREWZILLA_ENTITIES = CANONICAL
    source._live_authority = lambda hass: (SimpleNamespace(mode=mode["value"]), {})

    def previous(hass, entity, *, switch_action=None, value=None):
        delegated.append((entity, switch_action, value))
        return True

    source._write_allowed = previous
    monkeypatch.setitem(sys.modules, source.__name__, source)
    name = "direct_contract.brewassistant.brewzilla.brewzilla_direct_entity_guard"
    spec = spec_from_file_location(name, GUARD)
    module = module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    module.install_direct_entity_guard()
    module.install_direct_entity_guard()
    assert module._PREVIOUS_WRITE is previous
    return SimpleNamespace(source=source, mode=mode, delegated=delegated)


def test_source_modes_block_prefixed_actuators_and_main_power_before_dispatch(rig):
    aliased = (
        "number.bryggeriet_brewzilla_target_temperature",
        "number.bryggeriet_brewzilla_heat_utilization",
        "number.bryggeriet_brewzilla_pump_utilization",
        "switch.bryggeriet_brewzilla_heater",
        "switch.bryggeriet_brewzilla_pump",
        "switch.brewzilla",
        "switch.bryggeriet_brewzilla",
        "number.BREWZILLA_target_temperature",
    )
    for mode in ("rapt_controller", "brewfather_observer", "blocked"):
        rig.mode["value"] = mode
        for entity in aliased:
            assert rig.source._write_allowed(None, entity, switch_action="on", value=95) is False
    assert rig.delegated == []


def test_canonical_control_preserves_all_existing_source_and_sparge_checks(rig):
    for entity in CANONICAL:
        assert rig.source._write_allowed(None, entity, switch_action="on", value=95) is True
    assert {call[0] for call in rig.delegated} == CANONICAL


def test_manual_alias_and_unrelated_equipment_remain_untouched(rig):
    rig.mode["value"] = "manual_legacy_unresolved"
    assert rig.source._write_allowed(None, "number.bryggeriet_brewzilla_target_temperature", value=65)
    assert rig.source._write_allowed(None, "switch.brewzilla", switch_action="off")
    rig.mode["value"] = "rapt_controller"
    assert rig.source._write_allowed(None, "switch.fermentation_heat_mat", switch_action="on")
    assert rig.source._write_allowed(None, "switch.hlt", switch_action="on")
    assert len(rig.delegated) == 4


def test_guard_installed_on_real_direct_writer_lookup_without_removing_old_chain():
    source = SOURCE.read_text(encoding="utf-8")
    identity = IDENTITY.read_text(encoding="utf-8")
    assert "if not _write_allowed(hass, entity_id, value=value):" in source
    assert "if not _write_allowed(hass, entity_id, switch_action=service_suffix):" in source
    assert "brewzilla_sparge_local_target_guard.install_sparge_local_target_guard()" in identity
    assert "brewzilla_policy_payload_guard.install_policy_payload_guard()" in identity
    assert "brewzilla_direct_entity_guard.install_direct_entity_guard()" in identity
