"""Regression checks for Heatstrike ownership while Mash-In is merely ready."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BREWZILLA_INIT = ROOT / "custom_components/brewassistant/brewzilla/__init__.py"
READY_HOLD = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_mash_in_ready_hold_guard.py"
MASH_IN_GATE = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_mash_in_gate.py"
PHASE_AUTHORITY = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_phase_authority.py"


def test_ready_hold_is_installed_after_mash_in_gate_before_later_safety_chain() -> None:
    source = BREWZILLA_INIT.read_text(encoding="utf-8")
    mash_gate_pos = source.index("_mash_in_gate.install_mash_in_gate()")
    ready_hold_pos = source.index("_mash_in_ready_hold_guard.install_mash_in_ready_hold_guard()")
    freshness_pos = source.index("_freshness_guard.install_freshness_guard()")
    assert mash_gate_pos < ready_hold_pos < freshness_pos


def test_ready_state_keeps_clean_heatstrike_target_heat_and_pump_authority() -> None:
    source = READY_HOLD.read_text(encoding="utf-8")
    assert 'snapshot.get("mash_in_gate_state")' in source
    assert "mash_in_gate.READY_STATE" in source
    assert 'snapshot.get("clean_heat_strike_active")' in source
    assert "clean_heatstrike._apply_clean_heatstrike(snapshot)" in source
    assert '"mash_in_ready_heatstrike_hold_active": True' in source
    assert '"mash_in_ready_heatstrike_release_event": "mash_in_started"' in source
    assert '"mash_in_started_visible": True' in source
    assert '"mash_in_complete_visible": False' in source


def test_ready_hold_does_not_write_hardware_directly_or_bypass_safety() -> None:
    source = READY_HOLD.read_text(encoding="utf-8")
    assert "number.set_value" not in source
    assert "switch.turn_on" not in source
    assert "switch.turn_off" not in source
    assert 'not snapshot.get("abort_lockout_active")' in source
    assert 'not snapshot.get("completed_runtime")' in source


def test_operator_notification_says_heatstrike_keeps_holding_until_started() -> None:
    source = READY_HOLD.read_text(encoding="utf-8")
    assert "Heatstrike fortsätter hålla temperaturen och cirkulationen" in source
    assert "Mash-In Started" in source
    assert "Då pausas pumpen och Mash-In-logiken tar över" in source


def test_mash_in_started_remains_the_physical_transition_boundary() -> None:
    gate_source = MASH_IN_GATE.read_text(encoding="utf-8")
    authority_source = PHASE_AUTHORITY.read_text(encoding="utf-8")

    # The existing started state releases strike target, pauses the pump and
    # applies the effective mash target/anti-drop heat until Mash-In Complete.
    assert '"state": STARTED_STATE' in gate_source
    assert '"requested_target_source": "mash_in_started_effective_target"' in gate_source
    assert '"desired_pump_on": False' in gate_source
    assert '"desired_pump_utilization": PUMP_OFF_UTILIZATION' in gate_source
    assert "Strike target released" in gate_source

    # Play-granted phase authority remains valid across READY/STARTED without a
    # generic confirmation; Mash-In Complete ends that authority.
    assert '_PRE_MASH_IN_GATE_STATES = {"idle", "ready_for_mash_in", "mash_in_started"}' in authority_source
    assert 'gate_state in {"ready_for_mash_in", "mash_in_started"}' in authority_source
    assert 'str(gate.get("state") or "").lower() == "mash_in_complete"' in authority_source
