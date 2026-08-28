"""Regression checks for Manual Brew operator-owned BrewZilla setpoints."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NUMBER_SOURCE = ROOT / "custom_components/brewassistant/number.py"
ADAPTER_SOURCE = ROOT / "custom_components/brewassistant/brewday/manual_brewday_adapter.py"
STORE_SOURCE = ROOT / "custom_components/brewassistant/brewday/manual_brewday_store.py"
CONTROL_SOURCE = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_manual_brew_control.py"
DASHBOARD_EN = ROOT / "dashboard/cards/brewassistant_manual_brewday.yaml"
DASHBOARD_SV = ROOT / "dashboard/cards/brewassistant_manual_brewday_sv.yaml"


def _literal_assignment(path: Path, name: str):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        else:
            continue
        if any(isinstance(target, ast.Name) and target.id == name for target in targets):
            return ast.literal_eval(node.value)
    raise AssertionError(f"Assignment {name} not found in {path}")


def test_manual_brewzilla_numbers_have_expected_steps_and_device_readbacks() -> None:
    numbers = _literal_assignment(NUMBER_SOURCE, "MANUAL_BREWZILLA_NUMBERS")

    target = numbers["brewzilla_manual_target_temperature"]
    heat = numbers["brewzilla_manual_heat_utilization"]
    pump = numbers["brewzilla_manual_pump_utilization"]

    assert target["object_id"] == "brewassistant_brewzilla_manual_target_temperature"
    assert target["step"] == 1.0
    assert target["device_entity"] == "number.brewzilla_target_temperature"

    assert heat["object_id"] == "brewassistant_brewzilla_manual_heat_utilization"
    assert heat["step"] == 5.0
    assert heat["device_entity"] == "number.brewzilla_heat_utilization"

    assert pump["object_id"] == "brewassistant_brewzilla_manual_pump_utilization"
    assert pump["step"] == 5.0
    assert pump["device_entity"] == "number.brewzilla_pump_utilization"


def test_manual_target_adapter_uses_ba_owned_setpoint_not_device_readback() -> None:
    source = ADAPTER_SOURCE.read_text(encoding="utf-8")
    assert 'MANUAL_TARGET_NUMBER = "number.brewassistant_brewzilla_manual_target_temperature"' in source
    assert 'MANUAL_TARGET_NUMBER = "number.brewzilla_target_temperature"' not in source


def test_manual_guard_keeps_reconciliation_enabled_for_operator_setpoints() -> None:
    source = CONTROL_SOURCE.read_text(encoding="utf-8")
    assert 'MANUAL_TARGET_SETPOINT = "number.brewassistant_brewzilla_manual_target_temperature"' in source
    assert 'MANUAL_HEAT_SETPOINT = "number.brewassistant_brewzilla_manual_heat_utilization"' in source
    assert 'MANUAL_PUMP_SETPOINT = "number.brewassistant_brewzilla_manual_pump_utilization"' in source
    assert "base._utilization_action_needed" in source


def test_manual_pause_overrides_operator_ownership_with_safe_down() -> None:
    source = CONTROL_SOURCE.read_text(encoding="utf-8")
    assert 'paused = bool(active and runtime_state == "paused")' in source
    assert '"manual_pause_safe_down_active": paused' in source
    assert '"desired_heat_utilization": 0.0' in source
    assert '"desired_pump_utilization": 0.0' in source
    assert '"desired_heater_on": False' in source
    assert '"desired_pump_on": False' in source
    assert '"heater_stop_needed": bool(out.get("heater_on"))' in source
    assert '"pump_stop_needed": bool(out.get("pump_on"))' in source
    assert '"target_sync_needed": False' in source
    assert "setpoints are retained for explicit resume" in source


def test_manual_brewfather_handoff_uses_runtime_activity_predicate() -> None:
    source = STORE_SOURCE.read_text(encoding="utf-8")
    assert "from .brewday_runtime_core import brewfather_session_active" in source
    assert "return brewfather_session_active(hass)" in source
    assert "BREWDAY_ACTIVE_STATUS" not in source
    assert "BF_STATUS" not in source


def test_manual_dashboard_uses_ba_owned_numeric_controls_in_both_languages() -> None:
    expected = {
        "number.brewassistant_brewzilla_manual_target_temperature",
        "number.brewassistant_brewzilla_manual_heat_utilization",
        "number.brewassistant_brewzilla_manual_pump_utilization",
    }
    for path in (DASHBOARD_EN, DASHBOARD_SV):
        source = path.read_text(encoding="utf-8")
        for entity_id in expected:
            assert entity_id in source, f"{entity_id} missing from {path.name}"
