"""Manual Brewday session helper."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .manual_brewday_runtime import ManualRuntimeSession

KEY = "manual_brewday_session"


def get_manual_brewday_session(hass: HomeAssistant) -> ManualRuntimeSession:
    """Return the persistent Manual Brewday session."""
    data = hass.data.setdefault(DOMAIN, {})
    session = data.get(KEY)
    if not isinstance(session, ManualRuntimeSession):
        session = ManualRuntimeSession()
        data[KEY] = session
    return session


def new_manual_brewday_session(hass: HomeAssistant) -> ManualRuntimeSession:
    """Replace and return the Manual Brewday session."""
    session = ManualRuntimeSession()
    hass.data.setdefault(DOMAIN, {})[KEY] = session
    return session
