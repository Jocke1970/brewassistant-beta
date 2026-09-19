"""BF/BT UI remains intact when RAPT is the selected brewing input.

The upstream Brewfather payload can be read by both BF and BT; only the chosen
brewing input determines BrewAssistant's hot-side process and controls. These
are static presentation checks, not a Lovelace browser integration test.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARDS = ROOT / "dashboard" / "cards"


def test_complete_existing_bf_feed_is_preserved_in_both_languages():
    for name in ("brewfather_feed.yaml", "brewfather_feed_sv.yaml"):
        card = (CARDS / name).read_text(encoding="utf-8")
        assert "sensor.brewassistant_brewfather_batch_phase" in card
        assert 'state: "fermenting"' in card
        assert "sensor.brewfather_brew_tracker_status" in card
        assert "brew_tracker_recipe_name" in card
        assert "brew_tracker_batch_name" in card
        assert "brew_tracker_batch_id" in card
        assert "climate.fermentation_chamber" in card
        assert "grid-template-columns:repeat(4,minmax(0,1fr))" in card
        assert "type: horizontal-stack" in card
        assert "sensor.brewassistant_brewday_runtime_source" not in card
        assert "binary_sensor.brewzilla_profile_active" not in card


def test_bf_fermentation_logic_is_outside_brewing_source_guard():
    source_guard = (ROOT / "custom_components/brewassistant/brewzilla/brewzilla_rapt_brewing_read_isolation.py").read_text(encoding="utf-8")
    installer = source_guard.split("def install_rapt_brewing_read_isolation", 1)[1]
    assert "fermentation" not in installer
    assert "setattr(core, name" not in source_guard
    assert "ownership.brewfather_batch_phase =" not in source_guard
