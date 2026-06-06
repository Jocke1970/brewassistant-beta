"""BrewAssistant custom integration.

BrewAssistant Python Core exposes normalized brewing state from Home Assistant
and Python-owned runtime stores. Legacy YAML/helper sync is intentionally not
maintained in the Python-only branch.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall

from .brewday.brewday_audit import (
    async_clear_brewday_audit_log,
    async_load_brewday_audit_log,
    async_record_brewday_audit_event,
    async_record_brewday_audit_snapshot,
    async_start_brewday_audit_log,
    async_stop_brewday_audit_log,
)
from .brewday.brewday_refresh import request_manual_brewfather_refresh
from .brewzilla.brewzilla_orchestration import async_abort_brewzilla, async_apply_brewzilla_target_if_allowed
from .carbonation_backend.carbonation_runtime import (
    async_load_carbonation_runtime,
    async_save_carbonation_runtime,
    pause_carbonation_runtime,
    reset_carbonation_runtime,
    start_carbonation_runtime,
    update_carbonation_runtime,
)
from .const import DOMAIN, PLATFORMS
from .coordinator import BrewAssistantCoordinator
from .kegerator_guard import async_setup_kegerator_guard
from .brewday.manual_brewday_runtime import ManualRuntimeState
from .brewday.manual_brewday_store import get_manual_brewday_session, new_manual_brewday_session

_LOGGER = logging.getLogger(__name__)
SERVICE_FORCE_BREWFATHER_REFRESH = "force_brewfather_refresh"
SERVICE_APPLY_BREWZILLA_TARGET = "apply_brewzilla_target"
SERVICE_ABORT_BREWZILLA = "abort_brewzilla"
SERVICE_BREWDAY_AUDIT_START = "brewday_audit_start"
SERVICE_BREWDAY_AUDIT_STOP = "brewday_audit_stop"
SERVICE_BREWDAY_AUDIT_CLEAR = "brewday_audit_clear"
SERVICE_BREWDAY_AUDIT_SNAPSHOT = "brewday_audit_snapshot"
SERVICE_MANUAL_PREPARE = "manual_brewday_prepare"
SERVICE_MANUAL_START = "manual_brewday_start"
SERVICE_MANUAL_PAUSE = "manual_brewday_pause"
SERVICE_MANUAL_NEXT = "manual_brewday_next"
SERVICE_MANUAL_START_MASH = "manual_brewday_start_mash"
SERVICE_MANUAL_START_BOIL = "manual_brewday_start_boil"
SERVICE_MANUAL_START_WHIRLPOOL = "manual_brewday_start_whirlpool"
SERVICE_MANUAL_START_COOLING = "manual_brewday_start_cooling"
SERVICE_MANUAL_FINISH = "manual_brewday_finish"
SERVICE_MANUAL_RESET = "manual_brewday_reset"
SERVICE_CARBONATION_START = "carbonation_start"
SERVICE_CARBONATION_UPDATE = "carbonation_update"
SERVICE_CARBONATION_PAUSE = "carbonation_pause"
SERVICE_CARBONATION_RESET = "carbonation_reset"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up BrewAssistant from a config entry."""
    await async_load_brewday_audit_log(hass)
    await async_load_carbonation_runtime(hass)
    await async_setup_kegerator_guard(hass)

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

    async def _refresh_runtime_sensors() -> None:
        await hass.services.async_call(
            "homeassistant",
            "update_entity",
            {"entity_id": [
                "sensor.brewassistant_brewday_runtime_summary",
                "sensor.brewassistant_brewday_runtime_state",
                "sensor.brewassistant_brewday_runtime_stage",
                "sensor.brewassistant_brewday_runtime_step",
                "sensor.brewassistant_brewday_runtime_next_step",
                "sensor.brewassistant_brewday_live_time_remaining_minutes",
                "sensor.brewassistant_brewday_live_progress",
                "sensor.brewassistant_brewday_audit_summary",
                "sensor.brewassistant_brewday_audit_event_count",
                "sensor.brewassistant_brewday_audit_last_event",
                "sensor.brewassistant_brewday_audit_last_step",
                "sensor.brewassistant_brewday_audit_last_target",
                "sensor.brewassistant_brewday_stage",
                "sensor.brewassistant_brewday_stage_reason",
                "sensor.brewassistant_brewday_stage_status_line",
                "sensor.brewassistant_brewday_stage_icon",
                "sensor.brewassistant_brewday_stage_group",
                "sensor.brewassistant_brewday_stage_priority",
                "sensor.brewassistant_brewday_stage_suggested_action",
                "sensor.brewassistant_brewday_stage_control_hint",
                "sensor.brewassistant_wort_cooling_status",
                "sensor.brewassistant_wort_cooling_summary",
                "sensor.brewassistant_wort_cooling_reference_temperature",
                "sensor.brewassistant_wort_cooling_target_temperature",
                "sensor.brewassistant_wort_cooling_delta",
                "sensor.brewassistant_wort_cooling_rate",
                "sensor.brewassistant_wort_cooling_eta_minutes",
                "sensor.brewassistant_wort_pitch_ready",
                "sensor.brewassistant_brewzilla_orchestration_mode",
                "sensor.brewassistant_brewzilla_control_reason",
                "sensor.brewassistant_brewzilla_requested_target",
                "sensor.brewassistant_brewzilla_applied_target",
                "sensor.brewassistant_brewzilla_target_delta",
                "sensor.brewassistant_brewzilla_target_sync_needed",
                "sensor.brewassistant_brewzilla_can_apply_target",
                "sensor.brewassistant_brewzilla_safety_state",
                "sensor.brewassistant_brewzilla_runtime_state",
                "sensor.brewassistant_brewzilla_runtime_summary",
            ]},
            blocking=False,
        )

    async def _refresh_carbonation_sensors() -> None:
        await hass.services.async_call(
            "homeassistant",
            "update_entity",
            {"entity_id": [
                "sensor.brewassistant_carbonation_status",
                "sensor.brewassistant_carbonation_method",
                "sensor.brewassistant_carbonation_target_volumes",
                "sensor.brewassistant_carbonation_temperature",
                "sensor.brewassistant_carbonation_recommended_pressure_bar",
                "sensor.brewassistant_carbonation_recommended_pressure_psi",
                "sensor.brewassistant_carbonation_actual_pressure_bar",
                "sensor.brewassistant_carbonation_actual_pressure_psi",
                "sensor.brewassistant_carbonation_equilibrium_volumes",
                "sensor.brewassistant_carbonation_estimated_volumes",
                "sensor.brewassistant_carbonation_progress_percent",
                "sensor.brewassistant_carbonation_started_at",
                "sensor.brewassistant_carbonation_age_days",
                "sensor.brewassistant_carbonation_summary",
            ]},
            blocking=False,
        )

    def _jump_to_manual_stage(*, keywords: tuple[str, ...], fallback_index: int | None = None) -> None:
        session = get_manual_brewday_session(hass)
        stage_index = None
        for index, stage in enumerate(session.plan.stages):
            stage_name = stage.name.lower()
            if any(keyword in stage_name for keyword in keywords):
                stage_index = index
                break

        if stage_index is None:
            stage_index = fallback_index if fallback_index is not None else 0
        stage_index = max(0, min(stage_index, len(session.plan.stages) - 1))

        session.active_stage_index = stage_index
        session.active_step_index = 0
        session.step_started_at = datetime.now(timezone.utc)
        session.paused_at = None
        session.remaining_when_paused = None
        session.state = ManualRuntimeState.RUNNING

    async def _handle_force_brewfather_refresh(call: ServiceCall) -> None:
        result = await request_manual_brewfather_refresh(hass)
        await async_record_brewday_audit_event(
            hass,
            "manual_brewfather_refresh",
            note=str(result),
            always_record=False,
        )
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
            _LOGGER.info("BrewZilla direct action applied: %s", result.get("apply_result"))
        else:
            _LOGGER.info(
                "BrewZilla direct action skipped: %s (%s)",
                result.get("apply_result"),
                result.get("control_reason"),
            )

    async def _handle_abort_brewzilla(call: ServiceCall) -> None:
        result = await async_abort_brewzilla(hass)
        await async_record_brewday_audit_event(hass, "abort", brewzilla_result=result, always_record=True)
        await _refresh_runtime_sensors()
        _LOGGER.warning("BrewZilla ABORT executed: %s", result.get("actions"))

    async def _handle_brewday_audit_start(call: ServiceCall) -> None:
        await async_start_brewday_audit_log(hass, note=str(call.data.get("note") or ""))
        await _refresh_runtime_sensors()

    async def _handle_brewday_audit_stop(call: ServiceCall) -> None:
        await async_stop_brewday_audit_log(hass, note=str(call.data.get("note") or ""))
        await _refresh_runtime_sensors()

    async def _handle_brewday_audit_clear(call: ServiceCall) -> None:
        await async_clear_brewday_audit_log(hass)
        await _refresh_runtime_sensors()

    async def _handle_brewday_audit_snapshot(call: ServiceCall) -> None:
        await async_record_brewday_audit_snapshot(hass, note=str(call.data.get("note") or ""))
        await _refresh_runtime_sensors()

    async def _handle_manual_prepare(call: ServiceCall) -> None:
        session = get_manual_brewday_session(hass)
        session.prepare()
        await _refresh_runtime_sensors()

    async def _handle_manual_start(call: ServiceCall) -> None:
        session = get_manual_brewday_session(hass)
        session.start()
        await _refresh_runtime_sensors()

    async def _handle_manual_pause(call: ServiceCall) -> None:
        session = get_manual_brewday_session(hass)
        session.pause()
        await _refresh_runtime_sensors()

    async def _handle_manual_next(call: ServiceCall) -> None:
        session = get_manual_brewday_session(hass)
        session.next()
        await _refresh_runtime_sensors()

    async def _handle_manual_start_mash(call: ServiceCall) -> None:
        _jump_to_manual_stage(keywords=("mash", "mäsk"), fallback_index=1)
        await _refresh_runtime_sensors()

    async def _handle_manual_start_boil(call: ServiceCall) -> None:
        _jump_to_manual_stage(keywords=("boil", "kok"), fallback_index=3)
        await _refresh_runtime_sensors()

    async def _handle_manual_start_whirlpool(call: ServiceCall) -> None:
        _jump_to_manual_stage(keywords=("whirlpool", "hop stand", "hopstand"), fallback_index=4)
        await _refresh_runtime_sensors()

    async def _handle_manual_start_cooling(call: ServiceCall) -> None:
        _jump_to_manual_stage(keywords=("chill", "cool", "kyl"), fallback_index=max(0, len(get_manual_brewday_session(hass).plan.stages) - 1))
        await _refresh_runtime_sensors()

    async def _handle_manual_finish(call: ServiceCall) -> None:
        session = get_manual_brewday_session(hass)
        session.finish()
        await _refresh_runtime_sensors()

    async def _handle_manual_reset(call: ServiceCall) -> None:
        new_manual_brewday_session(hass)
        await _refresh_runtime_sensors()

    async def _handle_carbonation_start(call: ServiceCall) -> None:
        start_carbonation_runtime(hass, dict(call.data))
        await async_save_carbonation_runtime(hass)
        await _refresh_carbonation_sensors()

    async def _handle_carbonation_update(call: ServiceCall) -> None:
        update_carbonation_runtime(hass, dict(call.data))
        await async_save_carbonation_runtime(hass)
        await _refresh_carbonation_sensors()

    async def _handle_carbonation_pause(call: ServiceCall) -> None:
        pause_carbonation_runtime(hass)
        await async_save_carbonation_runtime(hass)
        await _refresh_carbonation_sensors()

    async def _handle_carbonation_reset(call: ServiceCall) -> None:
        reset_carbonation_runtime(hass)
        await async_save_carbonation_runtime(hass)
        await _refresh_carbonation_sensors()

    hass.services.async_register(DOMAIN, SERVICE_FORCE_BREWFATHER_REFRESH, _handle_force_brewfather_refresh)
    hass.services.async_register(DOMAIN, SERVICE_APPLY_BREWZILLA_TARGET, _handle_apply_brewzilla_target)
    hass.services.async_register(DOMAIN, SERVICE_ABORT_BREWZILLA, _handle_abort_brewzilla)
    hass.services.async_register(DOMAIN, SERVICE_BREWDAY_AUDIT_START, _handle_brewday_audit_start)
    hass.services.async_register(DOMAIN, SERVICE_BREWDAY_AUDIT_STOP, _handle_brewday_audit_stop)
    hass.services.async_register(DOMAIN, SERVICE_BREWDAY_AUDIT_CLEAR, _handle_brewday_audit_clear)
    hass.services.async_register(DOMAIN, SERVICE_BREWDAY_AUDIT_SNAPSHOT, _handle_brewday_audit_snapshot)
    hass.services.async_register(DOMAIN, SERVICE_MANUAL_PREPARE, _handle_manual_prepare)
    hass.services.async_register(DOMAIN, SERVICE_MANUAL_START, _handle_manual_start)
    hass.services.async_register(DOMAIN, SERVICE_MANUAL_PAUSE, _handle_manual_pause)
    hass.services.async_register(DOMAIN, SERVICE_MANUAL_NEXT, _handle_manual_next)
    hass.services.async_register(DOMAIN, SERVICE_MANUAL_START_MASH, _handle_manual_start_mash)
    hass.services.async_register(DOMAIN, SERVICE_MANUAL_START_BOIL, _handle_manual_start_boil)
    hass.services.async_register(DOMAIN, SERVICE_MANUAL_START_WHIRLPOOL, _handle_manual_start_whirlpool)
    hass.services.async_register(DOMAIN, SERVICE_MANUAL_START_COOLING, _handle_manual_start_cooling)
    hass.services.async_register(DOMAIN, SERVICE_MANUAL_FINISH, _handle_manual_finish)
    hass.services.async_register(DOMAIN, SERVICE_MANUAL_RESET, _handle_manual_reset)
    hass.services.async_register(DOMAIN, SERVICE_CARBONATION_START, _handle_carbonation_start)
    hass.services.async_register(DOMAIN, SERVICE_CARBONATION_UPDATE, _handle_carbonation_update)
    hass.services.async_register(DOMAIN, SERVICE_CARBONATION_PAUSE, _handle_carbonation_pause)
    hass.services.async_register(DOMAIN, SERVICE_CARBONATION_RESET, _handle_carbonation_reset)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload BrewAssistant config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
