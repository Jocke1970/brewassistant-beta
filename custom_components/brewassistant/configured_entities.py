# Resolve external entity IDs and simple options from the BrewAssistant config entry.

from __future__ import annotations

from homeassistant.core import HomeAssistant

from .const import CONF_KEGERATOR_POWER_ENTITY, DOMAIN

INVALID_ENTITY_STATES = {"unknown", "unavailable", "none", ""}
TRUE_VALUES = {"1", "true", "yes", "on", "enabled"}
FALSE_VALUES = {"0", "false", "no", "off", "disabled"}


def _entry_value(hass: HomeAssistant, key: str, default):
    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        return default

    entry = entries[0]
    if key in entry.options:
        return entry.options[key]
    if key in entry.data:
        return entry.data[key]
    return default


def configured_entity(hass: HomeAssistant, key: str, default: str) -> str:
    """Return a configured entity, with a safe kegerator-power fallback."""
    configured = str(_entry_value(hass, key, default) or default)

    if key != CONF_KEGERATOR_POWER_ENTITY or configured == default:
        return configured

    state = hass.states.get(configured)
    if state is None or str(state.state).lower() in INVALID_ENTITY_STATES:
        return default

    return configured


def configured_bool(hass: HomeAssistant, key: str, default: bool) -> bool:
    """Return one boolean config option without truthy-string surprises."""
    raw = _entry_value(hass, key, default)
    if isinstance(raw, bool):
        return raw
    normalized = str(raw).strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    return bool(default)
