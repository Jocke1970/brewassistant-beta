"""Regression checks for Brewfather/recipe fermentation ramp target consumption."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "custom_components/brewassistant/fermentation_tracking/snapshot.py"
SENSOR = ROOT / "custom_components/brewassistant/fermentation_tracking/sensor.py"


def test_tracking_snapshot_prefers_external_schedule_target() -> None:
    source = SNAPSHOT.read_text(encoding="utf-8")
    assert "external_target_temperature_c" in source
    assert 'recommended_temperature_source = external_target_source or "external_schedule"' in source
    assert '"recommended_temperature_source": recommended_temperature_source' in source
    assert '"recommended_temperature_entity": recommended_temperature_entity' in source


def test_tracking_sensor_reads_recipe_target_and_schedule_metadata() -> None:
    source = SENSOR.read_text(encoding="utf-8")
    assert "CONF_RECIPE_TARGET_ENTITY" in source
    assert 'state.attributes.get("schedule_target_temperature")' in source
    assert '"brewfather_schedule"' in source
    assert "external_target_temperature_c=external_target" in source
