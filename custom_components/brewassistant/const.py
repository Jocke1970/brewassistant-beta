"""Constants for the BrewAssistant integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "brewassistant"
NAME = "BrewAssistant"
VERSION = "0.1.0"

PLATFORMS: list[str] = ["sensor", "binary_sensor"]

DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)

CONF_LIQUID_TEMP_ENTITY = "liquid_temp_entity"
CONF_CHAMBER_TEMP_ENTITY = "chamber_temp_entity"
CONF_RECIPE_TARGET_ENTITY = "recipe_target_entity"
CONF_GRAVITY_ENTITY = "gravity_entity"

DEFAULT_LIQUID_TEMP_ENTITY = "sensor.yellow_pill_temperature"
DEFAULT_CHAMBER_TEMP_ENTITY = "sensor.kyl_temperatur_4"
DEFAULT_RECIPE_TARGET_ENTITY = "sensor.brew_recipe_active_target_temp"
DEFAULT_GRAVITY_ENTITY = "sensor.yellow_pill_gravity_2"

ATTR_SOURCE = "source"
ATTR_SOURCE_ENTITY = "source_entity"
ATTR_TARGET_ENTITY = "target_entity"
