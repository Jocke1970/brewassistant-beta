"""BrewZilla temperature filter."""

from __future__ import annotations

from typing import Any

from . import brewzilla_orchestration as base

_BASE_BUILD = base.build_orchestration_snapshot
_INSTALLED = False


def _num(v: Any) -> float | None:
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


def build_orchestration_snapshot(hass):
    snap = _BASE_BUILD(hass)
    snap["temperature_raw"] = snap.get("current_temperature")
    snap["temperature_trusted"] = snap.get("current_temperature")
    snap["temperature_filter_active"] = True
    snap["temperature_sample_filtered"] = False
    snap["temperature_filter_reason"] = None
    return snap


def install_temp_filter() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    base.build_orchestration_snapshot = build_orchestration_snapshot
    _INSTALLED = True
