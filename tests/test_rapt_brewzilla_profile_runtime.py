"""Regression checks for RAPT BrewZilla profile-runtime ownership."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAPT_RUNTIME = ROOT / "custom_components/brewassistant/brewday/rapt_profile_runtime.py"
RUNTIME = ROOT / "custom_components/brewassistant/brewday/brewday_runtime.py"
MANUAL_STORE = ROOT / "custom_components/brewassistant/brewday/manual_brewday_store.py"
RAPT_CONTROL_BRIDGE = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_rapt_profile_control_bridge.py"
FAIL_PASSIVE = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_fail_passive_guard.py"
BREWZILLA_INIT = ROOT / "custom_components/brewassistant/brewzilla/__init__.py"
RAPT_CARD = ROOT / "dashboard/cards/rapt_profile_runtime.yaml"
RAPT_CARD_SV = ROOT / "dashboard/cards/rapt_profile_runtime_sv.yaml"
BREWDAY_CARD = ROOT / "dashboard/cards/brewassistant_brewday.yaml"
BREWDAY_CARD_SV = ROOT / "dashboard/cards/brewassistant_brewday_sv.yaml"


def test_rapt_profile_python_sources_parse() -> None:
    for path in (
        RAPT_RUNTIME,
        RUNTIME,
        MANUAL_STORE,
        RAPT_CONTROL_BRIDGE,
        FAIL_PASSIVE,
        BREWZILLA_INIT,
    ):
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


def test_active_rapt_profile_feeds_existing_ba_controller() -> None:
    bridge = RAPT_CONTROL_BRIDGE.read_text(encoding="utf-8")
    init = BREWZILLA_INIT.read_text(encoding="utf-8")

    assert '"runtime_state": "running"' in bridge
    assert '"process_source": "rapt_cloud_link"' in bridge
    assert '"directive_source": "rapt_profile"' in bridge
    assert '"control_owner": "brewassistant"' in bridge
    assert '"brewassistant_role": "hot_side_controller"' in bridge
    assert '"direct_brewzilla_control_allowed": not cooling_marker' in bridge
    assert '"rapt_profile_role": "process_and_target_source"' in bridge
    assert '"heat_pump_owner": "brewassistant" if not cooling_marker else "cooling_handoff"' in bridge
    assert "rapt_runtime._active_snapshot = _active_snapshot" in bridge
    assert "install_rapt_profile_control_bridge()" in init


def test_rapt_heatstrike_and_profile_steps_map_to_existing_ba_stage_kinds() -> None:
    bridge = RAPT_CONTROL_BRIDGE.read_text(encoding="utf-8")
    assert '"heatstrike", "heat strike", "strike water"' in bridge
    assert 'return "Mash", "Heat Strike"' in bridge
    assert 'end_type == "temperature"' in bridge
    assert 'f"Ramp · {raw_name}"' in bridge
    assert 'end_type == "duration"' in bridge
    assert 'f"Mash Hold · {raw_name}"' in bridge
    assert 'target >= 95.0' in bridge
    assert 'return "Boil"' in bridge


def test_rapt_mash_out_single_step_switches_from_ramp_to_hold_at_target() -> None:
    bridge = RAPT_CONTROL_BRIDGE.read_text(encoding="utf-8")
    assert '_TARGET_REACHED_TOLERANCE_C = 0.3' in bridge
    assert 'current < target - _TARGET_REACHED_TOLERANCE_C' in bridge
    assert 'return "Mash", f"Ramp · {raw_name}"' in bridge
    assert 'return "Mash", f"Mash Hold · {raw_name}"' in bridge


def test_manual_rapt_mash_in_holds_previous_strike_target_until_operator_starts() -> None:
    bridge = RAPT_CONTROL_BRIDGE.read_text(encoding="utf-8")
    assert "def _previous_profile_target" in bridge
    assert "def _manual_mash_in" in bridge
    assert 'gate_state not in _MASH_IN_STARTED_STATES' in bridge
    assert 'out["target_temperature"] = strike_hold_target' in bridge
    assert '"rapt_previous_heatstrike_until_mash_in_started"' in bridge
    assert '"rapt_mash_in_strike_hold_active": strike_hold_active' in bridge
    assert '"rapt_directive_target_temperature": raw_target' in bridge
    assert '"rapt_effective_ba_target_temperature": _num(out.get("target_temperature"))' in bridge


def test_rapt_cooling_marker_never_becomes_hot_side_target() -> None:
    bridge = RAPT_CONTROL_BRIDGE.read_text(encoding="utf-8")
    fail_passive = FAIL_PASSIVE.read_text(encoding="utf-8")

    assert 'out["target_temperature"] = None' in bridge
    assert '"rapt_cooling_marker_ignored"' in bridge
    assert '"requested_target": None' in bridge
    assert '"target_sync_needed": False' in bridge
    assert '"desired_heat_utilization": 0.0' in bridge
    assert '"desired_heater_on": False' in bridge
    assert '"desired_pump_on": None' in bridge
    assert '"pump_stop_needed": False' in bridge
    assert '"rapt_cooling_handoff_active": True' in bridge
    assert '"brewzilla_pump_owner": "cooling_runtime_or_operator"' in bridge
    assert 'snapshot.get("rapt_cooling_handoff_active")' in fail_passive


def test_rapt_uses_same_supervised_policy_and_phase_authority_as_bt() -> None:
    bridge = RAPT_CONTROL_BRIDGE.read_text(encoding="utf-8")
    assert "supervised._request_source = _request_source" in bridge
    assert "return supervised.SOURCE_BREW_TRACKER" in bridge
    assert "phase_authority._phase_authority_active = _phase_authority_active" in bridge
    assert "phase_authority._brewtracker_pre_mash_in = _rapt_pre_mash_in" in bridge
    assert 'out["phase_authority_source"] = "rapt_profile_active"' in bridge


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


def test_rapt_runtime_cards_make_directive_and_control_ownership_explicit() -> None:
    for path in (RAPT_CARD, RAPT_CARD_SV):
        source = path.read_text(encoding="utf-8")
        assert "RAPT BrewZilla Profile" in source
        assert "RAPT PROFILE" in source
        assert "BREWASSISTANT" in source
        assert "RCL" in source
        assert "BREWZILLA" in source
        assert "step_target_temperature" in source
        assert "next_step_target_temperature" in source
        assert "step_end_type" in source
        assert "step_duration_type" in source


def test_brewday_cards_show_dynamic_source_chain() -> None:
    for path in (BREWDAY_CARD, BREWDAY_CARD_SV):
        source = path.read_text(encoding="utf-8")
        assert "sensor.brewassistant_brewday_runtime_source" in source
        assert "RAPT BrewZilla Profile" in source
        assert "Brewfather Brew Tracker" in source
        assert "Manual Brewday" in source
        assert "RAPT PROFILE" in source
        assert "BREWTRACKER" in source
        assert "BREWASSISTANT" in source
        assert "RCL" in source
        assert "BREWZILLA" in source


def test_brewday_cards_distinguish_observed_rapt_from_control_ownership_during_abort() -> None:
    en = BREWDAY_CARD.read_text(encoding="utf-8")
    sv = BREWDAY_CARD_SV.read_text(encoding="utf-8")
    for source in (en, sv):
        assert "binary_sensor.brewzilla_profile_active" in source
        assert "rapt_cloud_link_brewzilla_profile_runtime" in source
        assert "lockedRapt = state === 'aborted'" in source
        assert "sourceIsRapt" in source
    assert "RAPT PROFILE · OBSERVED" in en
    assert "BREWASSISTANT LOCKED" in en
    assert "RAPT PROFILE · OBSERVERAD" in sv
    assert "BREWASSISTANT LÅST" in sv
