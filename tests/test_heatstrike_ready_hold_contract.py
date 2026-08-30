"""Regression checks for the strike-ready -> Mash-In Started boundary."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_clean_heat_strike_guard.py"
TARGET_PATCH = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_mash_in_target_patch.py"
MASH_IN_GATE = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_mash_in_gate.py"
PHASE_AUTHORITY = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_phase_authority.py"


def test_strike_ready_band_can_reheat_if_temperature_drifts_low() -> None:
    source = CLEAN.read_text(encoding="utf-8")
    assert '_READY_TOLERANCE_C = 0.3' in source
    assert '(_READY_TOLERANCE_C, 0.0, False, "clean_gate_ready_coast")' in source
    assert '(3.0, 10.0, True, "clean_gate_final_low_hold")' in source
    assert '(_READY_TOLERANCE_C, 0.0, False, "clean_safety_ready_coast")' in source
    assert '(1.0, 10.0, True, "clean_safety_final_low_hold")' in source


def test_ready_gate_keeps_existing_heatstrike_target_and_heat_logic() -> None:
    source = TARGET_PATCH.read_text(encoding="utf-8")
    ready_body = source.split("def _force_pump_run_until_mash_in_started", 1)[1].split(
        "def _mash_in_started_hold_snapshot", 1
    )[0]

    # READY may adjust circulation, but it must not replace the strike target or
    # Heatstrike heat request. Those values are inherited from the physical
    # controller until the operator explicitly presses Mash-In Started.
    assert "**snapshot" in ready_body
    assert '"desired_pump_on": True' in ready_body
    assert '"desired_pump_utilization": READY_PUMP_UTILIZATION' in ready_body
    assert '"requested_target"' not in ready_body
    assert '"desired_heat_utilization"' not in ready_body
    assert "until Mash-In Started is pressed" in ready_body


def test_ready_notification_describes_maintained_strike_hold() -> None:
    source = TARGET_PATCH.read_text(encoding="utf-8")
    assert "fortsätter hålla strike-temperaturen" in source
    assert "cirkulationen tills du bekräftar" in source
    assert "Då pausas pumpen och strike-target släpps" in source
    assert "gate._create_ready_notification = _create_ready_notification" in source


def test_mash_in_started_is_the_explicit_release_boundary() -> None:
    gate_source = MASH_IN_GATE.read_text(encoding="utf-8")
    started_body = gate_source.split("def _mash_in_started_hold_snapshot", 1)[1].split(
        "def _idle_snapshot", 1
    )[0]

    assert '"requested_target_source": "mash_in_started_effective_target"' in started_body
    assert '"desired_pump_on": False' in started_body
    assert '"desired_pump_utilization": PUMP_OFF_UTILIZATION' in started_body
    assert "Strike target released" in started_body
    assert '"state": STARTED_STATE' in gate_source


def test_play_granted_authority_survives_ready_and_started_until_complete() -> None:
    source = PHASE_AUTHORITY.read_text(encoding="utf-8")
    assert '_PRE_MASH_IN_GATE_STATES = {"idle", "ready_for_mash_in", "mash_in_started"}' in source
    assert 'gate_state in {"ready_for_mash_in", "mash_in_started"}' in source
    assert 'str(gate.get("state") or "").lower() == "mash_in_complete"' in source
    assert '"phase_authority_requires_generic_confirmation": False' in source
