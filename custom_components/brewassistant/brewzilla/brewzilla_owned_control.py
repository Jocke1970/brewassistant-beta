"""BrewAssistant-owned BrewZilla desired control state.

This module stores operator-confirmed Brewday Advice settings in memory so other
BrewZilla backend modules can distinguish BA-owned desired values from one-off
number writes. The store is intentionally small and volatile; Home Assistant
restart clears ownership and forces the operator/backend to confirm again.
"""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

DATA_KEY = "brewzilla_owned_control"
SOURCE_BREWDAY_ADVICE = "brewday_advice"

BREWZILLA_HEAT_UTILIZATION = "number.brewzilla_heat_utilization"
BREWZILLA_PUMP_UTILIZATION = "number.brewzilla_pump_utilization"


def _store(hass: HomeAssistant) -> dict[str, Any]:
    return hass.data.setdefault("brewassistant", {}).setdefault(
        DATA_KEY,
        {
            "active": False,
            "source": None,
            "created_at": None,
            "updated_at": None,
            "cleared_at": None,
            "clear_reason": None,
            "desired_heat_utilization": None,
            "desired_pump_utilization": None,
            "recommendation_id": None,
        },
    )


def _float(value: Any) -> float | None:
    try:
        if value is None or str(value).lower() in {"unknown", "unavailable", "none", ""}:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def get_owned_control(hass: HomeAssistant) -> dict[str, Any]:
    """Return a copy of the current BA-owned BrewZilla control store."""
    return dict(_store(hass))


def clear_owned_control(hass: HomeAssistant, *, reason: str) -> dict[str, Any]:
    """Clear BA-owned BrewZilla desired state."""
    store = _store(hass)
    store.update(
        {
            "active": False,
            "updated_at": dt_util.utcnow().isoformat(),
            "cleared_at": dt_util.utcnow().isoformat(),
            "clear_reason": reason,
            "desired_heat_utilization": None,
            "desired_pump_utilization": None,
            "recommendation_id": None,
        }
    )
    return dict(store)


def remember_owned_control_from_apply_result(
    hass: HomeAssistant,
    apply_result: dict[str, Any],
) -> dict[str, Any]:
    """Store BA-owned desired utilization after a successful Brewday Advice APPLY."""
    store = _store(hass)
    if not apply_result.get("applied"):
        return dict(store)

    entity_id = str(apply_result.get("applied_entity") or "")
    value = _float(apply_result.get("applied_value"))
    if value is None:
        return dict(store)

    pending = apply_result.get("pending_recommendation")
    pending = pending if isinstance(pending, dict) else {}
    kind = str(pending.get("kind") or "")

    if entity_id == BREWZILLA_HEAT_UTILIZATION or kind == "heat_utilization":
        desired_key = "desired_heat_utilization"
    elif entity_id == BREWZILLA_PUMP_UTILIZATION or kind == "pump_utilization":
        desired_key = "desired_pump_utilization"
    else:
        return dict(store)

    now = dt_util.utcnow().isoformat()
    if not store.get("created_at") or not store.get("active"):
        store["created_at"] = now

    store.update(
        {
            "active": True,
            "source": SOURCE_BREWDAY_ADVICE,
            "updated_at": now,
            "cleared_at": None,
            "clear_reason": None,
            desired_key: value,
            "recommendation_id": pending.get("recommendation_id") or apply_result.get("recommendation_id"),
        }
    )
    return dict(store)
