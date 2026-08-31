"""Regression checks for explicit BrewZilla heat safe-down precedence."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCAL_HEAT_GUARD = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_local_regulation_heat_guard.py"
CLEAN_HEATSTRIKE = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_clean_heat_strike_guard.py"


def test_clean_heatstrike_zero_bypasses_local_heat_preserve() -> None:
    source = LOCAL_HEAT_GUARD.read_text(encoding="utf-8")
    assert 'snapshot.get("clean_heat_strike_active")' in source
    assert 'return "clean_heatstrike_explicit_zero"' in source
    assert '"brewzilla_local_heat_preserve_bypassed": True' in source
    assert "explicit safe-down wins" in source


def test_process_above_active_target_bypasses_local_heat_preserve() -> None:
    source = LOCAL_HEAT_GUARD.read_text(encoding="utf-8")
    assert '_PROCESS_ABOVE_TARGET_MARGIN_C = 0.3' in source
    assert 'process_temperature > requested_target + _PROCESS_ABOVE_TARGET_MARGIN_C' in source
    assert 'return "process_above_active_target"' in source


def test_mash_in_started_explicit_zero_bypasses_local_heat_preserve() -> None:
    source = LOCAL_HEAT_GUARD.read_text(encoding="utf-8")
    assert 'snapshot.get("mash_in_started_hold_active")' in source
    assert 'return "mash_in_started_explicit_zero"' in source


def test_clean_heatstrike_zero_is_reserved_for_real_overshoot() -> None:
    source = CLEAN_HEATSTRIKE.read_text(encoding="utf-8")
    assert '_READY_TOLERANCE_C = 0.3' in source
    assert '_SAFETY_OVERSHOOT_STOP_C = 0.5' in source
    assert '(_READY_TOLERANCE_C, 25.0, True, "clean_gate_ready_local_hold")' in source
    assert '(-_SAFETY_OVERSHOOT_STOP_C, 0.0, False, "clean_safety_overshoot_stop")' in source
    assert '(_READY_TOLERANCE_C, 25.0, True, "clean_safety_local_regulation_hold")' in source
    assert '"heater_stop_needed": heater_stop_needed' in source


def test_clean_heatstrike_keeps_positive_authority_through_final_approach() -> None:
    source = CLEAN_HEATSTRIKE.read_text(encoding="utf-8")
    # The local BrewZilla thermostat remains enabled near target. BA limits the
    # maximum utilization, while the device itself decides whether to energize
    # the element against the written target.
    assert '(_READY_TOLERANCE_C, 25.0, True, "clean_gate_ready_local_hold")' in source
    assert '(3.0, 25.0, True, "clean_gate_final_approach")' in source
    assert '(_READY_TOLERANCE_C, 25.0, True, "clean_safety_local_regulation_hold")' in source
    assert '(3.0, 50.0, True, "clean_safety_final_approach_cap")' in source
    assert 'clean_gate_ready_coast' not in source
    assert 'clean_safety_ready_coast' not in source
