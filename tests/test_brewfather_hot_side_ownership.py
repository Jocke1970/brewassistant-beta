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


def test_only_brewing_is_authoritative_for_hot_side() -> None:
    source = OWNERSHIP.read_text(encoding="utf-8")
    assert 'return brewfather_batch_phase(hass) == BREWING' in source
    assert 'return brewfather_batch_phase(hass) in {PLANNING, BREWING}' in source
    assert 'core.brewfather_session_active = brewfather_hot_side_active' in source
    assert 'if value in {PLANNING, BREWING, FERMENTING}' in source


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


def test_brewfather_cards_show_planning_as_ready_not_authoritative() -> None:
    for path in (BT_EN, BT_SV, FEED_EN, FEED_SV):
        source = path.read_text(encoding="utf-8")
        assert "sensor.brewfather_brew_tracker_status" in source
        assert 'state_not: "inactive"' in source
        assert "brew_tracker_batch_status" in source
        assert "planning" in source.lower()
        assert "Brewing" in source


def test_brewtracker_cards_do_not_use_manual_runtime_as_planning_content() -> None:
    for path in (BT_EN, BT_SV):
        source = path.read_text(encoding="utf-8")
        assert "connected but not authoritative" in source or "inkopplad men inte styrande" in source
        assert "Manual Brewday" in source
