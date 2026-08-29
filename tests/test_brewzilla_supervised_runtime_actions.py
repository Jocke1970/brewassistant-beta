"""Regression checks for supervised BrewZilla runtime execution."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BREWZILLA_INIT = ROOT / "custom_components/brewassistant/brewzilla/__init__.py"
MANUAL_GUARD = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_manual_brew_control.py"
NO_POSITIVE = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_no_positive_gate.py"
SUPERVISED = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_supervised_runtime_guard.py"
SUPERVISED_CORE = ROOT / "custom_components/brewassistant/supervised_apply.py"
MANUAL_CARD = ROOT / "dashboard/cards/brewassistant_manual_brewday.yaml"
MANUAL_CARD_SV = ROOT / "dashboard/cards/brewassistant_manual_brewday_sv.yaml"


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


def test_brewzilla_confirmation_uses_registered_explicit_executor() -> None:
    guard = SUPERVISED.read_text(encoding="utf-8")
    core = SUPERVISED_CORE.read_text(encoding="utf-8")
    assert "register_supervised_executor" in guard
    assert "async def async_execute_confirmed_plan(" in guard
    assert "register_supervised_executor(SOURCE, KIND, async_execute_confirmed_plan)" in guard
    assert 'pending.get("source") != SOURCE' in guard
    assert 'pending.get("kind") != KIND' in guard
    assert "live_plan_id != expected_plan_id" in guard
    assert '"supervised_confirmation_consumed": True' in guard
    assert 'f"supervised_plan_stale:{blocked_reason}"' in guard
    assert "def register_supervised_executor(" in core
    assert "executor = _executor_for(pending)" in core
    assert "execution_result = await executor(hass, pending)" in core
    assert '"supervised_confirmed"' in core
    assert '"supervised_executed"' in core
    assert '"supervised_cancelled"' in core
    assert "Normal coordinator ticks never" in guard


def test_generic_supervised_fallback_retains_one_shot_grant() -> None:
    core = SUPERVISED_CORE.read_text(encoding="utf-8")
    assert "EXECUTION_GRANT_KEY" in core
    assert "def consume_execution_grant(" in core
    assert "_issue_execution_grant(hass, pending)" in core


def test_pending_sensor_is_refreshed_without_waiting_for_coordinator() -> None:
    core = SUPERVISED_CORE.read_text(encoding="utf-8")
    assert 'PENDING_SENSOR = "sensor.brewassistant_brewzilla_pending_action"' in core
    assert "def _schedule_pending_sensor_refresh(" in core
    assert "_schedule_pending_sensor_refresh(hass)" in core


def test_manual_heat_strike_has_explicit_ui_confirmation() -> None:
    for path in (MANUAL_CARD, MANUAL_CARD_SV):
        source = path.read_text(encoding="utf-8")
        heat_pos = source.index("name: Heat strike")
        next_pos = source.index("styles: *manual_action", heat_pos)
        heat_block = source[heat_pos:next_pos]
        assert "confirmation:" in heat_block
        assert "separate" in heat_block.lower() or "separat" in heat_block.lower()


def test_manual_card_surfaces_pending_supervised_plan() -> None:
    for path in (MANUAL_CARD, MANUAL_CARD_SV):
        source = path.read_text(encoding="utf-8")
        assert "sensor.brewassistant_brewzilla_pending_action" in source
        assert "button.brewassistant_confirm_supervised_apply" in source
        assert "button.brewassistant_cancel_supervised_apply" in source
        assert "confirmation:" in source
