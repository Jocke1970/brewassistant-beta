"""Temperature-gated Brewfather ramp handling for Brewday Runtime."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from . import brewday_runtime_core as core

RAMP_TARGET_REACHED_TOLERANCE_C = 0.3
MIN_RAMP_WAIT_REMAINING_SECONDS = 1
TEMP_ENTITY_CANDIDATES = (
    "sensor.brewassistant_brewzilla_mash_temperature",
    "sensor.brewzilla_ble_thermometer_temperature",
    "sensor.brewzilla_control_device_temperature",
    "sensor.brewzilla_temperature",
)


def _float_state(hass: HomeAssistant, entity_id: str) -> float | None:
    state = hass.states.get(entity_id)
    if state is None or state.state in core.BAD:
        return None
    try:
        return float(state.state)
    except (TypeError, ValueError):
        return None


def _runtime_temperature(hass: HomeAssistant) -> tuple[float | None, str | None]:
    for entity_id in TEMP_ENTITY_CANDIDATES:
        value = _float_state(hass, entity_id)
        if value is not None:
            return value, entity_id
    return None, None


def _is_ramp(step: dict[str, Any]) -> bool:
    return str(step.get("type") or "").lower() == "ramp"


def _ramp_target(step: dict[str, Any]) -> float | None:
    return core.as_float(step.get("value"))


def _target_reached(current_temperature: float | None, target: float | None) -> bool | None:
    if current_temperature is None or target is None:
        return None
    return current_temperature >= target - RAMP_TARGET_REACHED_TOLERANCE_C


def build_core_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    """Build a Brewday Runtime snapshot, holding ramp steps until target is reached."""
    snapshot = core.build_core_snapshot(hass)
    if snapshot.get("source") != "Brewfather Brew Tracker":
        return snapshot

    live_step = core.live_current_step(hass)
    if not live_step or not _is_ramp(live_step):
        return {
            **snapshot,
            "ramp_target_gate_active": False,
            "ramp_target_gate_blocking": False,
        }

    target = _ramp_target(live_step)
    current_temperature, temperature_entity = _runtime_temperature(hass)
    reached = _target_reached(current_temperature, target)
    if reached is not False:
        return {
            **snapshot,
            "ramp_target_gate_active": True,
            "ramp_target_gate_blocking": False,
            "ramp_target_reached": reached,
            "ramp_target_temperature": target,
            "ramp_actual_temperature": current_temperature,
            "ramp_temperature_entity": temperature_entity,
            "ramp_target_tolerance_c": RAMP_TARGET_REACHED_TOLERANCE_C,
        }

    nxt_name, nxt_desc, nxt_step = core.next_step(hass)
    step_name = core.step_display_name(live_step, core.step_name(live_step, "Ramp"))
    raw_step_name = core.step_name(live_step, step_name)
    remaining = max(
        int(snapshot.get("time_remaining_seconds") or 0),
        MIN_RAMP_WAIT_REMAINING_SECONDS,
    )
    runtime_state = snapshot.get("runtime_state")
    if runtime_state == "awaiting_snapshot":
        runtime_state = "live"

    return {
        **snapshot,
        "runtime_state": runtime_state,
        "step": step_name,
        "raw_step_name": raw_step_name,
        "next_step": nxt_name,
        "next_step_description": nxt_desc,
        "time_remaining_seconds": remaining,
        "time_remaining_minutes": round(remaining / 60),
        "current_step_remaining_seconds": remaining,
        "current_step_remaining_minutes": round(remaining / 60),
        "target_temperature": target,
        "target_temperature_source": "current_step_ramp_target_gate",
        "refresh_recommended": False,
        "awaiting_snapshot": False,
        "ramp_target_gate_active": True,
        "ramp_target_gate_blocking": True,
        "ramp_target_reached": False,
        "ramp_target_temperature": target,
        "ramp_actual_temperature": current_temperature,
        "ramp_temperature_entity": temperature_entity,
        "ramp_target_tolerance_c": RAMP_TARGET_REACHED_TOLERANCE_C,
        "ramp_next_step_type": nxt_step.get("type") if isinstance(nxt_step, dict) else None,
        "summary": f"{runtime_state} · {snapshot.get('stage')} · {step_name} · väntar på {target}°C",
    }


def core_attrs(snapshot: dict[str, Any]) -> dict[str, Any]:
    return core.core_attrs(snapshot)


def source(hass: HomeAssistant) -> str:
    return core.source(hass)
