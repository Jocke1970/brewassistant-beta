# Resolve external entity IDs from the BrewAssistant config entry.

from __future__ import annotations

from homeassistant.core import HomeAssistant

from .const import CONF_KEGERATOR_POWER_ENTITY, DOMAIN

INVALID_ENTITY_STATES = {"unknown", "unavailable", "none", ""}


def configured_entity(hass: HomeAssistant, key: str, default: str) -> str:
    """Return a configured entity, with a safe kegerator-power fallback."""
    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        return default

    entry = entries[0]
    configured = str(entry.options.get(key) or entry.data.get(key) or default)

    if key != CONF_KEGERATOR_POWER_ENTITY or configured == default:
        return configured

    state = hass.states.get(configured)
    if state is None or str(state.state).lower() in INVALID_ENTITY_STATES:
        return default

    return configured
