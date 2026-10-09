"""Contract checks for Brewday three-mode execution."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODE = ROOT / "custom_components/brewassistant/brewday/brewday_execution_mode.py"
RECIPE_FALLBACK = ROOT / "custom_components/brewassistant/brewday/brewday_recipe_fallback.py"
RUNTIME = ROOT / "custom_components/brewassistant/brewday/brewday_runtime.py"
MANUAL_STORE = ROOT / "custom_components/brewassistant/brewday/manual_brewday_store.py"
SENSOR = ROOT / "custom_components/brewassistant/brewday/brewday_runtime_sensor.py"
ABORT = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_emergency_abort.py"


def test_contract_files_parse():
    for path in (MODE, RECIPE_FALLBACK, RUNTIME, MANUAL_STORE, SENSOR, ABORT):
        ast.parse(path.read_text(encoding="utf-8"))


def test_exact_three_normal_mode_labels():
    source = MODE.read_text(encoding="utf-8")
    assert 'MANUAL_BREWING = "Manual Brewing"' in source
    assert 'BREWFATHER_BREWING = "Brewfather Brewing"' in source
    assert 'RCL_BREWING = "RCL Brewing"' in source
    assert "BREWDAY_MODES = (MANUAL_BREWING, BREWFATHER_BREWING, RCL_BREWING)" in source


def test_recipe_identity_is_retained_across_manual_fallback():
    source = MODE.read_text(encoding="utf-8")
    recipe = RECIPE_FALLBACK.read_text(encoding="utf-8")
    for token in (
        "external_snapshots", "deepcopy(snapshot)", "build_manual_fallback_snapshot",
        '"recipe_context_retained": recipe_context_retained',
        '"fallback_external_timeline_frozen": True',
        '"manual_plan_operator_progression_until_source_recovers"',
        '"runtime_state": "running"',
        '"manual_fallback_recipe_active": True',
        '"manual_fallback_plan_loaded": manual_plan_loaded',
        "_prime_manual_fallback_plan",
    ):
        assert token in source
    for token in (
        "plan_from_external_snapshot",
        "active_position_from_snapshot",
        "ManualPlan",
        "ManualStage",
        "ManualStep",
        "auto_advance=False",
    ):
        assert token in recipe



def test_rcl_manual_fallback_can_progress_but_live_rapt_reclaims_guard():
    source = MANUAL_STORE.read_text(encoding="utf-8")
    for token in (
        "execution_mode.fallback_active(hass)",
        "execution_mode.last_external_mode(hass) == execution_mode.RCL_BREWING",
        "not rapt_profile_runtime_active(hass)",
        "A live RAPT profile always wins immediately",
    ):
        assert token in source

def test_runtime_exposes_mode_and_reconnect_contract():
    runtime = RUNTIME.read_text(encoding="utf-8")
    sensor = SENSOR.read_text(encoding="utf-8")
    assert '"brewday_mode": {"field": "brewday_mode"}' in sensor
    assert "remember_external_snapshot" in runtime
    assert "build_manual_fallback_snapshot" in runtime
    assert "if rapt_live:" in runtime
    assert 'runtime_source == "Brewfather Brew Tracker"' in runtime


def test_abort_is_global_and_not_a_fourth_mode():
    mode = MODE.read_text(encoding="utf-8")
    abort = ABORT.read_text(encoding="utf-8")
    mode_line = mode.split("BREWDAY_MODES =", 1)[1].splitlines()[0]
    assert "ABORT" not in mode_line
    for token in (
        '"heater_off"', '"pump_off"', '"heat_utilization_zero"',
        '"pump_utilization_zero"', '"main_power_off"',
    ):
        assert token in abort
