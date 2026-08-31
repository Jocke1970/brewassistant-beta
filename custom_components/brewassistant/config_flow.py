"""Config flow for BrewAssistant."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_CHAMBER_TEMP_ENTITY,
    CONF_COLD_CRASH_ACTIVE_ENTITY,
    CONF_COLD_CRASH_TARGET_ENTITY,
    CONF_FERMENTATION_HEAT_POWER_ENTITY,
    CONF_GRAVITY_ENTITY,
    CONF_KEGERATOR_AIR_TEMP_ENTITY,
    CONF_KEGERATOR_FAN_POWER_ENTITY,
    CONF_KEGERATOR_POWER_ENTITY,
    CONF_LIQUID_TEMP_ENTITY,
    CONF_RECIPE_TARGET_ENTITY,
    CONF_RUNTIME_COLD_CRASH_TARGET_ENTITY,
    CONF_RUNTIME_PRIMARY_TARGET_ENTITY,
    CONF_RUNTIME_RECIPE_NAME_ENTITY,
    CONF_RUNTIME_STATUS_ENTITY,
    CONF_RUNTIME_TARGET_FG_ENTITY,
    CONF_SHARED_KEGERATOR_FERMENTATION_COOLING,
    DEFAULT_CHAMBER_TEMP_ENTITY,
    DEFAULT_COLD_CRASH_ACTIVE_ENTITY,
    DEFAULT_COLD_CRASH_TARGET_ENTITY,
    DEFAULT_FERMENTATION_HEAT_POWER_ENTITY,
    DEFAULT_GRAVITY_ENTITY,
    DEFAULT_KEGERATOR_AIR_TEMP_ENTITY,
    DEFAULT_KEGERATOR_FAN_POWER_ENTITY,
    DEFAULT_KEGERATOR_POWER_ENTITY,
    DEFAULT_LIQUID_TEMP_ENTITY,
    DEFAULT_RECIPE_TARGET_ENTITY,
    DEFAULT_RUNTIME_COLD_CRASH_TARGET_ENTITY,
    DEFAULT_RUNTIME_PRIMARY_TARGET_ENTITY,
    DEFAULT_RUNTIME_RECIPE_NAME_ENTITY,
    DEFAULT_RUNTIME_STATUS_ENTITY,
    DEFAULT_RUNTIME_TARGET_FG_ENTITY,
    DEFAULT_SHARED_KEGERATOR_FERMENTATION_COOLING,
    DOMAIN,
    NAME,
)

ENTITY_CONFIG_KEYS = (
    CONF_LIQUID_TEMP_ENTITY,
    CONF_CHAMBER_TEMP_ENTITY,
    CONF_RECIPE_TARGET_ENTITY,
    CONF_COLD_CRASH_ACTIVE_ENTITY,
    CONF_COLD_CRASH_TARGET_ENTITY,
    CONF_GRAVITY_ENTITY,
    CONF_KEGERATOR_AIR_TEMP_ENTITY,
    CONF_KEGERATOR_POWER_ENTITY,
    CONF_KEGERATOR_FAN_POWER_ENTITY,
    CONF_FERMENTATION_HEAT_POWER_ENTITY,
    CONF_RUNTIME_RECIPE_NAME_ENTITY,
    CONF_RUNTIME_STATUS_ENTITY,
    CONF_RUNTIME_PRIMARY_TARGET_ENTITY,
    CONF_RUNTIME_COLD_CRASH_TARGET_ENTITY,
    CONF_RUNTIME_TARGET_FG_ENTITY,
)

BOOLEAN_CONFIG_KEYS = (
    CONF_SHARED_KEGERATOR_FERMENTATION_COOLING,
)

CONFIG_KEYS = ENTITY_CONFIG_KEYS + BOOLEAN_CONFIG_KEYS

DEFAULTS = {
    CONF_LIQUID_TEMP_ENTITY: DEFAULT_LIQUID_TEMP_ENTITY,
    CONF_CHAMBER_TEMP_ENTITY: DEFAULT_CHAMBER_TEMP_ENTITY,
    CONF_RECIPE_TARGET_ENTITY: DEFAULT_RECIPE_TARGET_ENTITY,
    CONF_COLD_CRASH_ACTIVE_ENTITY: DEFAULT_COLD_CRASH_ACTIVE_ENTITY,
    CONF_COLD_CRASH_TARGET_ENTITY: DEFAULT_COLD_CRASH_TARGET_ENTITY,
    CONF_GRAVITY_ENTITY: DEFAULT_GRAVITY_ENTITY,
    CONF_KEGERATOR_AIR_TEMP_ENTITY: DEFAULT_KEGERATOR_AIR_TEMP_ENTITY,
    CONF_KEGERATOR_POWER_ENTITY: DEFAULT_KEGERATOR_POWER_ENTITY,
    CONF_KEGERATOR_FAN_POWER_ENTITY: DEFAULT_KEGERATOR_FAN_POWER_ENTITY,
    CONF_FERMENTATION_HEAT_POWER_ENTITY: DEFAULT_FERMENTATION_HEAT_POWER_ENTITY,
    CONF_RUNTIME_RECIPE_NAME_ENTITY: DEFAULT_RUNTIME_RECIPE_NAME_ENTITY,
    CONF_RUNTIME_STATUS_ENTITY: DEFAULT_RUNTIME_STATUS_ENTITY,
    CONF_RUNTIME_PRIMARY_TARGET_ENTITY: DEFAULT_RUNTIME_PRIMARY_TARGET_ENTITY,
    CONF_RUNTIME_COLD_CRASH_TARGET_ENTITY: DEFAULT_RUNTIME_COLD_CRASH_TARGET_ENTITY,
    CONF_RUNTIME_TARGET_FG_ENTITY: DEFAULT_RUNTIME_TARGET_FG_ENTITY,
    CONF_SHARED_KEGERATOR_FERMENTATION_COOLING: DEFAULT_SHARED_KEGERATOR_FERMENTATION_COOLING,
}


def _schema(defaults: dict[str, Any]) -> vol.Schema:
    """Build the config/options schema."""
    fields: dict[Any, Any] = {
        vol.Optional(key, default=defaults.get(key, DEFAULTS[key])): str
        for key in ENTITY_CONFIG_KEYS
    }
    for key in BOOLEAN_CONFIG_KEYS:
        fields[vol.Optional(key, default=defaults.get(key, DEFAULTS[key]))] = bool
    return vol.Schema(fields)


class BrewAssistantConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a BrewAssistant config flow."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> BrewAssistantOptionsFlow:
        """Return the options flow handler."""
        return BrewAssistantOptionsFlow(config_entry)

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Handle the initial step."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(title=NAME, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=_schema(DEFAULTS),
            errors={},
        )


class BrewAssistantOptionsFlow(config_entries.OptionsFlowWithConfigEntry):
    """Handle BrewAssistant options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize the options flow."""
        super().__init__(config_entry)

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Manage BrewAssistant options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        defaults = dict(DEFAULTS)
        defaults.update(self.config_entry.data)
        defaults.update(self.config_entry.options)

        return self.async_show_form(
            step_id="init",
            data_schema=_schema(defaults),
            errors={},
        )
