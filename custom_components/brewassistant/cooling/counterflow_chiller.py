"""Counter Flow Chiller runtime helpers."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

BREWZILLA_PUMP_SWITCH = "switch.brewzilla_pump"
BREWZILLA_PUMP_UTILIZATION = "number.brewzilla_pump_utilization"

DOMAIN_DATA_KEY = "counterflow_chiller"
DEFAULT_SANITIZE_MINUTES = 15
DEFAULT_PUMP_UTILIZATION = 100
MIN_SANITIZE_MINUTES = 10
MAX_SANITIZE_MINUTES = 25
MIN_PUMP_UTILIZATION = 0
MAX_PUMP_UTILIZATION = 100


def _store(hass: HomeAssistant) -> dict[str, Any]:
    root = hass.data.setdefault("brewassistant", {})
    store = root.setdefault(
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
    return store


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
        store.get("sanitize_minutes"),
        DEFAULT_SANITIZE_MINUTES,
        MIN_SANITIZE_MINUTES,
        MAX_SANITIZE_MINUTES,
    )
    pump_utilization = _clamp_float(
        store.get("pump_utilization"),
        DEFAULT_PUMP_UTILIZATION,
        MIN_PUMP_UTILIZATION,
        MAX_PUMP_UTILIZATION,
    )
    ready = bool(store.get("ready", False))
    status = "ready" if ready else "enabled" if enabled else "disabled"
    return {
        "source": "counterflow_chiller_backend",
        "status": status,
        "enabled": enabled,
        "sanitize_minutes": round(sanitize_minutes),
        "sanitize_seconds": round(sanitize_minutes * 60),
        "pump_utilization": round(pump_utilization),
        "ready": ready,
        "ready_at": store.get("ready_at"),
        "last_action": store.get("last_action"),
        "pump_entity": BREWZILLA_PUMP_SWITCH,
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
        store["sanitize_minutes"] = round(_clamp_float(
            data.get("sanitize_minutes"),
            DEFAULT_SANITIZE_MINUTES,
            MIN_SANITIZE_MINUTES,
            MAX_SANITIZE_MINUTES,
        ))
    if "pump_utilization" in data:
        store["pump_utilization"] = round(_clamp_float(
            data.get("pump_utilization"),
            DEFAULT_PUMP_UTILIZATION,
            MIN_PUMP_UTILIZATION,
            MAX_PUMP_UTILIZATION,
        ))
    store["last_action"] = "configured"
    return get_counterflow_chiller_snapshot(hass)


async def async_counterflow_chiller_ready(hass: HomeAssistant) -> dict[str, Any]:
    store = _store(hass)
    store["enabled"] = True
    pump_utilization = _clamp_float(
        store.get("pump_utilization"),
        DEFAULT_PUMP_UTILIZATION,
        MIN_PUMP_UTILIZATION,
        MAX_PUMP_UTILIZATION,
    )
    actions: list[str] = []
    if hass.states.get(BREWZILLA_PUMP_UTILIZATION) is not None:
        await hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": BREWZILLA_PUMP_UTILIZATION, "value": pump_utilization},
            blocking=True,
        )
        actions.append(f"set:{BREWZILLA_PUMP_UTILIZATION}:{round(pump_utilization)}")
    if hass.states.get(BREWZILLA_PUMP_SWITCH) is not None:
        await hass.services.async_call(
            "switch",
            "turn_on",
            {"entity_id": BREWZILLA_PUMP_SWITCH},
            blocking=True,
        )
        actions.append(f"turn_on:{BREWZILLA_PUMP_SWITCH}")
    store["ready"] = True
    store["ready_at"] = dt_util.utcnow().isoformat()
    store["last_action"] = "cfc_ready"
    result = {**get_counterflow_chiller_snapshot(hass), "actions": actions}
    hass.data.setdefault("brewassistant", {})["counterflow_chiller_last_ready"] = result
    return result


async def async_reset_counterflow_chiller(hass: HomeAssistant) -> dict[str, Any]:
    store = _store(hass)
    store["ready"] = False
    store["ready_at"] = None
    store["last_action"] = "reset"
    return get_counterflow_chiller_snapshot(hass)
