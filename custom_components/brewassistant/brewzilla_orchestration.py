"""Production-style BrewZilla orchestration helpers.

BrewAssistant treats Brewfather Brew Tracker as the real runtime source. The low
temperature test batch is safe because the recipe is safe, not because the
runtime is artificially limited. Abort remains available as the hard stop.
"""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .brewday_audit import async_record_brewday_audit_tick
from .brewday_runtime_core import build_core_snapshot

BREWZILLA_TARGET_NUMBER = "number.brewzilla_target_temperature"
BREWZILLA_TEMP_SENSOR = "sensor.brewzilla_temperature"
BREWZILLA_CONNECTION_SENSOR = "sensor.brewzilla_connection"
BREWZILLA_HEATER_SWITCH = "switch.brewzilla_heater"
BREWZILLA_PUMP_SWITCH = "switch.brewzilla_pump"

SOURCE = "brewzilla_orchestration"
MIN_TARGET_TEMP = 0.0
MAX_TARGET_TEMP = 110.0
TARGET_SYNC_TOLERANCE = 0.1
MAX_SNAPSHOT_AGE_MINUTES = 15.0

_BAD = {None, "unknown", "unavailable", "none", ""}
_ACTIVE_RUNTIME_STATES = {"live", "running", "paused", "awaiting_snapshot"}
_MASH_WORDS = ("mash", "mäsk", "protein", "beta", "alpha", "saccharification", "sack", "rest")


def _state(hass: HomeAssistant, entity_id: str, default: str | None = None) -> str | None:
    entity_state = hass.states.get(entity_id)
    if entity_state is None or entity_state.state in _BAD:
        return default
    return entity_state.state


