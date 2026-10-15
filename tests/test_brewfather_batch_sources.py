"""Regression checks for Brewfather batch versus BrewTracker ownership.

Run in the Home Assistant integration test environment (pytest).
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

from custom_components.brewassistant.cooling.cooling_runtime import _brewfather_pitch_target
from custom_components.brewassistant.fermentation_tracking.sensor import _brewfather_recipe_schedule


def _batch():
    start = datetime.now(timezone.utc) - timedelta(hours=12)
    return {
        "name": "Julöl 2026",
        "status": "Fermenting",
        "fermentingStart": start.isoformat(),
        "recipe": {
            "fermentation": {
                "steps": [
                    {"actualTime": int(start.timestamp() * 1000), "stepTemp": 18, "stepTime": 3},
                    {"actualTime": int((start + timedelta(days=3)).timestamp() * 1000), "stepTemp": 19, "stepTime": 3},
                ]
            }
        },
    }


def _hass(batches):
    hass = MagicMock()
    def state(entity_id):
        if entity_id == "sensor.brewfather_all_batches_data":
            return SimpleNamespace(state="1", attributes={"data": batches})
        if "brew_tracker" in entity_id or "brewtracker" in entity_id:
            return SimpleNamespace(state="1", attributes={"recipe": {
                "fermentation": {"steps": [{"actualTime": 0, "stepTemp": 30}]}
            }})
        return None
    hass.states.get.side_effect = state
    return hass


def test_cooling_uses_first_batch_fermentation_step_not_brewtracker():
    target, source = _brewfather_pitch_target(_hass([_batch()]))
    assert target == 18
    assert source == "sensor.brewfather_all_batches_data"


def test_tracking_uses_batch_schedule_not_brewtracker():
    coordinator = SimpleNamespace(hass=_hass([_batch()]))
    target, source, kind, schedule = _brewfather_recipe_schedule(coordinator)
    assert target == 18
    assert source == "sensor.brewfather_all_batches_data"
    assert kind == "brewfather_recipe_schedule"
    assert schedule is not None


def test_multiple_batches_do_not_choose_arbitrary_recipe():
    hass = _hass([_batch(), _batch()])
    assert _brewfather_pitch_target(hass) == (None, None)
    assert _brewfather_recipe_schedule(SimpleNamespace(hass=hass)) == (None, None, None, None)


def test_no_batch_does_not_fall_back_to_old_brewtracker_recipe():
    hass = _hass([])
    assert _brewfather_pitch_target(hass) == (None, None)
    assert _brewfather_recipe_schedule(SimpleNamespace(hass=hass)) == (None, None, None, None)
