"""Regression checks for BrewAssistant-owned fermentation recipe schedules."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEDULE = ROOT / "custom_components/brewassistant/fermentation_tracking/recipe_schedule.py"
SNAPSHOT = ROOT / "custom_components/brewassistant/fermentation_tracking/snapshot.py"
SENSOR = ROOT / "custom_components/brewassistant/fermentation_tracking/sensor.py"


def _load_schedule_module():
    spec = importlib.util.spec_from_file_location("brewassistant_recipe_schedule", SCHEDULE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _recipe() -> dict:
    start = datetime(2026, 9, 9, 0, 0, tzinfo=timezone.utc)
    day_ms = 24 * 60 * 60 * 1000
    start_ms = int(start.timestamp() * 1000)
    return {
        "name": "Ramp test",
        "fermentation": {
            "steps": [
                {"actualTime": start_ms, "stepTemp": 18.0, "stepTime": 3},
                {"actualTime": start_ms + 4 * day_ms, "stepTemp": 19.0, "ramp": 1, "stepTime": 3},
                {"actualTime": start_ms + 8 * day_ms, "stepTemp": 20.5, "ramp": 1, "stepTime": 5},
                {"actualTime": start_ms + 14 * day_ms, "stepTemp": 2.0, "ramp": 1, "stepTime": 3},
            ]
        },
    }


def test_recipe_schedule_keeps_fixed_step_target() -> None:
    module = _load_schedule_module()
    started = datetime(2026, 9, 9, 10, 0, tzinfo=timezone.utc)
    schedule = module.build_recipe_temperature_schedule(
        _recipe(),
        fermentation_started_at=started,
        now=started + timedelta(days=1),
    )
    assert schedule["target_temperature_c"] == 18.0
    assert schedule["ramp_active"] is False


def test_recipe_schedule_interpolates_rising_ramp() -> None:
    module = _load_schedule_module()
    started = datetime(2026, 9, 9, 10, 0, tzinfo=timezone.utc)
    schedule = module.build_recipe_temperature_schedule(
        _recipe(),
        fermentation_started_at=started,
        now=started + timedelta(days=3, hours=12),
    )
    assert schedule["target_temperature_c"] == 18.5
    assert schedule["ramp_active"] is True
    assert schedule["ramp_start_temperature_c"] == 18.0
    assert schedule["ramp_target_temperature_c"] == 19.0
    assert schedule["ramp_progress_percent"] == 50.0


def test_recipe_schedule_interpolates_falling_ramp() -> None:
    module = _load_schedule_module()
    started = datetime(2026, 9, 9, 10, 0, tzinfo=timezone.utc)
    schedule = module.build_recipe_temperature_schedule(
        _recipe(),
        fermentation_started_at=started,
        now=started + timedelta(days=13, hours=12),
    )
    assert schedule["target_temperature_c"] == 11.25
    assert schedule["ramp_active"] is True
    assert schedule["ramp_start_temperature_c"] == 20.5
    assert schedule["ramp_target_temperature_c"] == 2.0
    assert schedule["ramp_progress_percent"] == 50.0


def test_tracking_owns_recipe_schedule_instead_of_brewfather_metadata() -> None:
    sensor_source = SENSOR.read_text(encoding="utf-8")
    schedule_source = SCHEDULE.read_text(encoding="utf-8")
    snapshot_source = SNAPSHOT.read_text(encoding="utf-8")

    assert "sensor.brewfather_brew_tracker_raw" in sensor_source
    assert 'state.attributes.get("recipe")' in sensor_source
    assert "build_recipe_temperature_schedule" in sensor_source
    assert "schedule_target_temperature" not in sensor_source
    assert '"brewfather_recipe_schedule"' in sensor_source
    assert '"temperature_schedule_ramp_active"' in snapshot_source
    assert "stepTemp" in schedule_source
    assert "actualTime" in schedule_source
    assert 'raw.get("ramp")' in schedule_source
