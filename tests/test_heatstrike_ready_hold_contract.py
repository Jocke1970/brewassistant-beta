"""Regression checks for the consolidated strike-ready -> Mash-In boundary."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_clean_heat_strike_guard.py"
CONTRACT = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_hot_side_contract.py"
INIT = ROOT / "custom_components/brewassistant/brewzilla/__init__.py"
PHASE_AUTHORITY = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_phase_authority.py"


def test_strike_ready_band_can_reheat_if_temperature_drifts_low() -> None:
    source = CLEAN.read_text(encoding="utf-8")
    assert '_READY_TOLERANCE_C = 0.3' in source
    assert '(_READY_TOLERANCE_C, 0.0, False, "clean_gate_ready_coast")' in source
    assert '(3.0, 10.0, True, "clean_gate_final_low_hold")' in source
    assert '(_READY_TOLERANCE_C, 0.0, False, "clean_safety_ready_coast")' in source
    assert '(1.0, 10.0, True, "clean_safety_final_low_hold")' in source


def test_ready_is_a_pure_operator_gate() -> None:
    source = CONTRACT.read_text(encoding="utf-8")
    ready_body = source.split("def _ready_is_pure_gate", 1)[1].split(
        "def _augment_with_process_roles", 1
    )[0]

    assert "**snapshot" in ready_body
    assert '"mash_in_ready_preserves_heatstrike_authority": True' in ready_body
    assert '"requested_target"' not in ready_body
    assert '"desired_heat_utilization"' not in ready_body
    assert '"desired_pump_utilization"' not in ready_body
    assert "Heatstrike target/heat/pump remain authoritative" in ready_body


def test_mash_in_started_is_atomic_release_boundary() -> None:
    source = CONTRACT.read_text(encoding="utf-8")
    started = source.split("async def async_mark_mash_in_started", 1)[1].split(
        "async def async_confirm_mash_in_complete", 1
    )[0]

    assert 'state != _READY_STATE' in started
    assert '"mash_in_started_set_pump_utilization"' in started
    assert '"mash_in_started_pump_off"' in started
    assert '"mash_in_started_set_target"' in started
    assert '"requested_target_source": "mash_in_started_effective_target"' in started
    assert '"desired_pump_on": False' in started
    assert '"desired_pump_utilization": gate.PUMP_OFF_UTILIZATION' in started


def test_complete_is_only_valid_after_started() -> None:
    source = CONTRACT.read_text(encoding="utf-8")
    complete = source.split("async def async_confirm_mash_in_complete", 1)[1].split(
        "def install_hot_side_contract", 1
    )[0]
    assert 'state != _STARTED_STATE' in complete
    assert 'mash_in_complete_blocked_from:' in complete


def test_legacy_overlapping_layers_are_not_installed() -> None:
    source = INIT.read_text(encoding="utf-8")

    assert "_hot_side_contract.install_hot_side_contract()" in source
    assert "install_strike_ready_hold_guard()" not in source
    assert "install_heat_strike_pump_mix_guard()" not in source
    assert "install_heat_strike_near_target_safety_guard()" not in source
    assert "install_mash_in_target_patch()" not in source
    assert "install_mash_in_started_guard()" not in source
    assert "install_mash_in_state_guard()" not in source


def test_play_granted_authority_survives_ready_and_started_until_complete() -> None:
    source = PHASE_AUTHORITY.read_text(encoding="utf-8")
    assert '_PRE_MASH_IN_GATE_STATES = {"idle", "ready_for_mash_in", "mash_in_started"}' in source
    assert 'gate_state in {"ready_for_mash_in", "mash_in_started"}' in source
    assert 'str(gate.get("state") or "").lower() == "mash_in_complete"' in source
    assert '"phase_authority_requires_generic_confirmation": False' in source
