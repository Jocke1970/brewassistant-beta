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
        assert "runtime_timeline" in source
        assert "raw_stages" in source
        assert "pause_before" in source
        assert "pauseBefore" in source
        assert "startswith('paus')" in source


def test_recipe_cards_remain_visible_for_brewfather_planning_context() -> None:
    for source in _cards():
        assert source.startswith("type: vertical-stack")
        assert "brew_tracker_batch_status" in source
        assert "binary_sensor.brewassistant_runtime_brewfather_available" not in source
        assert "state: \"Brewfather Brew Tracker\"" not in source


def test_execution_schedule_humanizes_raw_brewtracker_events() -> None:
    en = EN.read_text(encoding="utf-8")
    sv = SV.read_text(encoding="utf-8")

    for source in (en, sv):
        assert "stage_paused" in source
        assert "raw_step_index" in source
        assert "value_num > 0" in source
        assert "show_anchor" in source
        assert "stage_marker" in source
        assert "temp_display" in source
        assert "desc.split('</br>', 1)[1]" in source
        assert "⏸" not in source
        assert "_{{ detail }}_" not in source
        assert "{{ detail }}{% endif %}" in source

    assert "Mäsktillsatser" in sv
    assert "Kryddor" in sv
    assert "· pausad" in sv
    assert "· kvittens" in sv
    assert "Mash additions" in en
    assert "Spices" in en
    assert "· paused" in en
    assert "· confirm" in en
