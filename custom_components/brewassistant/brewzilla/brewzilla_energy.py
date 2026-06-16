"""BrewZilla energy tracking helpers.

This module integrates the BrewZilla power sensor over time and exposes a simple
session-style energy counter. It is intentionally local and advisory; it does not
replace a utility-meter integration or a hardware energy meter.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant, State
from homeassistant.util import dt as dt_util

DATA_KEY = "brewzilla_energy"

BREWZILLA_POWER_SENSOR = "sensor.brewzilla_power"
NORDPOOL_PRICE_SENSOR = "sensor.nordpool_kwh_se3_sek_3_10_025"
BREWDAY_RUNTIME_STATE_SENSOR = "sensor.brewassistant_brewday_runtime_state"
BREWDAY_RUNTIME_STAGE_SENSOR = "sensor.brewassistant_brewday_runtime_stage"
BREWDAY_RUNTIME_STEP_SENSOR = "sensor.brewassistant_brewday_runtime_step"

_BAD = {None, "unknown", "unavailable", "none", ""}
_ACTIVE_STATES = {"live", "running", "paused", "awaiting_snapshot"}


def _state_obj(hass: HomeAssistant, entity_id: str) -> State | None:
    state = hass.states.get(entity_id)
    if state is None or state.state in _BAD:
        return None
    return state


def _state(hass: HomeAssistant, entity_id: str, default: str | None = None) -> str | None:
    state = _state_obj(hass, entity_id)
    return state.state if state is not None else default


def _float_state(hass: HomeAssistant, entity_id: str) -> float | None:
    raw = _state(hass, entity_id)
    try:
        if raw is None or str(raw).lower() in _BAD:
            return None
        return float(raw)
    except (TypeError, ValueError):
        return None


def _energy_store(hass: HomeAssistant) -> dict[str, Any]:
    return hass.data.setdefault("brewassistant", {}).setdefault(
        DATA_KEY,
        {
            "energy_kwh": 0.0,
            "cost_sek": 0.0,
            "last_power_w": None,
            "last_price_sek_per_kwh": None,
            "last_power_at": None,
            "started_at": None,
            "updated_at": None,
            "sample_count": 0,
        },
    )


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return dt_util.as_utc(value)
    parsed = dt_util.parse_datetime(str(value))
    return dt_util.as_utc(parsed) if parsed is not None else None


def _runtime_active(hass: HomeAssistant) -> bool:
    state = str(_state(hass, BREWDAY_RUNTIME_STATE_SENSOR, "idle") or "idle").lower()
    return state in _ACTIVE_STATES


def _update_energy_from_power(hass: HomeAssistant) -> dict[str, Any]:
    """Integrate energy and cost from power and Nordpool price sensor changes."""
    store = _energy_store(hass)
    power_state = _state_obj(hass, BREWZILLA_POWER_SENSOR)
    power_w = _float_state(hass, BREWZILLA_POWER_SENSOR)
    price_sek_per_kwh = _float_state(hass, NORDPOOL_PRICE_SENSOR)
    now = dt_util.utcnow()

    if power_state is None or power_w is None:
        return {
            "energy_kwh": round(float(store.get("energy_kwh") or 0.0), 4),
            "energy_wh": round(float(store.get("energy_kwh") or 0.0) * 1000.0, 1),
            "cost_sek": round(float(store.get("cost_sek") or 0.0), 2),
            "price_sek_per_kwh": price_sek_per_kwh,
            "power_w": None,
            "tracking_active": False,
            "reason": "BrewZilla power sensor unavailable",
        }

    observed_at = dt_util.as_utc(power_state.last_updated)
    observed_at_iso = observed_at.isoformat()
    last_power_at = _parse_dt(store.get("last_power_at"))
    last_power_w = store.get("last_power_w")
    last_price = store.get("last_price_sek_per_kwh")
    energy_kwh = float(store.get("energy_kwh") or 0.0)
    cost_sek = float(store.get("cost_sek") or 0.0)

    if store.get("started_at") is None:
        store["started_at"] = now.isoformat()

    if store.get("last_power_at") != observed_at_iso:
        if last_power_at is not None and last_power_w is not None:
            seconds = max(0.0, min(3600.0, (observed_at - last_power_at).total_seconds()))
            avg_power_w = (float(last_power_w) + float(power_w)) / 2.0
            delta_kwh = (avg_power_w * seconds) / 3_600_000.0
            energy_kwh += delta_kwh
            if last_price is not None:
                cost_sek += delta_kwh * float(last_price)
            elif price_sek_per_kwh is not None:
                cost_sek += delta_kwh * float(price_sek_per_kwh)
            store["energy_kwh"] = energy_kwh
            store["cost_sek"] = cost_sek
            store["sample_count"] = int(store.get("sample_count") or 0) + 1
        store["last_power_w"] = power_w
        store["last_price_sek_per_kwh"] = price_sek_per_kwh
        store["last_power_at"] = observed_at_iso
        store["updated_at"] = now.isoformat()

    current_estimated_cost_sek = None
    if price_sek_per_kwh is not None:
        current_estimated_cost_sek = float(store.get("energy_kwh") or 0.0) * float(price_sek_per_kwh)

    return {
        "energy_kwh": round(float(store.get("energy_kwh") or 0.0), 4),
        "energy_wh": round(float(store.get("energy_kwh") or 0.0) * 1000.0, 1),
        "cost_sek": round(float(store.get("cost_sek") or 0.0), 2),
        "current_price_cost_estimate_sek": round(current_estimated_cost_sek, 2) if current_estimated_cost_sek is not None else None,
        "price_sek_per_kwh": price_sek_per_kwh,
        "power_w": power_w,
        "tracking_active": _runtime_active(hass) or power_w > 1.0,
        "started_at": store.get("started_at"),
        "updated_at": store.get("updated_at"),
        "last_power_w": store.get("last_power_w"),
        "last_price_sek_per_kwh": store.get("last_price_sek_per_kwh"),
        "last_power_at": store.get("last_power_at"),
        "sample_count": store.get("sample_count"),
        "runtime_state": _state(hass, BREWDAY_RUNTIME_STATE_SENSOR, "idle"),
        "runtime_stage": _state(hass, BREWDAY_RUNTIME_STAGE_SENSOR, "Idle"),
        "runtime_step": _state(hass, BREWDAY_RUNTIME_STEP_SENSOR, "Idle"),
        "source_entity": BREWZILLA_POWER_SENSOR,
        "price_source_entity": NORDPOOL_PRICE_SENSOR,
        "integration_method": "trapezoid_by_power_sensor_last_updated",
        "cost_method": "delta_kwh_times_last_known_nordpool_price",
        "note": "Session-style local estimate. Reset on HA restart unless later persisted/reset services are added.",
    }


def build_brewzilla_energy_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    """Return BrewZilla energy snapshot."""
    return _update_energy_from_power(hass)
