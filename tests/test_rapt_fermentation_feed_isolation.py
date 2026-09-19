"""BF and BT presentation must not be rewritten to enforce RAPT brewing authority.

BF/BT may read, update and display the same upstream Brewfather data. Only the
selected brewing input can influence BA's normalized hot-side process/control.
These assertions validate card structure, not a Home Assistant browser test.
"""

from pathlib import Path

CARDS = Path(__file__).resolve().parents[1] / "dashboard" / "cards"


def test_existing_bf_feed_presentation_is_preserved_for_both_languages():
    for name in ("brewfather_feed.yaml", "brewfather_feed_sv.yaml"):
        card = (CARDS / name).read_text(encoding="utf-8")
        assert "sensor.brewassistant_brewfather_batch_phase" in card
        assert 'state: "fermenting"' in card
        assert "sensor.brewfather_recipe_name" in card
        assert "climate.fermentation_chamber" in card
        # No imposed link from RAPT source selection to BF feed visibility.
        assert "sensor.brewassistant_brewday_runtime_source" not in card
        assert "binary_sensor.brewzilla_profile_active" not in card


def test_bf_fermentation_logic_is_outside_brewing_source_guard():
    root = CARDS.parents[1]
    source_guard = (root / "custom_components/brewassistant/brewzilla/brewzilla_rapt_brewing_read_isolation.py").read_text(encoding="utf-8")
    installer = source_guard.split("def install_rapt_brewing_read_isolation", 1)[1]
    assert "fermentation" not in installer
    assert "setattr(core, name" not in source_guard
    assert "ownership.brewfather_batch_phase =" not in source_guard
