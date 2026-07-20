# Resolve external entity IDs from the BrewAssistant config entry.

from __future__ import annotations

from homeassistant.core import HomeAssistant

from .const import DOMAIN


def configured_entity(hass: HomeAssistant, key: str, default: str) -> str:
    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        return default

    entry = entries[0]
    return str(entry.options.get(key) or entry.data.get(key) or default)
