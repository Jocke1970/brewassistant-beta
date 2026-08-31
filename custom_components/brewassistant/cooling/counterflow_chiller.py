"""Counter Flow Chiller compatibility helpers.

Cooling Runtime v2 owns the cooling lifecycle. This module remains as a
compatibility adapter for existing CFC switch/number/button entities.

Important architecture boundary: BrewAssistant Cooling must never start,
stop or regulate the BrewZilla wort pump. Pump state is operator-owned and
read-only from this backend.
"""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .cooling_runtime import update_cooling_runtime_settings

BREWZILLA_PUMP_SWITCH = "switch.brewzilla_pump"
BREWZILLA_PUMP_UTILIZATION = "number.brewzilla_pump_utilization"

DOMAIN_DATA_KEY = "counterflow_chiller"
DEFAULT_SANITIZE_MINUTES = 15
DEFAULT_PUMP_UTILIZATION = 100  # legacy readback only; no longer applied
MIN_SANITIZE_MINUTES = 10
MAX_SANITIZE_MINUTES = 25
MIN_PUMP_UTILIZATION = 0
MAX_PUMP_UTILIZATION = 100


def _store(hass: HomeAssistant) -> dict[str, Any]:
    root = hass.data.setdefault("brewassistant", {})
    return root.setdefault(
        DOMAIN_DATA_KEY,
        {
            "enabled": False,
            "sanitize_minutes": DEFAULT_SANITIZE_MINUTES,
            "pump_utilization": DEFAULT_PUMP_UTILIZATION,
            "ready": False,
            "ready_at": None,
            "last_action": None,
        },
    )


def _clamp_float(value: Any, default: float, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default
    return max(minimum, min(maximum, number))


def get_counterflow_chiller_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    store = _store(hass)
    enabled = bool(store.get("enabled", False))
    sanitize_minutes = _clamp_float(
        store.get("sanitize_minutes"), DEFAULT_SANITIZE_MINUTES, MIN_SANITIZE_MINUTES, MAX_SANITIZE_MINUTES
    )
    pump_utilization = _clamp_float(
        store.get("pump_utilization"), DEFAULT_PUMP_UTILIZATION, MIN_PUMP_UTILIZATION, MAX_PUMP_UTILIZATION
    )
    ready = bool(store.get("ready", False))
    pump_state_obj = hass.states.get(BREWZILLA_PUMP_SWITCH)
    pump_state = pump_state_obj.state if pump_state_obj is not None else "unknown"
    status = "ready" if ready else "enabled" if enabled else "disabled"
    return {
        "source": "counterflow_chiller_compatibility_backend",
        "status": status,
        "enabled": enabled,
        "sanitize_minutes": round(sanitize_minutes),
        "sanitize_seconds": round(sanitize_minutes * 60),
        "pump_utilization": round(pump_utilization),
        "pump_utilization_legacy_only": True,
        "ready": ready,
        "ready_at": store.get("ready_at"),
        "last_action": store.get("last_action"),
        "pump_entity": BREWZILLA_PUMP_SWITCH,
        "pump_state": pump_state,
        "pump_operator_owned": True,
        "pump_write_allowed": False,
        "pump_utilization_entity": BREWZILLA_PUMP_UTILIZATION,
    }


async def async_set_counterflow_chiller(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    store = _store(hass)
    if "enabled" in data:
        store["enabled"] = bool(data.get("enabled"))
        if not store["enabled"]:
            store["ready"] = False
            store["ready_at"] = None
    if "sanitize_minutes" in data:
        store["sanitize_minutes"] = round(
            _clamp_float(data.get("sanitize_minutes"), DEFAULT_SANITIZE_MINUTES, MIN_SANITIZE_MINUTES, MAX_SANITIZE_MINUTES)
        )
        update_cooling_runtime_settings(hass, {"sanitize_minutes": store["sanitize_minutes"]})
    if "pump_utilization" in data:
        # Retained only so restored legacy entities do not crash. It is never
        # written to BrewZilla by Cooling Runtime v2.
        store["pump_utilization"] = round(
            _clamp_float(data.get("pump_utilization"), DEFAULT_PUMP_UTILIZATION, MIN_PUMP_UTILIZATION, MAX_PUMP_UTILIZATION)
        )
    store["last_action"] = "configured"
    return get_counterflow_chiller_snapshot(hass)


async def async_counterflow_chiller_ready(hass: HomeAssistant) -> dict[str, Any]:
    """Mark the CFC ready without touching the operator-owned wort pump."""
    store = _store(hass)
    store["enabled"] = True
    store["ready"] = True
    store["ready_at"] = dt_util.utcnow().isoformat()
    store["last_action"] = "cfc_ready_advisory_only"
    result = {
        **get_counterflow_chiller_snapshot(hass),
        "actions": [],
        "operator_action": "Start/stop BrewZilla wort circulation manually as required.",
    }
    hass.data.setdefault("brewassistant", {})["counterflow_chiller_last_ready"] = result
    return result


async def async_reset_counterflow_chiller(hass: HomeAssistant) -> dict[str, Any]:
    store = _store(hass)
    store["ready"] = False
    store["ready_at"] = None
    store["last_action"] = "reset"
    return get_counterflow_chiller_snapshot(hass)
