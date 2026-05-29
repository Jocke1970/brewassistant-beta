"""Production-style BrewZilla orchestration helpers.

BrewAssistant treats Brewfather Brew Tracker as the real runtime source. The low
temperature test batch is safe because the recipe is safe, not because the
runtime is artificially limited. Abort remains available as the hard stop.
"""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

BREWDAY_TARGET_SENSOR = "sensor.brewassistant_brewday_target_temperature"
BREWDAY_STATE_SENSOR = "sensor.brewassistant_brewday_runtime_state"
BREWDAY_STAGE_SENSOR = "sensor.brewassistant_brewday_runtime_stage"
BREWDAY_STEP_SENSOR = "sensor.brewassistant_brewday_runtime_step"
BREWDAY_AWAITING_SNAPSHOT = "sensor.brewassistant_brewday_awaiting_snapshot"
BREWZILLA_TARGET_NUMBER = "number.brewzilla_target_temperature"
BREWZILLA_TEMP_SENSOR = "sensor.brewzilla_temperature"
BREWZILLA_CONNECTION_SENSOR = "sensor.brewzilla_connection"
BREWZILLA_HEATER_SWITCH = "switch.brewzilla_heater"
BREWZILLA_PUMP_SWITCH = "switch.brewzilla_pump"

SOURCE = "brewzilla_orchestration"
MIN_TARGET_TEMP = 0.0
MAX_TARGET_TEMP = 110.0
TARGET_SYNC_TOLERANCE = 0.1

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


def _stage_recommends_pump(hass: HomeAssistant) -> bool:
    text = f"{_state(hass, BREWDAY_STAGE_SENSOR, '')} {_state(hass, BREWDAY_STEP_SENSOR, '')}".lower()
    return any(word in text for word in _MASH_WORDS)


def _target_valid(target: float | None) -> bool:
    return target is not None and MIN_TARGET_TEMP <= target <= MAX_TARGET_TEMP


def build_orchestration_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    """Build a production-style BrewZilla orchestration snapshot."""
    runtime_state = _state(hass, BREWDAY_STATE_SENSOR, "idle")
    requested_target = _float(hass, BREWDAY_TARGET_SENSOR)
    applied_target = _float(hass, BREWZILLA_TARGET_NUMBER)
    current_temperature = _float(hass, BREWZILLA_TEMP_SENSOR)
    connection = _state(hass, BREWZILLA_CONNECTION_SENSOR, "unknown")
    connected = connection == "Connected"
    awaiting_snapshot = _bool_state(hass, BREWDAY_AWAITING_SNAPSHOT)

    target_delta = None
    if requested_target is not None and applied_target is not None:
        target_delta = round(requested_target - applied_target, 2)

    target_sync_needed = target_delta is not None and abs(target_delta) > TARGET_SYNC_TOLERANCE
    heating_needed = False
    if requested_target is not None and current_temperature is not None:
        heating_needed = current_temperature < requested_target - TARGET_SYNC_TOLERANCE

    hard_block = None
    if not connected:
        hard_block = "BrewZilla disconnected"
    elif not _runtime_active(runtime_state):
        hard_block = f"Brewday runtime {runtime_state}"
    elif awaiting_snapshot:
        hard_block = "Waiting for fresh Brew Tracker snapshot"
    elif not _target_valid(requested_target):
        hard_block = "Missing or invalid Brew Tracker target"

    can_control = hard_block is None
    mode = "direct-control" if can_control and target_sync_needed else "monitor"
    if hard_block is not None:
        mode = "blocked"

    return {
        "source": SOURCE,
        "connected": connected,
        "connection_state": connection,
        "brewday_state": runtime_state,
        "runtime_stage": _state(hass, BREWDAY_STAGE_SENSOR),
        "runtime_step": _state(hass, BREWDAY_STEP_SENSOR),
        "requested_target": requested_target,
        "applied_target": applied_target,
        "current_temperature": current_temperature,
        "target_delta": target_delta,
        "target_sync_needed": target_sync_needed,
        "can_apply_target": can_control and target_sync_needed,
        "heating_needed": heating_needed,
        "pump_recommended": _stage_recommends_pump(hass),
        "awaiting_snapshot": awaiting_snapshot,
        "orchestration_mode": mode,
        "safety_state": "operator-supervised",
        "control_reason": hard_block or "Direct production flow active",
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
    """Apply Brew Tracker runtime target directly to BrewZilla.

    This is the intended final flow for the low-temperature supervised test:
    Brew Tracker drives the target, BrewAssistant applies it, and the operator can
    abort immediately if anything looks wrong.
    """
    snapshot = build_orchestration_snapshot(hass)
    if not snapshot["can_apply_target"]:
        return {**snapshot, "applied": False, "apply_result": "not_needed_or_blocked"}

    target = snapshot["requested_target"]
    if target is None:
        return {**snapshot, "applied": False, "apply_result": "missing_target"}

    rounded_target = round(float(target), 1)
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": BREWZILLA_TARGET_NUMBER, "value": rounded_target},
        blocking=True,
    )

    heater_changed = False
    if snapshot.get("heating_needed") and hass.states.get(BREWZILLA_HEATER_SWITCH) is not None:
        await hass.services.async_call(
            "switch",
            "turn_on",
            {"entity_id": BREWZILLA_HEATER_SWITCH},
            blocking=True,
        )
        heater_changed = True

    pump_changed = False
    if snapshot.get("pump_recommended") and hass.states.get(BREWZILLA_PUMP_SWITCH) is not None:
        await hass.services.async_call(
            "switch",
            "turn_on",
            {"entity_id": BREWZILLA_PUMP_SWITCH},
            blocking=True,
        )
        pump_changed = True

    result = {
        **snapshot,
        "applied": True,
        "apply_result": "direct_applied",
        "applied_target_value": rounded_target,
        "heater_started": heater_changed,
        "pump_started": pump_changed,
        "executed_at": dt_util.utcnow().isoformat(),
    }
    hass.data.setdefault("brewassistant", {})["brewzilla_last_apply_result"] = result
    return result
