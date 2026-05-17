"""Config flow for BrewAssistant."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_CHAMBER_TEMP_ENTITY,
    CONF_COLD_CRASH_ACTIVE_ENTITY,
    CONF_COLD_CRASH_TARGET_ENTITY,
    CONF_GRAVITY_ENTITY,
    CONF_LIQUID_TEMP_ENTITY,
    CONF_RECIPE_TARGET_ENTITY,
    DEFAULT_CHAMBER_TEMP_ENTITY,
    DEFAULT_COLD_CRASH_ACTIVE_ENTITY,
    DEFAULT_COLD_CRASH_TARGET_ENTITY,
    DEFAULT_GRAVITY_ENTITY,
    DEFAULT_LIQUID_TEMP_ENTITY,
    DEFAULT_RECIPE_TARGET_ENTITY,
    DOMAIN,
    NAME,
)

CONFIG_KEYS = (
    CONF_LIQUID_TEMP_ENTITY,
    CONF_CHAMBER_TEMP_ENTITY,
    CONF_RECIPE_TARGET_ENTITY,
    CONF_COLD_CRASH_ACTIVE_ENTITY,
    CONF_COLD_CRASH_TARGET_ENTITY,
    CONF_GRAVITY_ENTITY,
)

DEFAULTS = {
    CONF_LIQUID_TEMP_ENTITY: DEFAULT_LIQUID_TEMP_ENTITY,
    CONF_CHAMBER_TEMP_ENTITY: DEFAULT_CHAMBER_TEMP_ENTITY,
    CONF_RECIPE_TARGET_ENTITY: DEFAULT_RECIPE_TARGET_ENTITY,
    CONF_COLD_CRASH_ACTIVE_ENTITY: DEFAULT_COLD_CRASH_ACTIVE_ENTITY,
    CONF_COLD_CRASH_TARGET_ENTITY: DEFAULT_COLD_CRASH_TARGET_ENTITY,
    CONF_GRAVITY_ENTITY: DEFAULT_GRAVITY_ENTITY,
}


def _schema(defaults: dict[str, Any]) -> vol.Schema:
    """Build the config/options schema."""
    return vol.Schema(
        {
            vol.Optional(key, default=defaults.get(key, DEFAULTS[key])): str
            for key in CONFIG_KEYS
        }
    )


class BrewAssistantConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a BrewAssistant config flow."""

    VERSION = 1

    @staticmethod
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


class BrewAssistantOptionsFlow(config_entries.OptionsFlow):
    """Handle BrewAssistant options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize the options flow."""
        self.config_entry = config_entry

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
