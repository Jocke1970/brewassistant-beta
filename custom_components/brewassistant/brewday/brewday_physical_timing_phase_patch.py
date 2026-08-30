"""Physical-controller semantics for Brewday ramp timing.

The source schedule may pause or advance while BrewZilla is still physically
heating.  Physical ramp telemetry must therefore start from observed actuation
and must not freeze merely because Brewfather is paused at an operator/event
step such as mash additions.

This patch remains read-only: it only changes timing bookkeeping and never sends
BrewZilla commands.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import brewday_physical_timing as timing

_TARGET_ENTITY = "number.brewzilla_target_temperature"
_HEAT_ENTITY = "number.brewzilla_heat_utilization"
_HEATER_ENTITY = "switch.brewzilla_heater"
_TARGET_TOLERANCE_C = 0.3
_TEMP_MOVEMENT_START_C = 0.1

_ORIGINAL_NEW_ACTIVE: Callable[..., dict[str, Any]] | None = None
_ORIGINAL_UPDATE_PAUSE: Callable[..., None] | None = None
_ORIGINAL_TIMING_VALUES: Callable[..., tuple[float, float, float]] | None = None
_ORIGINAL_BUILD: Callable[[HomeAssistant], dict[str, Any]] | None = None
_INSTALLED = False


def _state_num(hass: HomeAssistant, entity_id: str) -> float | None:
    state = hass.states.get(entity_id)
    if state is None or str(state.state).lower() in {"unknown", "unavailable", "none", ""}:
        return None
    try:
        return float(str(state.state).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _state_on(hass: HomeAssistant, entity_id: str) -> bool:
    state = hass.states.get(entity_id)
    return bool(state is not None and str(state.state).lower() in {"on", "true", "yes"})


def _new_active(
    hass: HomeAssistant,
    candidate: dict[str, Any],
    now,
    current_temp: float | None,
    temp_entity: str | None,
) -> dict[str, Any]:
    assert _ORIGINAL_NEW_ACTIVE is not None
    active = _ORIGINAL_NEW_ACTIVE(hass, candidate, now, current_temp, temp_entity)
    if candidate.get("kind") == "ramp":
        # Observing a source ramp is not the same thing as physically starting it.
        active["timer_started_at"] = None
        active["physical_start_pending"] = True
    return active


def _timing_values(active: dict[str, Any], now) -> tuple[float, float, float]:
    assert _ORIGINAL_TIMING_VALUES is not None
    if active.get("kind") == "ramp" and not active.get("timer_started_at"):
        return 0.0, 0.0, float(active.get("paused_seconds") or 0.0)
    return _ORIGINAL_TIMING_VALUES(active, now)


def _update_pause(active: dict[str, Any], runtime_state: str, now) -> None:
    assert _ORIGINAL_UPDATE_PAUSE is not None
    if active.get("kind") == "ramp":
        # Brewfather frequently pauses at mash additions while Clean Heatstrike
        # remains physically active. Source-schedule pause must not freeze a
        # physical ramp clock. ABORT is handled separately by the base module.
        pause_started = active.get("pause_started_at")
        if pause_started:
            active["paused_seconds"] = float(active.get("paused_seconds") or 0.0) + timing._seconds_between(
                pause_started, now
            )
            active["pause_started_at"] = None
        return
    _ORIGINAL_UPDATE_PAUSE(active, runtime_state, now)


def _physical_ramp_started(hass: HomeAssistant, active: dict[str, Any], current_temp: float | None) -> bool:
    target = timing._num(active.get("target"))
    device_target = _state_num(hass, _TARGET_ENTITY)
    heat = _state_num(hass, _HEAT_ENTITY)
    heater_on = _state_on(hass, _HEATER_ENTITY)
    start_temp = timing._num(active.get("start_temperature"))

    target_applied = bool(
        target is not None
        and device_target is not None
        and abs(device_target - target) <= _TARGET_TOLERANCE_C
    )
    energized = bool(heater_on and heat is not None and heat > 0.1)
    moved = bool(
        current_temp is not None
        and start_temp is not None
        and target is not None
        and (
            (target >= start_temp and current_temp >= start_temp + _TEMP_MOVEMENT_START_C)
            or (target < start_temp and current_temp <= start_temp - _TEMP_MOVEMENT_START_C)
        )
    )
    return bool(target_applied and (energized or moved))


def _latch_physical_start(hass: HomeAssistant) -> bool:
    store = hass.data.get(timing.DOMAIN, {}).get(timing.DATA_KEY)
    if not isinstance(store, dict):
        return False
    active = store.get("active")
    if not isinstance(active, dict) or active.get("kind") != "ramp" or active.get("timer_started_at"):
        return False

    current_temp, temp_entity = timing._process_temperature(hass)
    if not _physical_ramp_started(hass, active, current_temp):
        return False

    now = dt_util.utcnow()
    active["timer_started_at"] = now.isoformat()
    active["physical_started_at"] = now.isoformat()
    active["physical_start_pending"] = False
    active["start_temperature"] = current_temp
    active["start_temperature_entity"] = temp_entity
    active["heat_utilization_start"] = _state_num(hass, _HEAT_ENTITY)
    active["pump_utilization_start"] = _state_num(hass, timing.PUMP_UTILIZATION_ENTITY)
    active["paused_seconds"] = 0.0
    active["pause_started_at"] = None
    return True


def _fix_ramp_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    if snapshot.get("step_kind") != "ramp":
        snapshot.setdefault("physical_start_pending", False)
        return snapshot

    mode = str(snapshot.get("mode") or "ramp")
    runtime_paused = str(snapshot.get("runtime_state") or "").lower() == "paused"
    timer_started = bool(snapshot.get("timer_started_at"))

    if not timer_started:
        snapshot["mode"] = "waiting_for_physical_start"
        snapshot["summary"] = (
            f"waiting_for_physical_start · {snapshot.get('step_name')} · "
            f"{snapshot.get('current_temperature') if snapshot.get('current_temperature') is not None else '—'}°C / "
            f"{snapshot.get('target_temperature') if snapshot.get('target_temperature') is not None else '—'}°C"
        )
        snapshot["elapsed_seconds"] = 0
        snapshot["wall_elapsed_seconds"] = 0
        snapshot["average_c_per_min"] = None
        snapshot["physical_start_pending"] = True
    else:
        if mode.endswith("_paused"):
            snapshot["mode"] = mode.removesuffix("_paused")
        snapshot["physical_start_pending"] = False

    snapshot["source_schedule_paused"] = runtime_paused
    snapshot["physical_ramp_clock_follows_source_pause"] = False
    return snapshot


def build_brewday_physical_timing_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    """Advance base telemetry, then latch actual ramp actuation if observed."""
    assert _ORIGINAL_BUILD is not None
    snapshot = _ORIGINAL_BUILD(hass)

    if _latch_physical_start(hass):
        # Rebuild once so the same coordinator tick exposes the newly latched
        # physical start instead of waiting another 30 seconds.
        snapshot = _ORIGINAL_BUILD(hass)

    return _fix_ramp_snapshot(snapshot)


def install_physical_timing_phase_patch() -> None:
    """Install read-only physical timing semantics."""
    global _ORIGINAL_NEW_ACTIVE, _ORIGINAL_UPDATE_PAUSE, _ORIGINAL_TIMING_VALUES, _ORIGINAL_BUILD, _INSTALLED
    if _INSTALLED:
        return

    _ORIGINAL_NEW_ACTIVE = timing._new_active
    _ORIGINAL_UPDATE_PAUSE = timing._update_pause
    _ORIGINAL_TIMING_VALUES = timing._timing_values
    _ORIGINAL_BUILD = timing.build_brewday_physical_timing_snapshot

    timing._new_active = _new_active
    timing._update_pause = _update_pause
    timing._timing_values = _timing_values
    timing.build_brewday_physical_timing_snapshot = build_brewday_physical_timing_snapshot
    _INSTALLED = True
