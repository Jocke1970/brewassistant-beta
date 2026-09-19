"""BF fermentation feed must not depend on BT brewing batch phase.

The UI uses BA's fermentation/cold-crash process stage, not the selected RAPT
or BrewTracker hot-side source. These are source/structure assertions, not
browser or actual HA Lovelace rendering tests.
"""

from pathlib import Path

CARDS = Path(__file__).resolve().parents[1] / "dashboard" / "cards"


def test_fermentation_feed_en_sv_do_not_read_bt_or_gate_on_bt_phase():
    for name in ("brewfather_feed.yaml", "brewfather_feed_sv.yaml"):
        card = (CARDS / name).read_text(encoding="utf-8")
        assert "sensor.brewfather_brew_tracker_" not in card
        assert "sensor.brewfather_brewtracker_" not in card
        assert "sensor.brewassistant_brewfather_batch_phase" not in card
        assert "switch.brewassistant_show_brewfather_feed" in card
        assert "sensor.brewassistant_process_current_action_stage" in card
        assert 'state: "fermentation"' in card
        assert 'state: "cold_crash"' in card
        assert "sensor.brewfather_recipe_name" in card
        assert "climate.fermentation_chamber" in card
        assert "brewassistant.force_brewfather_refresh" not in card


def test_fermentation_process_stage_is_not_derived_from_bt_brewing_status():
    coordinator = (CARDS.parents[1] / "custom_components/brewassistant/coordinator.py").read_text(encoding="utf-8")
    sensor = (CARDS.parents[1] / "custom_components/brewassistant/sensor.py").read_text(encoding="utf-8")
    assert 'runtime_status = _state_string(self.hass, "sensor.recipe_runtime_status")' in coordinator
    assert 'elif normalized_runtime == "fermenting":' in coordinator
    assert 'or bool(fermentation.get("active"))' in coordinator
    assert 'key="process_current_action_stage"' in sensor
    assert "brewfather_brew_tracker" not in coordinator
