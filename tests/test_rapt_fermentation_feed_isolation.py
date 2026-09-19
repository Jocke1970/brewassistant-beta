"""The browser-side fermentation feed must never read BrewTracker raw sensors.

Python's source guard cannot intercept JS and Jinja Lovelace reads. Keep the
fermentation surface sourced from independent BF fermentation/BA entities.
"""

from pathlib import Path


CARDS = Path(__file__).resolve().parents[1] / "dashboard" / "cards"


def test_fermentation_feed_en_sv_do_not_read_brewtracker_entities():
    for name in ("brewfather_feed.yaml", "brewfather_feed_sv.yaml"):
        card = (CARDS / name).read_text(encoding="utf-8")
        assert "states['sensor.brewfather_brew_tracker_" not in card
        assert "states['sensor.brewfather_brewtracker_" not in card
        assert "entity: sensor.brewfather_brew_tracker_" not in card
        assert "entity: sensor.brewfather_brewtracker_" not in card
        assert "state_attr('sensor.brewfather_brew_tracker_" not in card
        assert "state_attr('sensor.brewfather_brewtracker_" not in card
        assert "sensor.brewfather_recipe_name" in card
        assert "climate.fermentation_chamber" in card
        assert 'state: "fermenting"' in card
        assert "brewassistant.force_brewfather_refresh" not in card
