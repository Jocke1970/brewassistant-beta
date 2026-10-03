"""Supervised GF30 target adapter for BrewAssistant.

BrewAssistant owns the recommendation. The external Grainfather integration owns
controller transport, command validation and MQTT readback verification.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from homeassistant.core import HomeAssistant

from ..supervised_apply import (
    get_last_result,
    get_pending_action,
    register_supervised_executor,
    set_pending_action,
    supervised_apply_enabled,
)
from .adapter import build_grainfather_fermenter_snapshot

SOURCE = "grainfather_fermenter_supervisor"
KIND = "gf30_set_target_temperature"
RECOMMENDED_TARGET_ENTITY = "sensor.brewassistant_fermentation_recommended_temperature"
EXTERNAL_DOMAIN = "grainfather"
EXTERNAL_SERVICE = "set_controller_target_temperature"
TARGET_EPSILON_C = 0.25
INVALID_STATES = {"unknown", "unavailable", "none", ""}


def _float_state(hass: HomeAssistant, entity_id: str) -> float | None:
    state = hass.states.get(entity_id)
    if state is None or str(state.state).strip().lower() in INVALID_STATES:
        return None
    try:
        return float(str(state.state).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _build_pending_action(snapshot: dict[str, Any]) -> dict[str, Any]:
    target = float(snapshot["recommended_target_temperature"])
    device_id = int(snapshot["device_id"])
    return {
        "source": SOURCE,
        "kind": KIND,
        "entity_id": snapshot.get("target_temperature_entity"),
        "domain": EXTERNAL_DOMAIN,
        "service": EXTERNAL_SERVICE,
        "service_data": {
            "device_id": device_id,
            "temperature": target,
            "confirm": True,
        },
        "device_id": device_id,
        "recommended_target_temperature": target,
        "controller_target_temperature": snapshot.get("controller_target_temperature"),
        "target_delta": snapshot.get("target_delta"),
        "summary": f"Set GF30 target to {target:.1f} °C",
    }


def build_gf30_target_adapter_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    cloud = build_grainfather_fermenter_snapshot(hass)
    selected = cloud.get("selected_device") or {}
    recommended = _float_state(hass, RECOMMENDED_TARGET_ENTITY)
    controller_target = cloud.get("target_temperature")
    device_id = selected.get("device_id") if isinstance(selected, dict) else None
    controller_online = (
        selected.get("controller_online") if isinstance(selected, dict) else None
    )
    target_entity = cloud.get("target_temperature_entity")
    service_available = hass.services.has_service(EXTERNAL_DOMAIN, EXTERNAL_SERVICE)

    delta = None
    if recommended is not None and controller_target is not None:
        delta = round(recommended - float(controller_target), 2)

    ready = bool(
        device_id is not None
        and cloud.get("controller_linked") is True
        and controller_online is True
        and target_entity
        and service_available
    )

    if not ready:
        state = "unavailable"
        reason = "GF30 supervised target prerequisites are incomplete"
    elif recommended is None:
        state = "waiting_for_recommendation"
        reason = "BrewAssistant has no current fermentation temperature recommendation"
    elif controller_target is None:
        state = "waiting_for_controller_target"
        reason = "GF30 target temperature is unavailable"
    elif delta is not None and abs(delta) < TARGET_EPSILON_C:
        state = "no_change"
        reason = "GF30 target already matches the BrewAssistant recommendation"
    else:
        state = "proposed"
        reason = "BrewAssistant recommendation differs from the GF30 controller target"

    pending = get_pending_action(hass)
    has_pending = bool(
        pending
        and pending.get("source") == SOURCE
        and pending.get("kind") == KIND
    )
    last_result = get_last_result(hass)

    return {
        "state": "awaiting_confirmation" if has_pending else state,
        "reason": reason,
        "ready": ready,
        "supervised_apply_enabled": supervised_apply_enabled(hass),
        "recommended_target_temperature": recommended,
        "recommendation_entity": RECOMMENDED_TARGET_ENTITY,
        "controller_target_temperature": controller_target,
        "target_temperature_entity": target_entity,
        "target_delta": delta,
        "device_id": device_id,
        "controller_online": controller_online,
        "controller_state": (
            selected.get("controller_state") if isinstance(selected, dict) else None
        ),
        "service_available": service_available,
        "service": f"{EXTERNAL_DOMAIN}.{EXTERNAL_SERVICE}",
        "has_pending_action": has_pending,
        "pending_action": deepcopy(pending) if has_pending else None,
        "last_supervised_result": deepcopy(last_result),
        "backend": "grainfather_fermenter",
        "control_mode": "supervised_apply",
    }


def request_gf30_target_confirmation(hass: HomeAssistant) -> dict[str, Any]:
    """Create a pending GF30 target action; never execute the write here."""
    snapshot = build_gf30_target_adapter_snapshot(hass)
    if not snapshot["supervised_apply_enabled"]:
        return {**snapshot, "request_result": "supervised_apply_disabled"}
    if not snapshot["ready"]:
        return {**snapshot, "request_result": "not_ready"}
    if snapshot["state"] == "no_change":
        return {**snapshot, "request_result": "no_change"}
    if snapshot["recommended_target_temperature"] is None:
        return {**snapshot, "request_result": "no_recommendation"}

    pending = set_pending_action(hass, _build_pending_action(snapshot))
    return {
        **snapshot,
        "state": "awaiting_confirmation",
        "has_pending_action": True,
        "pending_action": pending,
        "request_result": "pending_confirmation",
    }


async def async_execute_confirmed_gf30_target(
    hass: HomeAssistant,
    pending: dict[str, Any],
) -> dict[str, Any]:
    """Execute only the exact currently valid recommendation after confirmation."""
    live = build_gf30_target_adapter_snapshot(hass)
    requested = pending.get("recommended_target_temperature")
    live_recommended = live.get("recommended_target_temperature")

    if not live.get("ready"):
        return {
            "supervised_confirmation_consumed": False,
            "apply_result": "not_ready",
            "live_snapshot": live,
        }
    if requested is None or live_recommended is None:
        return {
            "supervised_confirmation_consumed": False,
            "apply_result": "recommendation_missing",
            "live_snapshot": live,
        }
    if abs(float(requested) - float(live_recommended)) > 0.01:
        return {
            "supervised_confirmation_consumed": False,
            "apply_result": "recommendation_changed",
            "live_snapshot": live,
        }

    device_id = int(live["device_id"])
    target = float(live_recommended)
    await hass.services.async_call(
        EXTERNAL_DOMAIN,
        EXTERNAL_SERVICE,
        {
            "device_id": device_id,
            "temperature": target,
            "confirm": True,
        },
        blocking=True,
    )

    temperature_entity = live.get("temperature_entity")
    if temperature_entity is None:
        cloud = build_grainfather_fermenter_snapshot(hass)
        temperature_entity = cloud.get("temperature_entity")
    temperature_state = hass.states.get(temperature_entity) if temperature_entity else None
    attrs = temperature_state.attributes if temperature_state is not None else {}
    external_result = attrs.get("target_write_last_result")
    readback = attrs.get("target_write_last_readback_value")

    verified = external_result == "verified"
    return {
        "supervised_confirmation_consumed": verified,
        "apply_result": "verified" if verified else str(external_result or "unverified"),
        "requested_target_temperature": target,
        "readback_target_temperature": readback,
        "device_id": device_id,
        "external_service": f"{EXTERNAL_DOMAIN}.{EXTERNAL_SERVICE}",
    }


def setup_gf30_supervised_target_adapter() -> None:
    register_supervised_executor(SOURCE, KIND, async_execute_confirmed_gf30_target)
