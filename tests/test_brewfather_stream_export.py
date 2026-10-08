"""Regression contract for provider-neutral Brewfather stream telemetry."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE = (
    ROOT
    / "custom_components/brewassistant/fermentation_tracking/brewfather_stream.py"
)
SENSOR_PLATFORM = ROOT / "custom_components/brewassistant/sensor.py"


def test_brewfather_stream_module_is_syntax_valid() -> None:
    ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))


def test_brewfather_stream_has_stable_provider_neutral_entities() -> None:
    source = MODULE.read_text(encoding="utf-8")

    for key in (
        "brewfather_stream_status",
        "brewfather_stream_temperature",
        "brewfather_stream_gravity",
        "brewfather_stream_temp_target",
        "brewfather_stream_gravity_target",
        "brewfather_stream_aux_temperature",
    ):
        assert f'key="{key}"' in source


def test_brewfather_stream_requires_fresh_primary_temperature() -> None:
    source = MODULE.read_text(encoding="utf-8")

    assert "MAX_STREAM_SAMPLE_AGE_SECONDS = 20 * 60" in source
    assert 'status = "blocked_stale_temperature"' in source
    assert "eligible = active and temperature is not None" in source
    assert '"brewfather_sample_observed_at"' in source


def test_brewfather_stream_aux_semantics_follow_provider() -> None:
    source = MODULE.read_text(encoding="utf-8")

    assert "CHAMBER_AUX_ENTITY" in source
    assert "GF30_AUX_ENTITY" in source
    assert '"fridge_temp_chamber_air"' in source
    assert '"fridge_temp_coolant_reservoir"' in source
    assert '"unmapped_room_temperature"' in source


def test_brewfather_stream_does_not_mislabel_gf30_internal_temperature() -> None:
    source = MODULE.read_text(encoding="utf-8")

    aux_block = source.split("aux_entity = None", 1)[1].split(
        "aux_temperature = None", 1
    )[0]
    assert "gf30_controller_temperature" not in aux_block
    assert "gf30_coolant_temperature" in source


def test_brewfather_stream_transport_remains_outside_brewassistant() -> None:
    source = MODULE.read_text(encoding="utf-8").lower()

    assert '"transport_owner": "brewfather_integration"' in source
    assert '"http_transport_in_brewassistant": false' in source
    assert "aiohttp" not in source
    assert "session.post" not in source
    assert "log.brewfather.net" not in source


def test_sensor_platform_registers_brewfather_stream_sources() -> None:
    source = SENSOR_PLATFORM.read_text(encoding="utf-8")

    assert "create_brewfather_stream_sensors" in source
    assert "+ create_brewfather_stream_sensors(coordinator)" in source
