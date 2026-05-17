"""Config flow for BrewAssistant."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_CHAMBER_TEMP_ENTITY,
    CONF_GRAVITY_ENTITY,
    CONF_LIQUID_TEMP_ENTITY,
    CONF_RECIPE_TARGET_ENTITY,
    DEFAULT_CHAMBER_TEMP_ENTITY,
    DEFAULT_GRAVITY_ENTITY,
    DEFAULT_LIQUID_TEMP_ENTITY,
    DEFAULT_RECIPE_TARGET_ENTITY,
    DOMAIN,
    NAME,
)


class BrewAssistantConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a BrewAssistant config flow."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Handle the initial step."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(title=NAME, data=user_input)

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_LIQUID_TEMP_ENTITY,
                    default=DEFAULT_LIQUID_TEMP_ENTITY,
                ): str,
                vol.Optional(
                    CONF_CHAMBER_TEMP_ENTITY,
                    default=DEFAULT_CHAMBER_TEMP_ENTITY,
                ): str,
                vol.Optional(
                    CONF_RECIPE_TARGET_ENTITY,
                    default=DEFAULT_RECIPE_TARGET_ENTITY,
                ): str,
                vol.Optional(
                    CONF_GRAVITY_ENTITY,
                    default=DEFAULT_GRAVITY_ENTITY,
                ): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors={},
        )
