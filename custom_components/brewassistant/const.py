"""Constants for the BrewAssistant integration."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "brewassistant"
NAME = "BrewAssistant"
VERSION = "0.1.0"

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]

DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)

CONF_LIQUID_TEMP_ENTITY = "liquid_temp_entity"
CONF_CHAMBER_TEMP_ENTITY = "chamber_temp_entity"
CONF_RECIPE_TARGET_ENTITY = "recipe_target_entity"
CONF_COLD_CRASH_ACTIVE_ENTITY = "cold_crash_active_entity"
CONF_COLD_CRASH_TARGET_ENTITY = "cold_crash_target_entity"
CONF_GRAVITY_ENTITY = "gravity_entity"

DEFAULT_LIQUID_TEMP_ENTITY = "sensor.yellow_pill_temperature"
DEFAULT_CHAMBER_TEMP_ENTITY = "sensor.kyl_temperatur_4"
DEFAULT_RECIPE_TARGET_ENTITY = "sensor.brew_recipe_active_target_temp"
DEFAULT_COLD_CRASH_ACTIVE_ENTITY = "input_boolean.brew_cold_crash_active"
DEFAULT_COLD_CRASH_TARGET_ENTITY = "input_number.cold_crash_temp_target"
DEFAULT_GRAVITY_ENTITY = "sensor.yellow_pill_gravity"

ATTR_SOURCE = "source"
ATTR_SOURCE_ENTITY = "source_entity"
ATTR_TARGET_ENTITY = "target_entity"
ATTR_TARGET_MODE = "target_mode"
