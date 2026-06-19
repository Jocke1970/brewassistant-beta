"""Guarded Brewday Runtime source refresh helper."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .brewday_refresh_policy import (
    build_refresh_policy_snapshot,
    mark_refresh_performed,
    mark_refresh_skipped,
)
from .brewday_runtime_core import (
    BF_NEXT,
    BF_PROGRESS,
    BF_RAW,
    BF_REMAINING,
    BF_STAGE,
    BF_STATUS,
    BF_STEP,
    EntityRef,
    resolved_entity_id,
)

MANUAL_COOLDOWN_SECONDS = 60

BREWFATHER_TRACKER_ENTITIES: list[EntityRef] = [
    BF_STATUS,
    BF_STAGE,
    BF_STEP,
    BF_NEXT,
    BF_PROGRESS,
    BF_REMAINING,
    BF_RAW,
]


def _state_store(hass: HomeAssistant) -> dict[str, Any]:
    """Return integration-local refresh state storage."""
    return hass.data.setdefault("brewassistant_brewday_refresh", {})


async def _update_brewfather_tracker_entities(hass: HomeAssistant) -> None:
    """Ask Home Assistant to refresh resolved Brewfather tracker entities.

    BrewTracker entity refs can be tuples of naming candidates. Home Assistant's
    update_entity service only accepts concrete entity_id strings, not tuples.
    """
    entity_ids: list[str] = []
    for ref in BREWFATHER_TRACKER_ENTITIES:
        entity_id = resolved_entity_id(hass, ref)
        if entity_id not in entity_ids:
            entity_ids.append(entity_id)

    await hass.services.async_call(
        "homeassistant",
        "update_entity",
        {"entity_id": entity_ids},
        blocking=False,
    )


async def maybe_request_brewfather_refresh(hass: HomeAssistant) -> dict[str, Any]:
    """Refresh Brewfather tracker entities when the policy says it is useful."""
    policy = build_refresh_policy_snapshot(hass)

    if not policy.get("due"):
        mark_refresh_skipped(hass, reason=str(policy.get("reason") or "not_due"))
        return {**policy, "refreshed": False}

    reason = str(policy.get("reason") or "policy_due")
    mark_refresh_performed(hass, reason=reason)
    await _update_brewfather_tracker_entities(hass)
    return {**policy, "refreshed": True}


async def request_manual_brewfather_refresh(hass: HomeAssistant) -> dict[str, Any]:
    """Manually refresh Brewfather tracker entities with a short cooldown."""
    store = _state_store(hass)
    now = dt_util.utcnow().timestamp()
    last_manual_refresh_ts = store.get("last_manual_refresh_ts")

    if last_manual_refresh_ts is not None:
        elapsed = now - float(last_manual_refresh_ts)
        if elapsed < MANUAL_COOLDOWN_SECONDS:
            return {
                "refreshed": False,
                "reason": "cooldown",
                "cooldown_remaining_seconds": int(MANUAL_COOLDOWN_SECONDS - elapsed),
                "policy": build_refresh_policy_snapshot(hass),
            }

    store["last_manual_refresh_ts"] = now
    mark_refresh_performed(hass, reason="manual")
    await _update_brewfather_tracker_entities(hass)
    return {
        "refreshed": True,
        "reason": "manual",
        "cooldown_remaining_seconds": MANUAL_COOLDOWN_SECONDS,
        "policy": build_refresh_policy_snapshot(hass),
    }
