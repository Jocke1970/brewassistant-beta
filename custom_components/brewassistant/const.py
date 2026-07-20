"""Constants for the BrewAssistant integration."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "brewassistant"
NAME = "BrewAssistant"
VERSION = "1.2.0"

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.BUTTON,
]

DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)

CONF_LIQUID_TEMP_ENTITY = "liquid_temp_entity"
CONF_CHAMBER_TEMP_ENTITY = "chamber_temp_entity"
CONF_RECIPE_TARGET_ENTITY = "recipe_target_entity"
CONF_COLD_CRASH_ACTIVE_ENTITY = "cold_crash_active_entity"
CONF_COLD_CRASH_TARGET_ENTITY = "cold_crash_target_entity"
CONF_GRAVITY_ENTITY = "gravity_entity"
CONF_KEGERATOR_AIR_TEMP_ENTITY = "kegerator_air_temp_entity"
CONF_KEGERATOR_POWER_ENTITY = "kegerator_power_entity"
CONF_KEGERATOR_FAN_POWER_ENTITY = "kegerator_fan_power_entity"
CONF_FERMENTATION_HEAT_POWER_ENTITY = "fermentation_heat_power_entity"

CONF_RUNTIME_RECIPE_NAME_ENTITY = "runtime_recipe_name_entity"
CONF_RUNTIME_STATUS_ENTITY = "runtime_status_entity"
CONF_RUNTIME_PRIMARY_TARGET_ENTITY = "runtime_primary_target_entity"
CONF_RUNTIME_COLD_CRASH_TARGET_ENTITY = "runtime_cold_crash_target_entity"
CONF_RUNTIME_TARGET_FG_ENTITY = "runtime_target_fg_entity"

DEFAULT_LIQUID_TEMP_ENTITY = "sensor.yellow_pill_temperature"
DEFAULT_CHAMBER_TEMP_ENTITY = "sensor.kyl_temperatur_4"
DEFAULT_RECIPE_TARGET_ENTITY = "sensor.brew_recipe_active_target_temp"
DEFAULT_COLD_CRASH_ACTIVE_ENTITY = "input_boolean.brew_cold_crash_active"
DEFAULT_COLD_CRASH_TARGET_ENTITY = "input_number.cold_crash_temp_target"
DEFAULT_GRAVITY_ENTITY = "sensor.yellow_pill_gravity"
DEFAULT_KEGERATOR_AIR_TEMP_ENTITY = "sensor.kyl_temperatur_4"
DEFAULT_KEGERATOR_POWER_ENTITY = "sensor.brewassistant_kegerator_power_w"
DEFAULT_KEGERATOR_FAN_POWER_ENTITY = "sensor.kegerator_fan_power"
DEFAULT_FERMENTATION_HEAT_POWER_ENTITY = "sensor.fermentation_heat_mat_power"

DEFAULT_RUNTIME_RECIPE_NAME_ENTITY = "sensor.recipe_runtime_name"
DEFAULT_RUNTIME_STATUS_ENTITY = "sensor.recipe_runtime_status"
DEFAULT_RUNTIME_PRIMARY_TARGET_ENTITY = "sensor.recipe_runtime_primary_temp"
DEFAULT_RUNTIME_COLD_CRASH_TARGET_ENTITY = "sensor.recipe_runtime_cold_crash_temp"
DEFAULT_RUNTIME_TARGET_FG_ENTITY = "sensor.recipe_runtime_target_fg"

ATTR_SOURCE = "source"
ATTR_SOURCE_ENTITY = "source_entity"
ATTR_TARGET_ENTITY = "target_entity"
ATTR_TARGET_MODE = "target_mode"
ATTR_ICON_HINT = "icon_hint"
ATTR_COLOR_HINT = "color_hint"
ATTR_PROCESS_REASON = "process_reason"
ATTR_RECOMMENDATION_REASON = "recommendation_reason"
ATTR_BLOCK_REASON = "block_reason"
