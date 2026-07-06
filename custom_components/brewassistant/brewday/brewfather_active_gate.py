"""Strict Brewfather Brew Tracker active gate.

Brewfather exposes several attributes that can remain truthy after a brewday has
been paused, completed, or left stale.  BrewAssistant should only let Brewfather
own Brewday Runtime when the status sensor itself is exactly ``active``.
"""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from . import brewday_runtime_core as core

_INSTALLED = False


def _strict_brewfather_session_active(hass: HomeAssistant) -> bool:
    """Return true only while the Brewfather Brew Tracker status is active."""
    source_state = core.state(hass, core.BF_STATUS, "inactive")
    return str(source_state or "").strip().lower() == core.BREWDAY_ACTIVE_STATUS


def install_brewfather_active_gate() -> None:
    """Install the strict Brewfather active-state resolver."""
    global _INSTALLED
    if _INSTALLED:
        return
    core.brewfather_session_active = _strict_brewfather_session_active
    _INSTALLED = True
