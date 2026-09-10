"""Regression checks for RAPT BrewZilla profile-runtime ownership."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAPT_RUNTIME = ROOT / "custom_components/brewassistant/brewday/rapt_profile_runtime.py"
RUNTIME = ROOT / "custom_components/brewassistant/brewday/brewday_runtime.py"
MANUAL_STORE = ROOT / "custom_components/brewassistant/brewday/manual_brewday_store.py"
ORCHESTRATION = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_orchestration.py"


def test_rapt_profile_python_sources_parse() -> None:
    for path in (RAPT_RUNTIME, RUNTIME, MANUAL_STORE):
        ast.parse(path.read_text(encoding="utf-8"))


def test_rapt_profile_wins_source_arbitration_before_brewfather() -> None:
    source = RUNTIME.read_text(encoding="utf-8")
    arbitration = source.split("def build_brewday_runtime_snapshot", 1)[1]
    assert "build_rapt_profile_runtime_snapshot(hass)" in arbitration
    assert 'runtime_source = core_source(hass)' in arbitration
    assert arbitration.index("build_rapt_profile_runtime_snapshot(hass)") < arbitration.index(
        "runtime_source = core_source(hass)"
    )
    assert "_pause_manual_brewday_for_rapt(hass)" in arbitration


def test_local_profile_runner_is_not_direct_ba_control_state() -> None:
    runtime = RAPT_RUNTIME.read_text(encoding="utf-8")
    orchestration = ORCHESTRATION.read_text(encoding="utf-8")
    assert 'RAPT_PROFILE_RUNTIME_STATE = "external_executor"' in runtime
    active_set = orchestration.split("_ACTIVE_RUNTIME_STATES = {", 1)[1].split("}", 1)[0]
    assert '"external_executor"' not in active_set
    assert '"direct_brewzilla_control_allowed": False' in runtime
    assert '"process_executor": "brewzilla_local_profile_runner"' in runtime


def test_source_loss_does_not_silently_fall_back() -> None:
    source = RAPT_RUNTIME.read_text(encoding="utf-8")
    assert 'if store.get("was_active"):' in source
    assert "return _unavailable_snapshot(hass, store)" in source
    assert '"runtime_state": "source_unavailable"' in source
    assert '"control_owner": "unknown_preserve_rapt_handoff"' in source


def test_confirmed_stop_requires_fresh_rcl_off_after_observed_active() -> None:
    source = RAPT_RUNTIME.read_text(encoding="utf-8")
    assert "def _fresh_stopped_contract" in source
    assert 'state.state == "off"' in source
    assert "and not _is_restored(state)" in source
    assert '_fresh_stopped_contract(state) and store.get("was_active")' in source
    assert '"stop_guard_active": True' in source


def test_confirmed_profile_stop_forces_full_safe_off() -> None:
    source = RAPT_RUNTIME.read_text(encoding="utf-8")
    for token in (
        'BREWZILLA_HEATER_SWITCH = "switch.brewzilla_heater"',
        'BREWZILLA_PUMP_SWITCH = "switch.brewzilla_pump"',
        'BREWZILLA_HEAT_UTILIZATION',
        'BREWZILLA_PUMP_UTILIZATION',
        '("switch", "turn_off", BREWZILLA_HEATER_SWITCH, None)',
        '("switch", "turn_off", BREWZILLA_PUMP_SWITCH, None)',
        '("number", "set_value", BREWZILLA_HEAT_UTILIZATION, {"value": 0})',
        '("number", "set_value", BREWZILLA_PUMP_UTILIZATION, {"value": 0})',
        'clear_owned_control(hass, reason="rapt_profile_stop_confirmed")',
    ):
        assert token in source


def test_manual_positive_control_respects_rapt_handoff() -> None:
    source = MANUAL_STORE.read_text(encoding="utf-8")
    assert "rapt_profile_runtime_claims_source" in source
    assert "clear_rapt_profile_stop_guard" in source
    assert "allow_stopped_takeover=True" in source
    assert "raise _rapt_ownership_error()" in source
    assert 'reason="manual_operator_takeover"' in source
