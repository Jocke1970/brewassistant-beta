"""Regression checks for supervised BrewZilla runtime execution."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BREWZILLA_INIT = ROOT / "custom_components/brewassistant/brewzilla/__init__.py"
MANUAL_GUARD = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_manual_brew_control.py"
NO_POSITIVE = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_no_positive_gate.py"
SUPERVISED = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_supervised_runtime_guard.py"


def test_manual_prepared_is_a_safe_boundary() -> None:
    source = MANUAL_GUARD.read_text(encoding="utf-8")
    assert 'prepared = bool(active and runtime_state == "prepared")' in source
    assert "safe_boundary = bool(paused or prepared)" in source
    assert '"manual_prepare_safe_down_active": prepared' in source
    assert '"target_sync_needed": False' in source
    assert '"desired_heat_utilization": 0.0' in source
    assert '"desired_pump_utilization": 0.0' in source
    assert '"heater_action_needed": False' in source
    assert '"pump_action_needed": False' in source
    assert "operator starts Heat strike" in source


def test_generic_no_positive_gate_includes_prepared() -> None:
    source = NO_POSITIVE.read_text(encoding="utf-8")
    assert '"prepared",' in source


def test_supervised_guard_is_installed_after_manual_ownership() -> None:
    source = BREWZILLA_INIT.read_text(encoding="utf-8")
    manual_pos = source.index("_manual_brew_control.install_manual_brew_control_guard()")
    supervised_pos = source.index("_supervised_runtime_guard.install_supervised_runtime_guard()")
    assert supervised_pos > manual_pos


def test_positive_auto_actions_are_bundled_for_confirmation() -> None:
    source = SUPERVISED.read_text(encoding="utf-8")
    assert '"key": "target_up"' in source
    assert '"key": "heat_up"' in source
    assert '"key": "heater_on"' in source
    assert '"key": "pump_up"' in source
    assert '"key": "pump_on"' in source
    assert '"kind": KIND' in source
    assert '"service": "apply_brewzilla_target"' in source
    assert '"apply_result": "pending_confirmation"' in source


def test_manual_owned_values_and_safe_down_bypass_confirmation() -> None:
    source = SUPERVISED.read_text(encoding="utf-8")
    assert "snapshot.get(\"manual_target_override_active\")" in source
    assert "snapshot.get(\"manual_heat_override_active\")" in source
    assert "snapshot.get(\"manual_pump_override_active\")" in source
    assert 'await base._call_switch(hass, "off", base.BREWZILLA_HEATER_SWITCH)' in source
    assert 'await base._call_switch(hass, "off", base.BREWZILLA_PUMP_SWITCH)' in source


def test_confirmation_revalidates_live_plan() -> None:
    source = SUPERVISED.read_text(encoding="utf-8")
    assert 'last.get("status") == "executing"' in source
    assert "_confirmation_matches(hass, plan_id)" in source
    assert '"apply_result": "supervised_plan_stale"' in source
    assert "Runtime progression is never paused by this guard" in source
