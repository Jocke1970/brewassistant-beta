"""Regression checks for RAPT profile runtime under three-mode Brewday."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAPT_RUNTIME = ROOT / "custom_components/brewassistant/brewday/rapt_profile_runtime.py"
RUNTIME = ROOT / "custom_components/brewassistant/brewday/brewday_runtime.py"
EXECUTION = ROOT / "custom_components/brewassistant/brewday/brewday_execution_mode.py"
RAPT_CONTROL_BRIDGE = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_rapt_profile_control_bridge.py"
AUTHORITY = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_source_authority_runtime.py"
SUPERVISED = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_supervised_runtime_guard.py"
RAPT_CARD = ROOT / "dashboard/cards/rapt_profile_runtime.yaml"
RAPT_CARD_SV = ROOT / "dashboard/cards/rapt_profile_runtime_sv.yaml"


def test_sources_parse():
    for path in (RAPT_RUNTIME, RUNTIME, EXECUTION, RAPT_CONTROL_BRIDGE, AUTHORITY, SUPERVISED):
        ast.parse(path.read_text(encoding="utf-8"))


def test_three_modes_and_rcl_priority_are_explicit():
    runtime = RUNTIME.read_text(encoding="utf-8")
    execution = EXECUTION.read_text(encoding="utf-8")
    arbitration = runtime.split("def build_brewday_runtime_snapshot", 1)[1]
    for mode in ("Manual Brewing", "Brewfather Brewing", "RCL Brewing"):
        assert mode in execution
    assert arbitration.index("build_rapt_profile_runtime_snapshot(hass)") < arbitration.index(
        "runtime_source = core_source(hass)"
    )
    assert "build_manual_fallback_snapshot" in arbitration
    assert "remember_external_snapshot" in arbitration


def test_rcl_bridge_never_rewrites_profile_target_and_declares_split_ownership():
    bridge = RAPT_CONTROL_BRIDGE.read_text(encoding="utf-8")
    assert 'out["target_temperature"] = strike_hold_target' not in bridge
    assert '"target_transport_owner": "rapt_brewzilla"' in bridge
    assert '"heater_switch_owner": "brewzilla_local_thermostat"' in bridge
    assert '"heat_utilization_owner": "brewassistant_learning"' in bridge
    assert '"pump_owner": "brewassistant_learning"' in bridge
    assert '"direct_target_control_allowed": False' in bridge
    assert '"direct_heater_control_allowed": False' in bridge
    assert '"rapt_target_control_suppressed": True' in bridge
    assert '"brewassistant_role": "rcl_heat_pump_assist"' in bridge


def test_rcl_assist_writer_scope_and_auto_learning_are_explicit():
    authority = AUTHORITY.read_text(encoding="utf-8")
    supervised = SUPERVISED.read_text(encoding="utf-8")
    assert "def _rcl_assist_write_allowed" in authority
    assert "base.BREWZILLA_TARGET_NUMBER, base.BREWZILLA_HEATER_SWITCH" in authority
    assert "rcl_assist_auto_apply=True" in authority
    assert 'allowed = {"heat_up", "pump_up", "pump_on"}' in supervised


def test_source_loss_becomes_manual_fallback_with_retained_recipe_context():
    runtime = RUNTIME.read_text(encoding="utf-8")
    execution = EXECUTION.read_text(encoding="utf-8")
    assert 'reason=f"rcl_{rapt_state}"' in runtime
    assert 'reason="brewfather_source_unavailable"' in runtime
    assert '"source": "Manual Brewday"' in execution
    assert '"recipe_context_retained": recipe_context_retained' in execution
    assert '"fallback_external_timeline_frozen": True' in execution
    assert '"manual_plan_operator_progression_until_source_recovers"' in execution
    assert '"reconnect_expected": reconnect_expected' in execution
    assert '"fresh_brewzilla_readback"' in execution
    assert '"cached_external_recipe"' in execution


def test_reconnect_automatically_precedes_fallback():
    runtime = RUNTIME.read_text(encoding="utf-8")
    arbitration = runtime.split("def build_brewday_runtime_snapshot", 1)[1]
    assert arbitration.index("if rapt_live:") < arbitration.index(
        'if rapt_state in {"source_unavailable", "source_unverified"}'
    )
    assert arbitration.index('runtime_source == "Brewfather Brew Tracker"') < arbitration.index(
        'execution_mode.last_external_mode(hass) == execution_mode.BREWFATHER_BREWING'
    )


def test_confirmed_rcl_stop_releases_source_arbitration_but_safe_off_code_remains():
    rapt = RAPT_RUNTIME.read_text(encoding="utf-8")
    isolation = (ROOT / "custom_components/brewassistant/brewzilla/brewzilla_rapt_brewing_read_isolation.py").read_text(encoding="utf-8")
    assert "def _fresh_stopped_contract" in rapt
    assert 'state.state == "off"' in rapt
    assert '"stop_guard_active": True' in rapt
    owns = isolation.split("def rapt_owns_brewing", 1)[1].split("def _rapt_runtime_snapshot", 1)[0]
    assert 'store.get("stop_guard_active")' not in owns


def test_cards_describe_rcl_assist_not_ba_target_ownership():
    for path in (RAPT_CARD, RAPT_CARD_SV):
        card = path.read_text(encoding="utf-8")
        assert "RAPT PROFILE" in card and "BREWASSISTANT" in card and "RCL" in card
        assert "runtime target" in card or "runtime-target" in card
        assert "controls target/heat/pump" not in card
        assert "styr target/heat/pump" not in card
