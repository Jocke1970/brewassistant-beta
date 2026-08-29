"""Regression checks for Brewfather hot-side ownership and Planning visibility."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OWNERSHIP = ROOT / "custom_components/brewassistant/brewday/brewfather_ownership.py"
BREWDAY_INIT = ROOT / "custom_components/brewassistant/brewday/__init__.py"
STORE = ROOT / "custom_components/brewassistant/brewday/manual_brewday_store.py"
BT_EN = ROOT / "dashboard/cards/brewtracker_runtime.yaml"
BT_SV = ROOT / "dashboard/cards/brewtracker_runtime_sv.yaml"
FEED_EN = ROOT / "dashboard/cards/brewfather_feed.yaml"
FEED_SV = ROOT / "dashboard/cards/brewfather_feed_sv.yaml"


def test_python_sources_parse() -> None:
    for path in (OWNERSHIP, BREWDAY_INIT, STORE):
        ast.parse(path.read_text(encoding="utf-8"))


def test_brewing_requires_positive_tracker_start_evidence_for_hot_side() -> None:
    source = OWNERSHIP.read_text(encoding="utf-8")
    assert "def brewfather_tracker_prestart" in source
    assert "def _tracker_started_evidence" in source
    assert "if brewfather_batch_phase(hass) != BREWING" in source
    assert "if brewfather_tracker_prestart(hass):" in source
    assert "if _tracker_started_evidence(hass):" in source
    assert 'state["started"] = True' in source
    assert 'return brewfather_batch_phase(hass) in {PLANNING, BREWING}' in source
    assert 'core.brewfather_session_active = brewfather_hot_side_active' in source
    assert 'if value in {PLANNING, BREWING, FERMENTING}' in source


def test_exact_brewfather_prestart_signature_is_fail_safe() -> None:
    """Protect the physical-test payload: Brewing but mash timer not started."""
    source = OWNERSHIP.read_text(encoding="utf-8")
    expected = (
        'source_status != "paused"',
        'stage_index == 0',
        'step_index == 0',
        'stage_paused',
        'progressPercent',
        'remainingSeconds',
        'duration',
        'abs(remaining - duration) <= 1.0',
        'name == "start"',
        '"starta mäsktimer" in description',
        '"start mash timer" in description',
        'return False\n\n\ndef brewfather_cards_visible',
    )
    for token in expected:
        assert token in source

    # Brewfather reported active=true before Play in the captured payload. It
    # must not be accepted by the explicit pre-start predicate as start proof.
    prestart = source.split("def brewfather_tracker_prestart", 1)[1].split("def _tracker_started_evidence", 1)[0]
    assert 'live_attr(hass, "active")' not in prestart


def test_started_tracker_latch_survives_pause_but_resets_for_new_tracker() -> None:
    source = OWNERSHIP.read_text(encoding="utf-8")
    assert 'for attribute in ("tracker_id", "brew_tracker_batch_id", "batch_id")' in source
    assert 'if state.get("tracker_id") != identity:' in source
    assert 'state["started"] = False' in source
    assert 'if state.get("started") is True:' in source
    assert 'source_status == core.BREWDAY_ACTIVE_STATUS' in source
    assert 'if stage_index > 0 or step_index > 0:' in source
    assert 'progress > 0.01' in source
    assert 'remaining < duration - 1.0' in source


def test_paused_live_step_wins_over_equal_time_anchor_heuristic() -> None:
    source = OWNERSHIP.read_text(encoding="utf-8")
    assert "_BASE_RESOLVE_STEP_INDEX = core.resolve_step_index_from_remaining" in source
    assert "def _resolve_step_index_with_paused_live_step" in source
    assert 'if core.as_bool(stage.get("paused")) is True and fallback is not None:' in source
    assert "return fallback" in source
    assert "return _BASE_RESOLVE_STEP_INDEX(stage, stage_remaining, fallback)" in source
    assert "core.resolve_step_index_from_remaining = _resolve_step_index_with_paused_live_step" in source


def test_ownership_policy_is_installed_before_brewday_submodules_use_core() -> None:
    source = BREWDAY_INIT.read_text(encoding="utf-8")
    assert "from .brewfather_ownership import install_core_ownership_policy" in source
    assert "install_core_ownership_policy()" in source


def test_manual_handoff_safe_down_is_event_driven() -> None:
    source = STORE.read_text(encoding="utf-8")
    expected = (
        "async_track_state_change_event",
        "entity_candidates(BF_STATUS)",
        "pause_manual_brewday_for_brewfather(hass)",
        "session.state != ManualRuntimeState.PAUSED",
        "async_apply_brewzilla_target_if_allowed(hass)",
        "last_brewfather_handoff_safe_down",
    )
    for token in expected:
        assert token in source


def test_brewtracker_cards_show_planning_and_prestart_without_claiming_ownership() -> None:
    for path in (BT_EN, BT_SV):
        source = path.read_text(encoding="utf-8")
        assert "sensor.brewfather_brew_tracker_status" in source
        assert "sensor.brewassistant_brewfather_batch_phase" in source
        assert 'state: "planning"' in source
        assert 'state: "brewing"' in source
        assert "prestart" in source
        assert "Play" in source
        assert "hot-side ownership" in source


def test_brewfather_post_brew_cards_are_fermenting_only() -> None:
    for path in (FEED_EN, FEED_SV):
        source = path.read_text(encoding="utf-8")
        assert "sensor.brewassistant_brewfather_batch_phase" in source
        assert 'state: "fermenting"' in source
        assert 'state: "planning"' not in source
        assert 'state: "brewing"' not in source


def test_brewtracker_cards_do_not_use_manual_runtime_as_planning_content() -> None:
    for path in (BT_EN, BT_SV):
        source = path.read_text(encoding="utf-8")
        assert "BrewTracker ready" in source or "BrewTracker redo" in source
        assert "Manual Brewday" not in source