def _float(hass: HomeAssistant, entity_id: str) -> float | None:
    raw = _state(hass, entity_id)
    if raw in _BAD:
        return None
    try:
        return float(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _bool_state(hass: HomeAssistant, entity_id: str, default: bool = False) -> bool:
    fallback = "on" if default else "off"
    return str(_state(hass, entity_id, fallback)).lower() in {"on", "true", "yes"}


def _runtime_active(state: str | None) -> bool:
    return (state or "").lower() in _ACTIVE_RUNTIME_STATES


def _stage_recommends_pump(runtime: dict[str, Any]) -> bool:
    """Return whether the current runtime stage/step should recommend pump use."""
    text = f"{runtime.get('stage') or ''} {runtime.get('step') or ''} {runtime.get('raw_step_name') or ''}".lower()
    return any(word in text for word in _MASH_WORDS)


def _target_valid(target: float | None) -> bool:
    return target is not None and MIN_TARGET_TEMP <= target <= MAX_TARGET_TEMP


def build_orchestration_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    """Build a production-style BrewZilla orchestration snapshot.

    Runtime values are read directly from Brewday Runtime Core instead of the
    rendered Home Assistant sensor entities. This avoids a one-coordinator-tick
    lag where the audit/runtime target has already advanced but orchestration
    still reads the previous sensor state.
    """
    runtime = build_core_snapshot(hass)
    runtime_state = str(runtime.get("runtime_state") or "idle")
    requested_target = runtime.get("target_temperature")
    try:
        requested_target = float(requested_target) if requested_target is not None else None
    except (TypeError, ValueError):
        requested_target = None

    applied_target = _float(hass, BREWZILLA_TARGET_NUMBER)
    current_temperature = _float(hass, BREWZILLA_TEMP_SENSOR)
    connection = _state(hass, BREWZILLA_CONNECTION_SENSOR, "unknown")
    connected = connection == "Connected"
    awaiting_snapshot = bool(runtime.get("awaiting_snapshot"))
    snapshot_age_minutes = float(runtime.get("snapshot_age_minutes") or 0.0)
    heater_on = _bool_state(hass, BREWZILLA_HEATER_SWITCH)
    pump_on = _bool_state(hass, BREWZILLA_PUMP_SWITCH)

    target_delta = None
    if requested_target is not None and applied_target is not None:
        target_delta = round(requested_target - applied_target, 2)

    target_sync_needed = target_delta is not None and abs(target_delta) > TARGET_SYNC_TOLERANCE
    heating_needed = False
    if requested_target is not None and current_temperature is not None:
        heating_needed = current_temperature < requested_target - TARGET_SYNC_TOLERANCE

    pump_recommended = _stage_recommends_pump(runtime)
    heater_action_needed = heating_needed and not heater_on
    pump_action_needed = pump_recommended and not pump_on

    hard_block = None
    if not connected:
        hard_block = "BrewZilla disconnected"
    elif not _runtime_active(runtime_state):
        hard_block = f"Brewday runtime {runtime_state}"
    elif snapshot_age_minutes > MAX_SNAPSHOT_AGE_MINUTES:
        hard_block = "Brew Tracker snapshot too old"
    elif not _target_valid(requested_target):
        hard_block = "Missing or invalid Brew Tracker target"

    can_control = hard_block is None
    action_needed = target_sync_needed or heater_action_needed or pump_action_needed
    mode = "direct-control" if can_control and action_needed else "monitor"
    if hard_block is not None:
        mode = "blocked"

    reason = hard_block or "Direct production flow active"
    if hard_block is None and heater_action_needed:
        reason = "Heating needed; heater should be ON"
    elif hard_block is None and pump_action_needed:
        reason = "Mash circulation recommended; pump should be ON"
    elif hard_block is None and awaiting_snapshot:
        reason = "Awaiting fresh snapshot, using current valid Brew Tracker target"
    elif hard_block is None and runtime_state == "paused":
        reason = "Brewfather paused; maintaining current valid target"

    return {
        "source": SOURCE,
        "connected": connected,
        "connection_state": connection,
        "brewday_state": runtime_state,
        "runtime_stage": runtime.get("stage"),
        "runtime_step": runtime.get("step"),
        "runtime_raw_step_name": runtime.get("raw_step_name"),
        "runtime_raw_step_index": runtime.get("raw_step_index"),
        "runtime_resolved_step_index": runtime.get("resolved_step_index"),
        "requested_target": requested_target,
        "applied_target": applied_target,
        "current_temperature": current_temperature,
        "target_delta": target_delta,
        "target_sync_needed": target_sync_needed,
        "can_apply_target": can_control and action_needed,
        "heating_needed": heating_needed,
        "heater_on": heater_on,
        "heater_action_needed": heater_action_needed,
        "pump_recommended": pump_recommended,
        "pump_on": pump_on,
        "pump_action_needed": pump_action_needed,
        "awaiting_snapshot": awaiting_snapshot,
        "snapshot_age_minutes": snapshot_age_minutes,
        "orchestration_mode": mode,
        "safety_state": "operator-supervised",
        "control_reason": reason,
        "has_pending_action": False,
        "pending_action": None,
        "pending_summary": None,
        "mode_scope": "direct_with_abort",
    }


async def async_abort_brewzilla(hass: HomeAssistant) -> dict[str, Any]:
    """Hard stop BrewZilla controllable outputs used by BrewAssistant."""
    result: dict[str, Any] = {
        "source": SOURCE,
        "status": "aborted",
        "aborted_at": dt_util.utcnow().isoformat(),
        "actions": [],
    }
    for entity_id in (BREWZILLA_HEATER_SWITCH, BREWZILLA_PUMP_SWITCH):
        if hass.states.get(entity_id) is not None:
            await hass.services.async_call(
                "switch",
                "turn_off",
                {"entity_id": entity_id},
                blocking=True,
            )
            result["actions"].append(f"turned_off:{entity_id}")
    hass.data.setdefault("brewassistant", {})["brewzilla_last_abort"] = result
    return result


async def async_apply_brewzilla_target_if_allowed(hass: HomeAssistant) -> dict[str, Any]:
    """Apply Brew Tracker runtime target and required BrewZilla actions."""
    snapshot = build_orchestration_snapshot(hass)
    if not snapshot["can_apply_target"]:
        result = {**snapshot, "applied": False, "apply_result": "not_needed_or_blocked"}
        await async_record_brewday_audit_tick(hass, brewzilla_result=result)
        return result

    target = snapshot["requested_target"]
    target_changed = False
    if snapshot.get("target_sync_needed") and target is not None:
        rounded_target = round(float(target), 1)
        await hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": BREWZILLA_TARGET_NUMBER, "value": rounded_target},
            blocking=True,
        )
        target_changed = True
    else:
        rounded_target = round(float(target), 1) if target is not None else None

    heater_changed = False
    if snapshot.get("heater_action_needed") and hass.states.get(BREWZILLA_HEATER_SWITCH) is not None:
        await hass.services.async_call(
            "switch",
            "turn_on",
            {"entity_id": BREWZILLA_HEATER_SWITCH},
            blocking=True,
        )
        heater_changed = True

    pump_changed = False
    if snapshot.get("pump_action_needed") and hass.states.get(BREWZILLA_PUMP_SWITCH) is not None:
        await hass.services.async_call(
            "switch",
            "turn_on",
            {"entity_id": BREWZILLA_PUMP_SWITCH},
            blocking=True,
        )
        pump_changed = True

    result = {
        **snapshot,
        "applied": target_changed or heater_changed or pump_changed,
        "apply_result": "direct_applied" if (target_changed or heater_changed or pump_changed) else "no_action_needed",
        "applied_target_value": rounded_target,
        "target_changed": target_changed,
        "heater_started": heater_changed,
        "pump_started": pump_changed,
        "executed_at": dt_util.utcnow().isoformat(),
    }
    hass.data.setdefault("brewassistant", {})["brewzilla_last_apply_result"] = result
    await async_record_brewday_audit_tick(hass, brewzilla_result=result)
    return result
