"""Read-only carbonation calculations for BrewAssistant.

Compatibility wrapper around the Python-owned carbonation runtime.
"""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .carbonation.carbonation_runtime import build_carbonation_snapshot as build_runtime_snapshot


def build_carbonation_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    """Build a read-only carbonation snapshot."""
    return build_runtime_snapshot(hass)
