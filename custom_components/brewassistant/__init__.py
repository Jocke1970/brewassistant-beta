"""BrewAssistant custom integration.

BrewAssistant Python Core exposes normalized brewing state from existing Home
Assistant entities so dashboards can move away from heavy YAML/Jinja templates
without changing the current package workflow.
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall

from .brewday_refresh import request_manual_brewfather_refresh
from .const import DOMAIN, PLATFORMS
from .coordinator import BrewAssistantCoordinator

_LOGGER = logging.getLogger(__name__)
SERVICE_FORCE_BREWFATHER_REFRESH = "force_brewfather_refresh"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up BrewAssistant from a config entry."""
    coordinator = BrewAssistantCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    _register_services(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


def _register_services(hass: HomeAssistant) -> None:
    """Register BrewAssistant services."""
    if hass.services.has_service(DOMAIN, SERVICE_FORCE_BREWFATHER_REFRESH):
        return

    async def _handle_force_brewfather_refresh(call: ServiceCall) -> None:
        result = await request_manual_brewfather_refresh(hass)
        if result.get("refreshed"):
            _LOGGER.info("Manual Brewfather Brew Tracker refresh requested")
        else:
            _LOGGER.info(
                "Manual Brewfather Brew Tracker refresh skipped: %s (%s s remaining)",
                result.get("reason"),
                result.get("cooldown_remaining_seconds"),
            )

    hass.services.async_register(
        DOMAIN,
        SERVICE_FORCE_BREWFATHER_REFRESH,
        _handle_force_brewfather_refresh,
    )


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload BrewAssistant config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
