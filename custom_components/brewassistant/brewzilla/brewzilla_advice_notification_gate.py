"""Gate Brewday Advice persistent notifications."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import brewzilla_learning as _learning

ADVICE_CARD_SWITCH = "switch.brewassistant_show_brewzilla_learning"
MASTER_NOTIFICATIONS_TOGGLE = "input_boolean.brewassistant_notifications_enabled"
_OFF_STATES = {"off", "false", "no", "disabled"}
_ORIGINAL: Callable[[HomeAssistant], Awaitable[dict[str, Any]]] | None = None


def _entity_is_explicitly_off(hass: HomeAssistant, entity_id: str) -> bool:
    """Return true only when an existing entity is explicitly off/disabled."""
    state = hass.states.get(entity_id)
    if state is None:
        return False
    return str(state.state).lower() in _OFF_STATES


def _advice_notifications_disabled(hass: HomeAssistant) -> bool:
    """Return whether Brewday Advice should stay quiet."""
    return _entity_is_explicitly_off(hass, ADVICE_CARD_SWITCH) or _entity_is_explicitly_off(
        hass, MASTER_NOTIFICATIONS_TOGGLE
    )


async def _quiet_result(hass: HomeAssistant) -> dict[str, Any]:
    """Return a quiet result and dismiss any already tracked Advice notification."""
    store = _learning._learning_store(hass)
    if store.get("last_notified_recommendation_id"):
        return await _learning._dismiss_advice_notification(
            hass,
            store,
            reason="disabled_by_backend_gate",
        )

    store["last_notification_result"] = "disabled_by_backend_gate"
    store["last_notification_updated_at"] = dt_util.utcnow().isoformat()
    return {
        "source": "brewzilla_learning",
        "notification_result": "disabled_by_backend_gate",
        "notification_id": _learning.ADVICE_NOTIFICATION_ID,
    }


def install_advice_notification_gate() -> None:
    """Install a gate around Brewday Advice persistent notifications."""
    global _ORIGINAL
    if _ORIGINAL is not None:
        return

    _ORIGINAL = _learning.async_update_brewday_advice_notification

    async def async_update_brewday_advice_notification(hass: HomeAssistant) -> dict[str, Any]:
        if _advice_notifications_disabled(hass):
            return await _quiet_result(hass)
        return await _ORIGINAL(hass)

    _learning.async_update_brewday_advice_notification = async_update_brewday_advice_notification
