"""Regression checks for the consolidated strike-ready -> Mash-In boundary."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_clean_heat_strike_guard.py"
CONTRACT = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_hot_side_contract.py"
FAIL_PASSIVE = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_fail_passive_guard.py"
INIT = ROOT / "custom_components/brewassistant/brewzilla/__init__.py"
PHASE_AUTHORITY = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_phase_authority.py"


def test_strike_ready_band_keeps_local_regulation_enabled_until_mash_in() -> None:
    source = CLEAN.read_text(encoding="utf-8")
    assert '_READY_TOLERANCE_C = 0.3' in source
    assert '_SAFETY_OVERSHOOT_STOP_C = 0.5' in source
    assert '(_READY_TOLERANCE_C, 25.0, True, "clean_gate_ready_local_hold")' in source
    assert '(3.0, 25.0, True, "clean_gate_final_approach")' in source
    assert '(-_SAFETY_OVERSHOOT_STOP_C, 0.0, False, "clean_safety_overshoot_stop")' in source
    assert '(_READY_TOLERANCE_C, 25.0, True, "clean_safety_local_regulation_hold")' in source
    assert '(3.0, 50.0, True, "clean_safety_final_approach_cap")' in source
    assert 'clean_safety_ready_coast' not in source


def test_final_approach_profile_has_no_zero_heat_dead_zone_below_overshoot() -> None:
    source = CLEAN.read_text(encoding="utf-8")
    gate = source.split("_GATE_HEAT_PROFILE", 1)[1].split("_GATE_FAR_HEAT", 1)[0]
    safety = source.split("_SAFETY_HEAT_CAPS", 1)[1].split("_SAFETY_FAR_CAP", 1)[0]

    # The 2026-08-31 water test deadlocked at MASH 69.6 / WORT 71.5 / target
    # 71.8: process delta 2.2 C, safety delta 0.3 C. Both profiles must now
    # preserve positive local-regulation authority for that state.
    assert '(3.0, 25.0, True, "clean_gate_final_approach")' in gate
    assert '(_READY_TOLERANCE_C, 25.0, True, "clean_safety_local_regulation_hold")' in safety
    assert '(-_SAFETY_OVERSHOOT_STOP_C, 0.0, False, "clean_safety_overshoot_stop")' in safety


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
    assert "Heatstrike target/heat/pump" in ready_body
    assert "remain authoritative until Mash-In Started" in ready_body


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


def test_old_stale_safe_layers_are_not_installed() -> None:
    source = INIT.read_text(encoding="utf-8")
    assert "install_freshness_guard()" not in source
    assert "install_stale_safe_guard()" not in source
    assert "_fail_passive_guard.install_fail_passive_guard()" in source
    assert source.rfind("_fail_passive_guard.install_fail_passive_guard()") > source.rfind(
        "_phase_authority.install_phase_authority()"
    )


def test_fail_passive_never_turns_outputs_off_for_ordinary_data_loss() -> None:
    source = FAIL_PASSIVE.read_text(encoding="utf-8")
    hold = source.split("def _hold_last_observed", 1)[1].split("def _augment_snapshot", 1)[0]
    apply_body = source.split("async def async_apply_brewzilla_target_if_allowed", 1)[1].split(
        "def _resolve_auto_without_internal_takeover", 1
    )[0]

    assert '"fail_passive_mode": "brewzilla_local_regulation"' in hold
    assert '"fail_passive_no_new_writes": True' in hold
    assert '"heater_stop_needed": False' in hold
    assert '"pump_stop_needed": False' in hold
    assert '"can_apply_target": False' in hold
    assert '"actions": []' in apply_body
    assert "_enforce_brewzilla_safe_state" not in source


def test_owned_external_probe_is_not_replaced_by_internal_on_dropout() -> None:
    source = FAIL_PASSIVE.read_text(encoding="utf-8")
    resolver = source.split("def _resolve_auto_without_internal_takeover", 1)[1].split(
        "def install_fail_passive_guard", 1
    )[0]
    assert "if lock_active and degraded_reason" in resolver
    assert "return None, True, degraded_reason" in resolver


def test_play_granted_authority_survives_ready_and_started_until_complete() -> None:
    source = PHASE_AUTHORITY.read_text(encoding="utf-8")
    assert '_PRE_MASH_IN_GATE_STATES = {"idle", "ready_for_mash_in", "mash_in_started"}' in source
    assert 'gate_state in {"ready_for_mash_in", "mash_in_started"}' in source
    assert 'str(gate.get("state") or "").lower() == "mash_in_complete"' in source
    assert '"phase_authority_requires_generic_confirmation": False' in source
