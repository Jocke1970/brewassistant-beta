"""Compatibility registration bridge for separated fermentation backends."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity

from ..coordinator import BrewAssistantCoordinator
from ..fermentation_chamber.air_target import (
    AirTargetRecommendation,
    AirTargetSensorConfig,
    BrewAssistantAirTargetSensor,
    build_air_target_snapshot,
    create_fermentation_chamber_sensors,
)
from ..fermentation_tracking.sensor import create_fermentation_tracking_sensors

__all__ = [
    "AirTargetRecommendation",
    "AirTargetSensorConfig",
    "BrewAssistantAirTargetSensor",
    "build_air_target_snapshot",
    "create_fermentation_air_target_sensors",
]


def create_fermentation_air_target_sensors(
    coordinator: BrewAssistantCoordinator,
) -> list[SensorEntity]:
    """Register chamber and tracking sensors while old root imports remain compatible."""
    return [
        *create_fermentation_chamber_sensors(coordinator),
        *create_fermentation_tracking_sensors(coordinator),
    ]
