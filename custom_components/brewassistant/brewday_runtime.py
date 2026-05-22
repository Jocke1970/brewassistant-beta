"""Compatibility wrapper for Brewday Runtime normalization.

The public functions in this module are imported by Brewday Runtime sensors.
The actual resolver lives in brewday_runtime_core.py so the runtime engine can
be evolved without bloating the sensor platform.
"""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .brewday_runtime_core import build_core_snapshot, core_attrs


def build_brewday_runtime_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    """Build a normalized brewday runtime snapshot."""
    return build_core_snapshot(hass)


def brewday_runtime_attrs(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Return common runtime attributes for Brewday Runtime sensors."""
    return core_attrs(snapshot)
