"""Read-only physical mash timing and ramp telemetry for Brewday Runtime.

This module deliberately does not participate in BrewZilla orchestration.  It
observes the normalized Brewday Runtime plus the selected process-temperature
sensor and keeps an in-memory timing ledger for the current brew.

The distinction is intentional:
* Brewfather/source schedule time remains diagnostic input.
* Ramp timing measures the physical temperature transition.
* Mash hold timing starts only when the process temperature actually enters the
  target band; reaching target later must not steal time from the recipe hold.
* Runtime pause freezes the active timer.  Wall-clock duration is retained
  separately for ramp analysis.
* ABORT stops timing without issuing any physical command.

The current implementation is volatile across a Home Assistant restart.  That is
acceptable for the first physical validation and, importantly, keeps this layer
isolated from the control path.  Persistence can be added after field validation.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .brewday_runtime import build_brewday_runtime_snapshot
from ..const import DOMAIN
from ..coordinator import BrewAssistantCoordinator
from ..entity import BrewAssistantEntity

DATA_KEY = "brewday_physical_timing"
MASH_IN_GATE_KEY = "brewzilla_mash_in_gate"
TARGET_TOLERANCE_C = 0.3
ACTIVE_RUNTIME_STATES = {"live", "running", "paused", "awaiting_snapshot"}
TERMINAL_RUNTIME_STATES = {"aborted", "completed", "finished", "idle", "inactive"}
PROCESS_TEMP_ENTITY_CANDIDATES = (
    "sensor.brewassistant_brewzilla_mash_temperature",
    "sensor.brewzilla_ble_thermometer_temperature",
    "sensor.brewzilla_control_device_temperature",
    "sensor.brewzilla_temperature",
)
LEARNING_CONTEXT_ENTITY = "select.brewassistant_brewzilla_learning_context"
HEAT_UTILIZATION_ENTITY = "number.brewzilla_heat_utilization"
PUMP_UTILIZATION_ENTITY = "number.brewzilla_pump_utilization"


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _state_num(hass: HomeAssistant, entity_id: str) -> float | None:
    state = hass.states.get(entity_id)
    if state is None or str(state.state).lower() in {"unknown", "unavailable", "none", ""}:
        return None
    return _num(str(state.state).replace(",", "."))


def _state_text(hass: HomeAssistant, entity_id: str, default: str | None = None) -> str | None:
    state = hass.states.get(entity_id)
    if state is None or str(state.state).lower() in {"unknown", "unavailable", "none", ""}:
        return default
    return str(state.state)


def _process_temperature(hass: HomeAssistant) -> tuple[float | None, str | None]:
    for entity_id in PROCESS_TEMP_ENTITY_CANDIDATES:
        value = _state_num(hass, entity_id)
        if value is not None:
            return value, entity_id
    return None, None


def _store(hass: HomeAssistant) -> dict[str, Any]:
    return hass.data.setdefault(DOMAIN, {}).setdefault(
        DATA_KEY,
        {
            "session_active": False,
            "session_source": None,
            "active": None,
            "history": [],
            "last_runtime_state": "idle",
        },
    )


def _parse_time(value: Any):
    if not value:
        return None
    parsed = dt_util.parse_datetime(str(value))
    return dt_util.as_utc(parsed) if parsed is not None else None


def _seconds_between(start: Any, end) -> float:
    parsed = _parse_time(start)
    return 0.0 if parsed is None else max(0.0, (end - parsed).total_seconds())


def _timing_values(active: dict[str, Any], now) -> tuple[float, float, float]:
    """Return active elapsed, wall elapsed and total paused seconds."""
    origin = active.get("timer_started_at") or active.get("observed_at")
    wall = _seconds_between(origin, now)
    paused = float(active.get("paused_seconds") or 0.0)
    pause_started = active.get("pause_started_at")
    if pause_started:
        paused += _seconds_between(pause_started, now)
    elapsed = max(0.0, wall - paused)
    return elapsed, wall, paused


def _update_pause(active: dict[str, Any], runtime_state: str, now) -> None:
    paused_now = runtime_state == "paused"
    pause_started = active.get("pause_started_at")
    if paused_now and not pause_started:
        active["pause_started_at"] = now.isoformat()
        return
    if not paused_now and pause_started:
        active["paused_seconds"] = float(active.get("paused_seconds") or 0.0) + _seconds_between(pause_started, now)
        active["pause_started_at"] = None


def _mash_in_complete(hass: HomeAssistant) -> bool:
    """Return whether the physical mash-in gate allows mash hold timing.

    If the BrewZilla mash-in gate has not been instantiated, do not block timing;
    this keeps the telemetry usable for non-BrewZilla/manual sources.
    """
    gate = hass.data.get(DOMAIN, {}).get(MASH_IN_GATE_KEY)
    if not isinstance(gate, dict):
        return True
    return bool(gate.get("completed_once") or str(gate.get("state") or "") == "mash_in_complete")


def _active_timeline_step(snapshot: dict[str, Any]) -> tuple[int | None, dict[str, Any] | None]:
    timeline = snapshot.get("timeline")
    if not isinstance(timeline, list):
        return None, None
    for stage in timeline:
        if not isinstance(stage, dict) or not stage.get("active"):
            continue
        stage_index = stage.get("index")
        steps = stage.get("steps") if isinstance(stage.get("steps"), list) else []
        for step in steps:
            if isinstance(step, dict) and step.get("active"):
                return stage_index if isinstance(stage_index, int) else None, step
    return None, None


def _candidate(snapshot: dict[str, Any]) -> dict[str, Any] | None:
    """Return the physical timing candidate represented by the current source."""
    source = str(snapshot.get("source") or "None")
    stage_name = str(snapshot.get("stage") or "Unknown")

    if snapshot.get("ramp_target_gate_active"):
        target = _num(snapshot.get("ramp_target_temperature") or snapshot.get("target_temperature"))
        if target is not None:
            index = snapshot.get("resolved_step_index")
            return {
                "key": f"{source}|{stage_name}|ramp|{index}|{target:.2f}",
                "kind": "ramp",
                "name": str(snapshot.get("step") or f"Ramp to {target:.1f}°C"),
                "target": target,
                "duration_seconds": None,
                "stage_index": None,
                "step_index": index,
            }

    stage_index, step = _active_timeline_step(snapshot)
    if not isinstance(step, dict):
        return None
    kind = str(step.get("type") or "").strip().lower()
    target = _num(step.get("value"))
    duration = _num(step.get("duration"))
    step_index = step.get("index")
    name = str(step.get("name") or snapshot.get("step") or "Mash step")

    if kind == "ramp" and target is not None:
        return {
            "key": f"{source}|{stage_index}|{step_index}|ramp|{target:.2f}",
            "kind": "ramp",
            "name": name,
            "target": target,
            "duration_seconds": None,
            "stage_index": stage_index,
            "step_index": step_index,
        }
    if kind == "mash" and target is not None and duration is not None and duration > 0:
        return {
            "key": f"{source}|{stage_index}|{step_index}|hold|{target:.2f}|{int(duration)}",
            "kind": "hold",
            "name": name,
            "target": target,
            "duration_seconds": int(duration),
            "stage_index": stage_index,
            "step_index": step_index,
        }
    return None


def _new_active(hass: HomeAssistant, candidate: dict[str, Any], now, current_temp: float | None, temp_entity: str | None) -> dict[str, Any]:
    return {
        **candidate,
        "observed_at": now.isoformat(),
        "timer_started_at": now.isoformat() if candidate["kind"] == "ramp" else None,
        "target_reached_at": None,
        "completed_at": None,
        "completed": False,
        "paused_seconds": 0.0,
        "pause_started_at": None,
        "start_temperature": current_temp,
        "start_temperature_entity": temp_entity,
        "heat_utilization_start": _state_num(hass, HEAT_UTILIZATION_ENTITY),
        "pump_utilization_start": _state_num(hass, PUMP_UTILIZATION_ENTITY),
        "context": _state_text(hass, LEARNING_CONTEXT_ENTITY, "Unknown"),
    }


def _append_history(store: dict[str, Any], active: dict[str, Any], now, current_temp: float | None, temp_entity: str | None) -> None:
    if active.get("history_recorded"):
        return
    elapsed, wall, paused = _timing_values(active, now)
    start_temp = _num(active.get("start_temperature"))
    target = _num(active.get("target"))
    delta = None if start_temp is None or target is None else round(target - start_temp, 2)
    rate = None
    if active.get("kind") == "ramp" and delta is not None and elapsed > 0:
        rate = round(delta / (elapsed / 60.0), 3)
    history = store.setdefault("history", [])
    history.append(
        {
            "kind": active.get("kind"),
            "name": active.get("name"),
            "target_temperature": target,
            "from_temperature": start_temp,
            "end_temperature": current_temp,
            "temperature_delta_c": delta,
            "started_at": active.get("timer_started_at") or active.get("observed_at"),
            "target_reached_at": active.get("target_reached_at"),
            "completed_at": now.isoformat(),
            "duration_seconds": round(elapsed),
            "wall_duration_seconds": round(wall),
            "paused_seconds": round(paused),
            "average_c_per_min": rate,
            "process_temperature_source": temp_entity or active.get("start_temperature_entity"),
            "context": active.get("context"),
            "heat_utilization_start": active.get("heat_utilization_start"),
            "heat_utilization_end": _state_num(hass=store["_hass"], entity_id=HEAT_UTILIZATION_ENTITY) if store.get("_hass") else None,
            "pump_utilization_start": active.get("pump_utilization_start"),
            "pump_utilization_end": _state_num(hass=store["_hass"], entity_id=PUMP_UTILIZATION_ENTITY) if store.get("_hass") else None,
        }
    )
    # Keep attributes bounded for Home Assistant state-size safety.
    if len(history) > 32:
        del history[:-32]
    active["history_recorded"] = True


def _record_history(hass: HomeAssistant, store: dict[str, Any], active: dict[str, Any], now, current_temp: float | None, temp_entity: str | None) -> None:
    """Append one bounded history row without leaking HomeAssistant into stored attrs."""
    if active.get("history_recorded"):
        return
    elapsed, wall, paused = _timing_values(active, now)
    start_temp = _num(active.get("start_temperature"))
    target = _num(active.get("target"))
    delta = None if start_temp is None or target is None else round(target - start_temp, 2)
    rate = None
    if active.get("kind") == "ramp" and delta is not None and elapsed > 0:
        rate = round(delta / (elapsed / 60.0), 3)
    row = {
        "kind": active.get("kind"),
        "name": active.get("name"),
        "target_temperature": target,
        "from_temperature": start_temp,
        "end_temperature": current_temp,
        "temperature_delta_c": delta,
        "started_at": active.get("timer_started_at") or active.get("observed_at"),
        "target_reached_at": active.get("target_reached_at"),
        "completed_at": now.isoformat(),
        "duration_seconds": round(elapsed),
        "wall_duration_seconds": round(wall),
        "paused_seconds": round(paused),
        "average_c_per_min": rate,
        "process_temperature_source": temp_entity or active.get("start_temperature_entity"),
        "context": active.get("context"),
        "heat_utilization_start": active.get("heat_utilization_start"),
        "heat_utilization_end": _state_num(hass, HEAT_UTILIZATION_ENTITY),
        "pump_utilization_start": active.get("pump_utilization_start"),
        "pump_utilization_end": _state_num(hass, PUMP_UTILIZATION_ENTITY),
    }
    history = store.setdefault("history", [])
    history.append(row)
    if len(history) > 32:
        del history[:-32]
    active["history_recorded"] = True


def _reset_session(store: dict[str, Any]) -> None:
    store.update(
        {
            "session_active": False,
            "session_source": None,
            "active": None,
            "history": [],
        }
    )


def build_brewday_physical_timing_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    """Build and advance read-only physical timing telemetry."""
    runtime = build_brewday_runtime_snapshot(hass)
    runtime_state = str(runtime.get("runtime_state") or "idle").lower()
    source = str(runtime.get("source") or "None")
    now = dt_util.utcnow()
    store = _store(hass)

    if runtime_state in {"idle", "inactive"}:
        if store.get("session_active"):
            _reset_session(store)
        store["last_runtime_state"] = runtime_state
        return _snapshot_from_store(hass, runtime, store, now, None, None, None)

    if not store.get("session_active") and runtime_state in ACTIVE_RUNTIME_STATES:
        store["session_active"] = True
        store["session_source"] = source
        store["history"] = []
        store["active"] = None

    current_temp, temp_entity = _process_temperature(hass)
    candidate = _candidate(runtime)
    active = store.get("active") if isinstance(store.get("active"), dict) else None

    if runtime_state == "aborted":
        if active is not None:
            active["completed_at"] = now.isoformat()
            active["aborted"] = True
        store["active"] = None
        store["last_runtime_state"] = runtime_state
        return _snapshot_from_store(hass, runtime, store, now, current_temp, temp_entity, candidate, mode_override="aborted")

    source_mismatch = False
    if candidate is not None:
        if active is None:
            active = _new_active(hass, candidate, now, current_temp, temp_entity)
            store["active"] = active
        elif candidate.get("key") != active.get("key"):
            if active.get("completed"):
                active = _new_active(hass, candidate, now, current_temp, temp_entity)
                store["active"] = active
            else:
                # Preserve the physical timer even if Brewfather's schedule races
                # ahead. This is telemetry only: expose the mismatch, do not alter
                # runtime/control state.
                source_mismatch = True

    if active is not None:
        _update_pause(active, runtime_state, now)
        kind = str(active.get("kind") or "")
        target = _num(active.get("target"))
        reached = False
        if current_temp is not None and target is not None:
            if kind == "ramp":
                reached = current_temp >= target - TARGET_TOLERANCE_C
            elif kind == "hold":
                reached = abs(current_temp - target) <= TARGET_TOLERANCE_C

        if kind == "ramp" and reached and not active.get("completed"):
            active["target_reached_at"] = active.get("target_reached_at") or now.isoformat()
            active["completed_at"] = now.isoformat()
            active["completed"] = True
            _record_history(hass, store, active, now, current_temp, temp_entity)

        if kind == "hold" and active.get("timer_started_at") is None:
            if reached and runtime_state != "paused" and _mash_in_complete(hass):
                active["timer_started_at"] = now.isoformat()
                active["target_reached_at"] = now.isoformat()
                active["start_temperature"] = current_temp
                active["start_temperature_entity"] = temp_entity
                active["paused_seconds"] = 0.0
                active["pause_started_at"] = None

        if kind == "hold" and active.get("timer_started_at") is not None and not active.get("completed"):
            elapsed, _, _ = _timing_values(active, now)
            total = _num(active.get("duration_seconds")) or 0.0
            if total > 0 and elapsed >= total:
                active["completed_at"] = now.isoformat()
                active["completed"] = True
                _record_history(hass, store, active, now, current_temp, temp_entity)

    store["last_runtime_state"] = runtime_state
    return _snapshot_from_store(
        hass,
        runtime,
        store,
        now,
        current_temp,
        temp_entity,
        candidate,
        source_mismatch=source_mismatch,
    )


def _snapshot_from_store(
    hass: HomeAssistant,
    runtime: dict[str, Any],
    store: dict[str, Any],
    now,
    current_temp: float | None,
    temp_entity: str | None,
    candidate: dict[str, Any] | None,
    *,
    mode_override: str | None = None,
    source_mismatch: bool = False,
) -> dict[str, Any]:
    active = store.get("active") if isinstance(store.get("active"), dict) else None
    runtime_state = str(runtime.get("runtime_state") or "idle").lower()
    mode = mode_override or "idle"
    elapsed = 0.0
    wall_elapsed = 0.0
    paused = 0.0
    remaining: float | None = None
    total: float | None = None
    progress = 0.0
    rate: float | None = None
    target_reached = False
    target_reached_at = None
    timer_started_at = None
    step_name = None
    step_kind = None
    target = None

    if active is not None:
        elapsed, wall_elapsed, paused = _timing_values(active, now)
        step_name = active.get("name")
        step_kind = active.get("kind")
        target = _num(active.get("target"))
        target_reached_at = active.get("target_reached_at")
        target_reached = bool(target_reached_at)
        timer_started_at = active.get("timer_started_at")
        completed = bool(active.get("completed"))

        if step_kind == "ramp":
            mode = "ramp_complete" if completed else "ramp"
            start_temp = _num(active.get("start_temperature"))
            if start_temp is not None and current_temp is not None and elapsed > 0:
                rate = round((current_temp - start_temp) / (elapsed / 60.0), 3)
        elif step_kind == "hold":
            total = _num(active.get("duration_seconds"))
            if timer_started_at is None:
                mode = "waiting_for_target"
                remaining = total
            else:
                remaining = max((total or 0.0) - elapsed, 0.0)
                progress = 100.0 if not total or total <= 0 else min(max((elapsed / total) * 100.0, 0.0), 100.0)
                mode = "hold_complete" if completed else "hold"

        if runtime_state == "paused" and not completed:
            mode = f"{mode}_paused"

    context = _state_text(hass, LEARNING_CONTEXT_ENTITY, "Unknown")
    history = list(store.get("history") or [])
    if mode == "idle":
        summary = "idle · ingen fysisk mäsk-/ramptimer"
    elif mode == "aborted":
        summary = "aborted · fysisk timer stoppad"
    elif step_kind == "ramp":
        summary = f"{mode} · {step_name} · {round(elapsed)} s · {current_temp if current_temp is not None else '—'}°C / {target if target is not None else '—'}°C"
    elif timer_started_at is None:
        summary = f"{mode} · {step_name} · väntar på {target if target is not None else '—'}°C"
    else:
        summary = f"{mode} · {step_name} · {round(remaining or 0)} s kvar"

    return {
        "mode": mode,
        "summary": summary,
        "runtime_state": runtime_state,
        "runtime_source": runtime.get("source"),
        "runtime_stage": runtime.get("stage"),
        "runtime_step": runtime.get("step"),
        "source_candidate": candidate,
        "source_schedule_mismatch": source_mismatch,
        "step_name": step_name,
        "step_kind": step_kind,
        "target_temperature": target,
        "current_temperature": current_temp,
        "temperature_entity": temp_entity,
        "target_tolerance_c": TARGET_TOLERANCE_C,
        "target_reached": target_reached,
        "target_reached_at": target_reached_at,
        "timer_started_at": timer_started_at,
        "elapsed_seconds": round(elapsed),
        "wall_elapsed_seconds": round(wall_elapsed),
        "paused_seconds": round(paused),
        "remaining_seconds": None if remaining is None else round(remaining),
        "total_seconds": None if total is None else round(total),
        "progress_percent": round(progress, 1),
        "average_c_per_min": rate,
        "context": context,
        "mash_in_complete": _mash_in_complete(hass),
        "history_count": len(history),
        "history": history,
        "read_only": True,
        "control_side_effects": False,
        "volatile_across_restart": True,
    }


PHYSICAL_TIMING_SENSORS: dict[str, dict[str, Any]] = {
    "brewday_physical_timing_summary": {"field": "summary"},
    "brewday_physical_timing_mode": {"field": "mode"},
    "brewday_physical_elapsed_seconds": {
        "field": "elapsed_seconds",
        "unit": "s",
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "brewday_physical_remaining_seconds": {
        "field": "remaining_seconds",
        "unit": "s",
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "brewday_physical_progress": {
        "field": "progress_percent",
        "unit": PERCENTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "brewday_physical_ramp_rate": {
        "field": "average_c_per_min",
        "unit": "°C/min",
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "brewday_physical_target_temperature": {
        "field": "target_temperature",
        "unit": UnitOfTemperature.CELSIUS,
        "state_class": SensorStateClass.MEASUREMENT,
    },
}


def create_brewday_physical_timing_sensors(coordinator: BrewAssistantCoordinator) -> list[SensorEntity]:
    return [BrewAssistantBrewdayPhysicalTimingSensor(coordinator, key) for key in PHYSICAL_TIMING_SENSORS]


class BrewAssistantBrewdayPhysicalTimingSensor(BrewAssistantEntity, SensorEntity):
    """One read-only field from the physical timing ledger."""

    _attr_has_entity_name = False

    def __init__(self, coordinator: BrewAssistantCoordinator, key: str) -> None:
        super().__init__(coordinator, key)
        config = PHYSICAL_TIMING_SENSORS[key]
        self._key = key
        self._field = str(config["field"])
        self._attr_name = f"BrewAssistant {key.replace('_', ' ').title()}"
        self._attr_suggested_object_id = f"{DOMAIN}_{key}"
        self._attr_native_unit_of_measurement = config.get("unit")
        self._attr_state_class = config.get("state_class")

    @property
    def native_value(self) -> Any:
        return build_brewday_physical_timing_snapshot(self.coordinator.hass).get(self._field)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        snapshot = build_brewday_physical_timing_snapshot(self.coordinator.hass)
        if self._key == "brewday_physical_timing_summary":
            return snapshot
        return {
            "mode": snapshot.get("mode"),
            "step_name": snapshot.get("step_name"),
            "step_kind": snapshot.get("step_kind"),
            "target_temperature": snapshot.get("target_temperature"),
            "current_temperature": snapshot.get("current_temperature"),
            "target_reached_at": snapshot.get("target_reached_at"),
            "context": snapshot.get("context"),
            "source_schedule_mismatch": snapshot.get("source_schedule_mismatch"),
            "read_only": True,
        }
