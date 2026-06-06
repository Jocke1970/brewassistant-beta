"""Compatibility wrapper for Brewday Runtime normalization.

The public functions in this module are imported by Brewday Runtime sensors.
The actual Brewfather resolver lives in brewday_runtime_core.py. Manual Brewday
can now be routed through its Python engine adapter without changing the sensor
platform.
"""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .brewday_runtime_core import build_core_snapshot, core_attrs, source
from .manual_brewday_adapter import build_manual_engine_snapshot
from .manual_brewday_runtime import ManualRuntimeState
from .manual_brewday_store import get_manual_brewday_session


MANUAL_RUNTIME_ACTIVE_STATES = {
    ManualRuntimeState.PREPARED,
    ManualRuntimeState.RUNNING,
    ManualRuntimeState.PAUSED,
    ManualRuntimeState.AWAITING_CONFIRM,
    ManualRuntimeState.COMPLETED,
}


def _manual_engine_is_active(hass: HomeAssistant) -> bool:
    """Return true when the Python-owned manual runtime session is active."""
    session = get_manual_brewday_session(hass)
    return session.state in MANUAL_RUNTIME_ACTIVE_STATES


def build_brewday_runtime_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    """Build a normalized brewday runtime snapshot."""
    if _manual_engine_is_active(hass):
        return build_manual_engine_snapshot(hass)
    if source(hass) == "Manual Brewday":
        return build_manual_engine_snapshot(hass)
    return build_core_snapshot(hass)


def brewday_runtime_attrs(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Return common runtime attributes for Brewday Runtime sensors."""
    return core_attrs(snapshot)
