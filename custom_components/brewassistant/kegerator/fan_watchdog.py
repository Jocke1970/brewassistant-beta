"""Watchdog loop for BrewAssistant kegerator fan auto control."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from ..const import DOMAIN
from .fan_control import async_apply_kegerator_fan_auto, kegerator_fan_auto_interval

DATA_KEY = "kegerator_fan_auto_watchdog"
FAN_AUTO_SWITCH = "switch.brewassistant_kegerator_fan_auto_enabled"


def _bucket(hass: HomeAssistant) -> dict[str, Any]:
    return hass.data.setdefault(DOMAIN, {}).setdefault(DATA_KEY, {})


def _fan_auto_enabled(hass: HomeAssistant) -> bool:
    return hass.states.is_state(FAN_AUTO_SWITCH, "on")


async def async_setup_kegerator_fan_auto_watchdog(hass: HomeAssistant) -> None:
    """Install an always-on watchdog that applies fan-auto when enabled."""
    data = _bucket(hass)
    if data.get("unsub") is not None:
        return

    async def _apply_once() -> None:
        data["last_check_at"] = dt_util.utcnow().isoformat()
        data["enabled"] = _fan_auto_enabled(hass)
        if not data["enabled"]:
            data["last_result"] = "disabled"
            return

        result = await async_apply_kegerator_fan_auto(hass)
        data["last_result"] = result.get("fan_action", "unknown")
        data["last_reason"] = result.get("fan_reason")
        data["last_status"] = result.get("status")
        data["last_fan_state"] = result.get("fan_state")
        data["last_action_needed"] = result.get("fan_action_needed")

    def _tick(now: datetime) -> None:
        hass.async_create_task(_apply_once())

    data["unsub"] = async_track_time_interval(
        hass,
        _tick,
        kegerator_fan_auto_interval() or timedelta(seconds=30),
    )
    data["installed_at"] = dt_util.utcnow().isoformat()
    await _apply_once()


def build_kegerator_fan_auto_watchdog_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    """Return watchdog diagnostics."""
    data = _bucket(hass)
    return {
        "source": "python_kegerator_fan_auto_watchdog",
        "watchdog_active": data.get("unsub") is not None,
        "watchdog_switch_entity": FAN_AUTO_SWITCH,
        "watchdog_enabled": _fan_auto_enabled(hass),
        "installed_at": data.get("installed_at"),
        "last_check_at": data.get("last_check_at"),
        "last_result": data.get("last_result"),
        "last_reason": data.get("last_reason"),
        "last_status": data.get("last_status"),
        "last_fan_state": data.get("last_fan_state"),
        "last_action_needed": data.get("last_action_needed"),
    }
