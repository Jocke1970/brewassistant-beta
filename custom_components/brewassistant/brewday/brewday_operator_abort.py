"""Persistent operator ABORT latch for Brewday hot-side ownership.

A Brewday ABORT is stronger than cancelling one pending Supervised Apply plan.
It represents explicit operator intent that BrewAssistant must stop owning the
hot side until the operator explicitly rearms control.  The latch is persisted
through Home Assistant storage so a restart cannot silently restore ownership.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

DATA_KEY = "brewassistant_brewday_operator_abort"
STORE_KEY = "brewassistant_brewday_operator_abort"
STORAGE_VERSION = 1


def _default_state() -> dict[str, Any]:
    return {
        "active": False,
        "source": "None",
        "stage": "Idle",
        "step": "Idle",
        "aborted_at": None,
        "rearmed_at": None,
        "reason": None,
    }


def _store(hass: HomeAssistant) -> Store:
    return Store(hass, STORAGE_VERSION, STORE_KEY)


def _state(hass: HomeAssistant) -> dict[str, Any]:
    state = hass.data.get(DATA_KEY)
    if isinstance(state, dict):
        return state
    state = _default_state()
    hass.data[DATA_KEY] = state
    return state


async def async_load_brewday_operator_abort(hass: HomeAssistant) -> dict[str, Any]:
    """Load the persisted operator ABORT latch once per HA runtime."""
    existing = hass.data.get(DATA_KEY)
    if isinstance(existing, dict):
        return existing

    stored = await _store(hass).async_load()
    state = _default_state()
    if isinstance(stored, dict):
        for key in state:
            if key in stored:
                state[key] = stored[key]
    hass.data[DATA_KEY] = state
    return state


async def async_latch_brewday_operator_abort(
    hass: HomeAssistant,
    *,
    source: str,
    stage: str,
    step: str,
    reason: str = "operator_abort",
) -> dict[str, Any]:
    """Latch Brewday ownership off until explicit operator rearm."""
    state = await async_load_brewday_operator_abort(hass)
    state.update(
        {
            "active": True,
            "source": str(source or "None"),
            "stage": str(stage or "Idle"),
            "step": str(step or "Idle"),
            "aborted_at": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
        }
    )
    await _store(hass).async_save(dict(state))
    return dict(state)


async def async_clear_brewday_operator_abort(hass: HomeAssistant) -> dict[str, Any]:
    """Explicitly rearm Brewday ownership after an operator ABORT."""
    state = await async_load_brewday_operator_abort(hass)
    state.update(
        {
            "active": False,
            "rearmed_at": datetime.now(timezone.utc).isoformat(),
            "reason": None,
        }
    )
    await _store(hass).async_save(dict(state))
    return dict(state)


def brewday_operator_abort_active(hass: HomeAssistant) -> bool:
    """Return true while operator ABORT blocks Brewday hot-side ownership."""
    return bool(_state(hass).get("active"))


def brewday_operator_abort_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    """Return UI/audit diagnostics for the operator ABORT latch."""
    state = dict(_state(hass))
    state["control_state"] = "aborted" if state.get("active") else "armed"
    return state
