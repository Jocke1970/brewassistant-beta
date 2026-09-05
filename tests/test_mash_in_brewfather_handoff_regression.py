"""Regression contracts for the Mash-In -> Brewfather Continue handoff."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_mash_in_complete_safe_down_guard.py"
RUNTIME_FLOW_CARDS = (
    ROOT / "dashboard/cards/brewassistant_brewday_runtime_flow.yaml",
    ROOT / "dashboard/cards/brewassistant_brewday_runtime_flow_sv.yaml",
)


def test_running_brewfather_alone_cannot_auto_complete_mash_in() -> None:
    source = BRIDGE.read_text(encoding="utf-8")
    body = source.split("def _auto_complete_allowed", 1)[1].split(
        "async def _apply_brewfather_resume_auto_complete", 1
    )[0]

    assert "def _gate_origin_target" in source
    assert "waiting_for_brewfather_progress" in body
    assert "running_after_mash_in_target_advanced" in body
    assert "paused_to_running_mash_target" in body
    assert "paused_to_running_mash_stage" in body
    assert "running_while_mash_in_started_mash_target" not in body
    assert "running_while_mash_in_started_mash_stage" not in body


def test_runtime_flow_prefers_live_orchestration_mash_in_state() -> None:
    preferred = (
        "oz.mash_in_gate_state || gate?.attributes?.state || "
        "gate?.attributes?.mash_in_gate_state"
    )
    stale_first = (
        "a.mash_in_gate_state || a.state || gate?.attributes?.mash_in_gate_state"
    )

    for path in RUNTIME_FLOW_CARDS:
        source = path.read_text(encoding="utf-8")
        assert preferred in source, f"live mash-in state priority missing from {path.name}"
        assert stale_first not in source, f"stale button state still outranks live state in {path.name}"
        assert "['ready_for_mash_in','mash_in_started'].includes(state)" in source
