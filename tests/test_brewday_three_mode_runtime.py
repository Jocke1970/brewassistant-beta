"""Contract checks for Brewday three-mode execution."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODE = ROOT / "custom_components/brewassistant/brewday/brewday_execution_mode.py"
RUNTIME = ROOT / "custom_components/brewassistant/brewday/brewday_runtime.py"
SENSOR = ROOT / "custom_components/brewassistant/brewday/brewday_runtime_sensor.py"
ABORT = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_emergency_abort.py"


def test_contract_files_parse():
    for path in (MODE, RUNTIME, SENSOR, ABORT):
        ast.parse(path.read_text(encoding="utf-8"))


def test_exact_three_normal_mode_labels():
    source = MODE.read_text(encoding="utf-8")
    assert 'MANUAL_BREWING = "Manual Brewing"' in source
    assert 'BREWFATHER_BREWING = "Brewfather Brewing"' in source
    assert 'RCL_BREWING = "RCL Brewing"' in source
    assert "BREWDAY_MODES = (MANUAL_BREWING, BREWFATHER_BREWING, RCL_BREWING)" in source


def test_recipe_identity_is_retained_across_manual_fallback():
    source = MODE.read_text(encoding="utf-8")
    for token in (
        "external_snapshots", "deepcopy(snapshot)", "build_manual_fallback_snapshot",
        '"recipe_context_retained": recipe_context_retained',
        '"fallback_timeline_frozen": True',
        '"fallback_progression_policy": "freeze_external_timeline_until_source_recovers"',
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
