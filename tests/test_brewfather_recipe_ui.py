"""Regression checks for Brewfather full-recipe presentation."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EN = ROOT / "dashboard/cards/brewfather_recipe.yaml"
SV = ROOT / "dashboard/cards/brewfather_recipe_sv.yaml"


def _cards() -> list[str]:
    return [EN.read_text(encoding="utf-8"), SV.read_text(encoding="utf-8")]


def test_recipe_cards_use_full_batch_recipe_payload() -> None:
    for source in _cards():
        assert "sensor.brewfather_brew_tracker_raw" in source
        assert "state_attr(raw_entity, 'recipe')" in source
        assert "recipe_data.get('mash')" in source
        assert "recipe_data.get('hops', [])" in source
        assert "recipe_data.get('boilTime')" in source


def test_recipe_cards_keep_brewtracker_execution_schedule_separate() -> None:
    for source in _cards():
        assert "sensor.brewassistant_brewday_runtime_summary" in source
        assert "timeline" in source
        assert "pause_before" in source
        assert "startswith('paus')" in source


def test_recipe_cards_remain_available_for_brewfather_planning_context() -> None:
    for source in _cards():
        assert "binary_sensor.brewassistant_runtime_brewfather_available" in source
        assert "brew_tracker_batch_status" in source
        assert "state: \"Brewfather Brew Tracker\"" not in source
