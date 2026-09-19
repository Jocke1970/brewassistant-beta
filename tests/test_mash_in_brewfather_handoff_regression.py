"""Regression contracts for the Mash-In -> Brewfather Continue handoff."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_mash_in_complete_safe_down_guard.py"
RUNTIME_FLOW_CARDS = (
    ROOT / "dashboard/cards/brewassistant_brewday_runtime_flow.yaml",
    ROOT / "dashboard/cards/brewassistant_brewday_runtime_flow_sv.yaml",
)


def test_brewfather_resume_requires_pause_observed_after_mash_in_started() -> None:
    source = BRIDGE.read_text(encoding="utf-8")
    transition_body = source.split("def _brewfather_transition", 1)[1].split(
        "def _runtime_allows_operator_safe_down", 1
    )[0]
    auto_body = source.split("def _auto_complete_allowed", 1)[1].split(
        "async def _apply_brewfather_resume_auto_complete", 1
    )[0]

    assert "sensor.brewfather_brew_tracker_status" in source
    assert "seen_paused_after_mash_in_started" in transition_body
    assert "current in _PAUSED_STATES" in transition_body

    assert "waiting_for_brewfather_pause_after_mash_in_started" in auto_body
    assert "paused_to_running_after_mash_in_started" in auto_body
    assert "running_after_observed_mash_in_pause" in auto_body
    assert "running_after_mash_in_target_advanced" not in auto_body
    assert "_gate_origin_target" not in source


def test_running_brewfather_that_predates_mash_in_started_cannot_complete() -> None:
    source = BRIDGE.read_text(encoding="utf-8")
    body = source.split("def _auto_complete_allowed", 1)[1].split(
        "async def _apply_brewfather_resume_auto_complete", 1
    )[0]

    assert "if not seen_paused_after_mash_in_started" in body
    assert "return False, \"waiting_for_brewfather_pause_after_mash_in_started\"" in body
    assert "target change by itself" in source


def test_runtime_flow_prefers_live_orchestration_mash_in_state() -> None:
    """The live orchestration sensor, not a stale button's attrs, owns visibility."""
    for path in RUNTIME_FLOW_CARDS:
        source = path.read_text(encoding="utf-8")
        assert "entity: sensor.brewassistant_brewzilla_control_reason" in source
        assert "const a = entity?.attributes || {};" in source
        assert "const gate = a.mash_in_gate_state || states['binary_sensor.brewassistant_brewzilla_mash_in_gate_pending']" in source
        assert "a.mash_in_gate_state === 'ready_for_mash_in'" in source
        assert "a.mash_in_gate_state === 'mash_in_started'" in source
        assert "a.mash_in_gate_state || a.state || gate?.attributes?.mash_in_gate_state" not in source
        assert "starts pump/circulation automatically" not in source
        assert "startar pump/cirkulation automatiskt" not in source
