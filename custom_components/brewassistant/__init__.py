"""BrewAssistant custom integration.

BrewAssistant Python Core exposes normalized brewing state from existing Home
Assistant entities so dashboards can move away from heavy YAML/Jinja templates
without changing the current package workflow.
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall

from .brewday_refresh import request_manual_brewfather_refresh
from .brewzilla_orchestration import async_apply_brewzilla_target_if_allowed
from .const import DOMAIN, PLATFORMS
from .coordinator import BrewAssistantCoordinator
from .manual_brewday_store import get_manual_brewday_session, new_manual_brewday_session

_LOGGER = logging.getLogger(__name__)
SERVICE_FORCE_BREWFATHER_REFRESH = "force_brewfather_refresh"
SERVICE_APPLY_BREWZILLA_TARGET = "apply_brewzilla_target"
SERVICE_MANUAL_PREPARE = "manual_brewday_prepare"
SERVICE_MANUAL_START = "manual_brewday_start"
SERVICE_MANUAL_PAUSE = "manual_brewday_pause"
SERVICE_MANUAL_NEXT = "manual_brewday_next"
SERVICE_MANUAL_FINISH = "manual_brewday_finish"
SERVICE_MANUAL_RESET = "manual_brewday_reset"

MANUAL_ACTIVE = "input_boolean.brewassistant_brewday_manual_active"
MANUAL_STATUS = "input_select.brewassistant_brewday_manual_status"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up BrewAssistant from a config entry."""
    coordinator = BrewAssistantCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    _register_services(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


def _register_services(hass: HomeAssistant) -> None:
    """Register BrewAssistant services."""
    if hass.services.has_service(DOMAIN, SERVICE_FORCE_BREWFATHER_REFRESH):
        return

    async def _set_manual_helper_status(status: str, active: bool = True) -> None:
        """Keep legacy manual helpers aligned while dashboard migrates to services."""
        await hass.services.async_call(
            "input_boolean",
            "turn_on" if active else "turn_off",
            {"entity_id": MANUAL_ACTIVE},
            blocking=False,
        )
        await hass.services.async_call(
            "input_select",
            "select_option",
            {"entity_id": MANUAL_STATUS, "option": status},
            blocking=False,
        )

    async def _refresh_runtime_sensors() -> None:
        await hass.services.async_call(
            "homeassistant",
            "update_entity",
            {"entity_id": [
                "sensor.brewassistant_brewday_runtime_summary",
                "sensor.brewassistant_brewday_runtime_state",
                "sensor.brewassistant_brewday_runtime_step",
                "sensor.brewassistant_brewday_runtime_next_step",
                "sensor.brewassistant_brewday_live_time_remaining_minutes",
                "sensor.brewassistant_brewzilla_orchestration_mode",
                "sensor.brewassistant_brewzilla_control_reason",
                "sensor.brewassistant_brewzilla_requested_target",
                "sensor.brewassistant_brewzilla_applied_target",
                "sensor.brewassistant_brewzilla_target_delta",
            ]},
            blocking=False,
        )

    async def _handle_force_brewfather_refresh(call: ServiceCall) -> None:
        result = await request_manual_brewfather_refresh(hass)
        if result.get("refreshed"):
            _LOGGER.info("Manual Brewfather Brew Tracker refresh requested")
        else:
            _LOGGER.info(
                "Manual Brewfather Brew Tracker refresh skipped: %s (%s s remaining)",
                result.get("reason"),
                result.get("cooldown_remaining_seconds"),
            )

    async def _handle_apply_brewzilla_target(call: ServiceCall) -> None:
        result = await async_apply_brewzilla_target_if_allowed(hass)
        await _refresh_runtime_sensors()
        if result.get("applied"):
            _LOGGER.info(
                "BrewZilla target applied: %s °C",
                result.get("requested_target"),
            )
        else:
            _LOGGER.info(
                "BrewZilla target apply skipped: %s (%s)",
                result.get("apply_result"),
                result.get("control_reason"),
            )

    async def _handle_manual_prepare(call: ServiceCall) -> None:
        session = get_manual_brewday_session(hass)
        session.prepare()
        await _set_manual_helper_status("prepared", True)
        await _refresh_runtime_sensors()

    async def _handle_manual_start(call: ServiceCall) -> None:
        session = get_manual_brewday_session(hass)
        session.start()
        await _set_manual_helper_status("running", True)
        await _refresh_runtime_sensors()

    async def _handle_manual_pause(call: ServiceCall) -> None:
        session = get_manual_brewday_session(hass)
        session.pause()
        await _set_manual_helper_status("paused", True)
        await _refresh_runtime_sensors()

    async def _handle_manual_next(call: ServiceCall) -> None:
        session = get_manual_brewday_session(hass)
        session.next()
        await _set_manual_helper_status(session.state.value, session.state.value != "idle")
        await _refresh_runtime_sensors()

    async def _handle_manual_finish(call: ServiceCall) -> None:
        session = get_manual_brewday_session(hass)
        session.finish()
        await _set_manual_helper_status("completed", True)
        await _refresh_runtime_sensors()

    async def _handle_manual_reset(call: ServiceCall) -> None:
        new_manual_brewday_session(hass)
        await _set_manual_helper_status("inactive", False)
        await _refresh_runtime_sensors()

    hass.services.async_register(DOMAIN, SERVICE_FORCE_BREWFATHER_REFRESH, _handle_force_brewfather_refresh)
    hass.services.async_register(DOMAIN, SERVICE_APPLY_BREWZILLA_TARGET, _handle_apply_brewzilla_target)
    hass.services.async_register(DOMAIN, SERVICE_MANUAL_PREPARE, _handle_manual_prepare)
    hass.services.async_register(DOMAIN, SERVICE_MANUAL_START, _handle_manual_start)
    hass.services.async_register(DOMAIN, SERVICE_MANUAL_PAUSE, _handle_manual_pause)
    hass.services.async_register(DOMAIN, SERVICE_MANUAL_NEXT, _handle_manual_next)
    hass.services.async_register(DOMAIN, SERVICE_MANUAL_FINISH, _handle_manual_finish)
    hass.services.async_register(DOMAIN, SERVICE_MANUAL_RESET, _handle_manual_reset)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload BrewAssistant config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
