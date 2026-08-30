"""Regression checks for BrewTracker Heatstrike physical phase authority."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BREWZILLA_INIT = ROOT / "custom_components/brewassistant/brewzilla/__init__.py"
PHASE_AUTHORITY = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_phase_authority.py"
SUPERVISED = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_supervised_runtime_guard.py"
LEARNING = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_learning.py"


def test_phase_authority_is_installed_after_generic_supervised_wrappers() -> None:
    source = BREWZILLA_INIT.read_text(encoding="utf-8")
    supervised_pos = source.index("_supervised_runtime_guard.install_supervised_runtime_guard()")
    readback_pos = source.index("_supervised_readback_grace.install_supervised_readback_grace()")
    authority_pos = source.index("_phase_authority.install_phase_authority()")
    assert authority_pos > supervised_pos
    assert authority_pos > readback_pos


def test_play_authorized_heatstrike_bypasses_per_write_confirmation_only() -> None:
    source = PHASE_AUTHORITY.read_text(encoding="utf-8")
    assert '"phase_authority_source": "brewfather_play"' in source
    assert '"phase_authority_requires_generic_confirmation": False' in source
    assert 'snapshot.get("clean_heat_strike_active")' in source
    assert "supervised._BASE_APPLY(hass)" in source
    assert "clear_pending_action_from_source(hass, supervised.SOURCE)" in source
    assert "clear_cancelled_action_from_source(hass, supervised.SOURCE)" in source

    # The lower apply chain is intentionally retained; this patch must not call
    # raw number/switch services itself and must not replace ABORT/safety guards.
    assert "number.set_value" not in source
    assert "switch.turn_on" not in source
    assert "switch.turn_off" not in source


def test_phase_authority_ends_at_mash_in_complete() -> None:
    source = PHASE_AUTHORITY.read_text(encoding="utf-8")
    assert 'str(gate.get("state") or "").lower() == "mash_in_complete"' in source
    assert "gate.get(\"completed_once\")" in source
    assert "not _gate_complete(hass)" in source


def test_heatstrike_internal_modulation_remains_present_in_clean_controller() -> None:
    source = (ROOT / "custom_components/brewassistant/brewzilla/brewzilla_clean_heat_strike_guard.py").read_text(
        encoding="utf-8"
    )
    for value in ("100.0", "75.0", "50.0", "25.0", "10.0", "0.0"):
        assert value in source
    assert "_PUMP_FAR = 70.0" in source
    assert "_PUMP_NEAR = 90.0" in source
    assert "_PUMP_READY = 100.0" in source


def test_learning_is_observe_only_while_physical_controller_owns_io() -> None:
    source = PHASE_AUTHORITY.read_text(encoding="utf-8")
    assert '"mode": "observe_only_controller_owned"' in source
    assert '"status": "observing_controller_owned"' in source
    assert '"controller_owned": True' in source
    assert '"pending_recommendation": None' in source
    assert '"recommendation_action_label": None' in source
    assert '"auto_apply_allowed": False' in source
    assert 'store["pending"] = None' in source


def test_generic_supervised_guard_still_exists_for_post_mash_in_authority() -> None:
    source = SUPERVISED.read_text(encoding="utf-8")
    assert '"key": "target_up"' in source
    assert '"key": "heat_up"' in source
    assert '"key": "pump_up"' in source
    assert '"apply_result": "pending_confirmation"' in source
    assert "live_plan_id != expected_plan_id" in source


def test_learning_apply_remains_explicit_outside_controller_owned_phase() -> None:
    source = LEARNING.read_text(encoding="utf-8")
    assert "async def async_apply_brewzilla_learning_recommendation" in source
    assert '"number",' in source
    assert '"set_value",' in source
