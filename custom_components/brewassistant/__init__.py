"""BrewAssistant custom integration.

v0.1 is intentionally read-only. It exposes normalized brewing state from
existing Home Assistant entities so dashboards can start moving away from
heavy YAML/Jinja templates without changing the current package workflow.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS
from .coordinator import BrewAssistantCoordinator


def _platforms() -> list[Platform]:
    """Return supported platforms as Home Assistant Platform enums."""
    return [Platform(platform) for platform in PLATFORMS]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up BrewAssistant from a config entry."""
    coordinator = BrewAssistantCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, _platforms())
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload BrewAssistant config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, _platforms())

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
