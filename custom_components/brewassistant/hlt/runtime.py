"""Brewday-scoped HLT simulation. BZ always takes power priority.

Only reads Home Assistant; never calls a hardware service or caps BrewZilla.
The 30-second sampling interval cannot protect a real shared electrical circuit
against autonomous heater cycles. An independent interlock is required for that.
"""
from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import logging
from math import isfinite
from typing import Any

from homeassistant.core import callback
from homeassistant.helpers.event import async_track_time_interval

from .flight_recorder import async_record_hlt_tick
from .ha_adapter import EntityConfig, collect_inputs
from .simulation import HLTSimulator, SimulationConfig

_LOGGER = logging.getLogger(__name__)
_KEY = "hlt_simulation_runtime"
_INTERVAL = timedelta(seconds=30)
_TERMINAL_STAGE_WORDS = (
    "boil", "kok", "hopstand", "hop stand", "whirlpool", "chill", "cool",
    "kyl", "transfer", "överför", "cleanup", "clean", "rengör", "pre-boil",
)
_INACTIVE = {"idle", "completed", "complete", "finished", "aborted", "error", "stopped"}


def _numeric(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def _option(entry: Any, key: str, default: Any) -> Any:
    return entry.options.get(key, entry.data.get(key, default))


def _config(entry: Any, water_l: float) -> SimulationConfig:
    """Scenario watts are NOT commissioned electrical ratings."""
    cutoff = _option(entry, "hlt_sim_thermostat_cutoff_c", None)
    return SimulationConfig(
        usable_budget_w=float(_option(entry, "hlt_sim_usable_budget_w", 2500)),
        hlt_heater_w=float(_option(entry, "hlt_sim_heater_w", 1800)),
        brewzilla_heater_w=float(_option(entry, "hlt_sim_brewzilla_heater_w", 2200)),
        brewzilla_idle_w=float(_option(entry, "hlt_sim_brewzilla_idle_w", 0)),
        hlt_volume_l=water_l,
        hlt_start_c=float(_option(entry, "hlt_sim_start_c", 18)),
        hlt_target_c=float(_option(entry, "hlt_sim_target_c", 78)),
        thermostat_cutoff_c=float(cutoff) if cutoff is not None else None,
    )


def _entities(entry: Any) -> EntityConfig:
    temperature = _option(entry, "hlt_sim_temperature_entity", None)
    return EntityConfig(
        brewzilla_power=str(_option(entry, "hlt_sim_brewzilla_power_entity", "sensor.brewzilla_power")),
        brewzilla_utilization=str(_option(entry, "hlt_sim_brewzilla_utilization_entity", "number.brewzilla_heat_utilization")),
        hlt_switch=str(_option(entry, "hlt_sim_switch_entity", "switch.sparge_heater")),
        hlt_power=str(_option(entry, "hlt_sim_power_entity", "sensor.sparge_heater_power")),
        hlt_temperature=str(temperature) if temperature else None,
    )


def _observed(hass: Any, entity_id: str, now: datetime, max_age_s: float) -> str | None:
    state = hass.states.get(entity_id)
    if state is None or state.state.lower() in {"unknown", "unavailable", "none", ""}:
        return None
    age = (now - state.last_updated).total_seconds()
    return str(state.state) if 0 <= age <= max_age_s else None


def _allowed_stage(stage: Any) -> bool:
    text = str(stage or "").lower()
    return bool(text) and not any(word in text for word in _TERMINAL_STAGE_WORDS)


def _bz_cruise_observation(hass: Any, brewday: dict[str, Any], now: datetime,
                           age_s: float, tolerance_c: float = 0.5) -> tuple[bool, bool]:
    """Observed cruise only; unavailable evidence is UNKNOWN, not a ramp.

    Require fresh internal temperature and device target, matching normalized
    runtime target. No sample can predict the next autonomous BZ heater cycle.
    """
    actual_c = _numeric(_observed(hass, "sensor.brewzilla_temperature", now, age_s))
    device_c = _numeric(_observed(hass, "number.brewzilla_target_temperature", now, age_s))
    requested_c = _numeric(brewday.get("target_temperature"))
    if any(value is None for value in (actual_c, device_c, requested_c)):
        return False, False
    ramp = abs(device_c - requested_c) > tolerance_c or actual_c < requested_c - tolerance_c
    cruising = not ramp and abs(actual_c - requested_c) <= tolerance_c
    return cruising, ramp


async def async_hlt_simulation_tick(hass: Any, entry: Any, *, now: datetime | None = None) -> dict[str, Any]:
    """Advance virtual HLT and append JSONL; no physical writes, ever."""
    from ..brewday.brewday_audit import get_brewday_audit_log
    from ..brewday.brewday_runtime import build_brewday_runtime_snapshot
    from ..brewzilla.brewzilla_learning import build_brewzilla_learning_snapshot

    data = hass.data.setdefault("brewassistant", {})
    runtime = data.setdefault(_KEY, {})
    audit = get_brewday_audit_log(hass)
    if not audit.active or audit.started_at is None:
        runtime["status"] = "waiting_for_brewday_recorder"
        runtime.pop("simulator", None)
        runtime.pop("session_id", None)
        return runtime

    brewday = build_brewday_runtime_snapshot(hass)
    stage = str(brewday.get("stage") or "")
    status = str(brewday.get("runtime_state") or "").lower()
    if status in _INACTIVE or brewday.get("operator_abort_active"):
        runtime["status"] = "brewday_inactive_or_aborted"
        runtime.pop("simulator", None)
        return runtime

    context = build_brewzilla_learning_snapshot(hass)
    water_l = _numeric(context.get("sparge_water_l"))
    if water_l is None or water_l < 0:
        runtime["status"] = "waiting_for_sparge_volume"
        runtime["sparge_water_l"] = None
        runtime.pop("simulator", None)
        return runtime
    session_id = audit.started_at.isoformat()
    key = (session_id, water_l)
    config = _config(entry, water_l if water_l > 0 else 0.001)
    if runtime.get("session_key") != key or runtime.get("scenario_config") != config or "simulator" not in runtime:
        runtime["simulator"] = HLTSimulator(config)
        runtime["session_key"] = key
        runtime["scenario_config"] = config
        runtime["session_id"] = session_id
        runtime["status"] = "new_simulation_session"

    now = now or datetime.now(timezone.utc)
    entities = _entities(entry)
    cruising, ramp_requested = _bz_cruise_observation(hass, brewday, now, entities.max_age_s)
    sparge_required = water_l > 0
    readings = collect_inputs(
        hass, entities, sparge_required=sparge_required,
        enabled=sparge_required and _allowed_stage(stage),
        brewzilla_unconstrained=True, now=now,
    )
    readings = replace(readings, brewzilla_cruising=cruising,
                       brewzilla_ramp_requested=ramp_requested)
    result = runtime["simulator"].tick(readings)
    power_w = _numeric(_observed(hass, entities.hlt_power, now, entities.max_age_s))
    await async_record_hlt_tick(
        hass, session_id=session_id, inputs=readings, result=result,
        hlt_power_w=power_w,
        hlt_switch=_observed(hass, entities.hlt_switch, now, entities.max_age_s),
        stage=stage, step=str(brewday.get("step") or ""),
        usable_budget_w=config.usable_budget_w, hlt_target_c=config.hlt_target_c,
        hlt_volume_l=water_l,
    )
    runtime["status"] = result.state
    runtime["last_result"] = result
    runtime["last_updated"] = now.isoformat()
    runtime["sparge_water_l"] = water_l
    runtime["bz_cruising_observed"] = cruising
    runtime["bz_ramp_requested"] = ramp_requested
    runtime["scenario_only"] = True
    return runtime


def async_setup_hlt_simulation(hass: Any, entry: Any):
    """Register unloadable timer; never participates in physical BZ IO."""
    lock = asyncio.Lock()

    async def _run(now: datetime) -> None:
        if lock.locked():
            return
        async with lock:
            try:
                await async_hlt_simulation_tick(hass, entry, now=now)
            except (ValueError, TypeError, OSError) as exc:
                hass.data.setdefault("brewassistant", {}).setdefault(_KEY, {})["status"] = "error"
                _LOGGER.warning("HLT simulation tick skipped: %s", exc)
            except Exception:
                hass.data.setdefault("brewassistant", {}).setdefault(_KEY, {})["status"] = "error"
                _LOGGER.exception("HLT simulation tick failed (simulation only)")

    @callback
    def _schedule(now: datetime) -> None:
        hass.async_create_task(_run(now))

    return async_track_time_interval(hass, _schedule, _INTERVAL)
