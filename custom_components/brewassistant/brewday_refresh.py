"""Guarded Brewday Runtime source refresh helper."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .brewday_runtime_core import BF_REMAINING, BF_STATUS, build_core_snapshot

COOLDOWN_SECONDS = 90
MAX_RETRIES = 3


def _state_store(hass: HomeAssistant) -> dict[str, Any]:
    """Return integration-local refresh state storage."""
    return hass.data.setdefault("brewassistant_brewday_refresh", {})


async def maybe_request_brewfather_refresh(hass: HomeAssistant) -> None:
    """Refresh Brewfather tracker entities when live runtime reaches zero.

    The runtime itself decides when a refresh is useful. This hook only adds
    conservative cooldown and retry protection.
    """
    snapshot = build_core_snapshot(hass)
    store = _state_store(hass)

    if snapshot.get("source") != "Brewfather Brew Tracker":
        store["retry_count"] = 0
        store["last_refresh_ts"] = None
        return

    if snapshot.get("time_remaining_seconds", 0) > 0:
        store["retry_count"] = 0
        return

    if snapshot.get("status") != "running" or not snapshot.get("refresh_recommended"):
        return

    now = dt_util.utcnow().timestamp()
    retry_count = int(store.get("retry_count") or 0)
    last_refresh_ts = store.get("last_refresh_ts")

    if retry_count >= MAX_RETRIES:
        return
    if last_refresh_ts is not None and now - float(last_refresh_ts) < COOLDOWN_SECONDS:
        return

    store["retry_count"] = retry_count + 1
    store["last_refresh_ts"] = now

    await hass.services.async_call(
        "homeassistant",
        "update_entity",
        {"entity_id": [BF_STATUS, BF_REMAINING]},
        blocking=False,
    )
