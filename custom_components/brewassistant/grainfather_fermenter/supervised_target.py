"""Supervised GF30 target adapter for BrewAssistant.

The fermentation recipe/profile owns the target. BrewAssistant supervises the
handoff, while the external Grainfather integration owns controller transport,
command validation and MQTT readback verification.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from homeassistant.core import HomeAssistant

from ..fermentation_tracking.models import PROVIDER_GRAINFATHER_GF30
from ..fermentation_tracking.storage import get_runtime
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
PROFILE_TARGET_SOURCES = {"brewfather_recipe_schedule"}
EXTERNAL_DOMAIN = "grainfather"
EXTERNAL_SERVICE = "set_controller_target_temperature"
TARGET_EPSILON_C = 0.25
INVALID_STATES = {"unknown", "unavailable", "none", ""}


def _target_state_info(hass: HomeAssistant) -> dict[str, Any]:
    """Return the normalized fermentation target and its provenance."""
    state = hass.states.get(RECOMMENDED_TARGET_ENTITY)
    value = None
    if state is not None and str(state.state).strip().lower() not in INVALID_STATES:
        try:
            value = float(str(state.state).replace(",", "."))
        except (TypeError, ValueError):
            value = None

    attrs = state.attributes if state is not None else {}
    source = str(attrs.get("recommended_temperature_source") or "")
    source_entity = attrs.get("recommended_temperature_entity")
    profile_backed = value is not None and source in PROFILE_TARGET_SOURCES

    return {
        "raw_target_temperature": value,
        "target_source": source or None,
        "target_source_entity": source_entity,
        "profile_backed": profile_backed,
        "profile_target_temperature": value if profile_backed else None,
    }


def _build_pending_action(snapshot: dict[str, Any]) -> dict[str, Any]:
    target = float(snapshot["profile_target_temperature"])
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
        "profile_target_temperature": target,
        "profile_target_source": snapshot.get("profile_target_source"),
        "recommended_target_temperature": target,
        "controller_target_temperature": snapshot.get("controller_target_temperature"),
        "target_delta": snapshot.get("target_delta"),
        "summary": f"Set GF30 target to fermentation profile target {target:.1f} °C",
    }


def build_gf30_target_adapter_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    cloud = build_grainfather_fermenter_snapshot(hass)
    selected_provider = get_runtime(hass).fermentation_provider
    provider_selected = selected_provider == PROVIDER_GRAINFATHER_GF30
    selected = cloud.get("selected_device") or {}
    target_info = _target_state_info(hass)
    raw_recommended = target_info["raw_target_temperature"]
    profile_target = target_info["profile_target_temperature"]
    profile_source = target_info["target_source"]
    profile_source_entity = target_info["target_source_entity"]
    profile_backed = bool(target_info["profile_backed"])
    controller_target = cloud.get("target_temperature")
    device_id = selected.get("device_id") if isinstance(selected, dict) else None
    controller_online = (
        selected.get("controller_online") if isinstance(selected, dict) else None
    )
    target_entity = cloud.get("target_temperature_entity")
    service_available = hass.services.has_service(EXTERNAL_DOMAIN, EXTERNAL_SERVICE)

    delta = None
    if profile_target is not None and controller_target is not None:
        delta = round(profile_target - float(controller_target), 2)

    hardware_ready = bool(
        device_id is not None
        and cloud.get("controller_linked") is True
        and controller_online is True
        and target_entity
        and service_available
    )
    profile_target_ready = bool(profile_backed and profile_target is not None)
    ready = provider_selected and hardware_ready and profile_target_ready

    if not provider_selected:
        state = "provider_inactive"
        reason = f"selected fermentation provider is {selected_provider}"
    elif not hardware_ready:
        state = "unavailable"
        reason = "GF30 supervised target prerequisites are incomplete"
    elif not profile_target_ready:
        state = "waiting_for_profile"
        reason = (
            "No authoritative fermentation profile target is available; "
            "tracking-rule fallback is not allowed to control GF30"
        )
    elif controller_target is None:
        state = "waiting_for_controller_target"
        reason = "GF30 target temperature is unavailable"
    elif delta is not None and abs(delta) < TARGET_EPSILON_C:
        state = "no_change"
        reason = "GF30 target already matches the fermentation profile target"
    else:
        state = "proposed"
        reason = "Fermentation profile target differs from the GF30 controller target"

    pending = get_pending_action(hass)
    has_pending = bool(
        pending
        and pending.get("source") == SOURCE
        and pending.get("kind") == KIND
    )
    last_result = get_last_result(hass)

    return {
        "state": "awaiting_confirmation" if has_pending and provider_selected else state,
        "fermentation_provider": selected_provider,
        "provider_selected": provider_selected,
        "provider_control_allowed": provider_selected,
        "reason": reason,
        "ready": ready,
        "hardware_ready": hardware_ready,
        "profile_target_ready": profile_target_ready,
        "supervised_apply_enabled": supervised_apply_enabled(hass),
        "profile_target_temperature": profile_target,
        "profile_target_source": profile_source,
        "profile_target_source_entity": profile_source_entity,
        "profile_target_backed": profile_backed,
        "raw_recommended_target_temperature": raw_recommended,
        "recommended_target_temperature": profile_target,
        "recommendation_entity": RECOMMENDED_TARGET_ENTITY,
        "controller_target_temperature": controller_target,
        "target_temperature_entity": target_entity,
        "temperature_entity": cloud.get("temperature_entity"),
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
    existing = get_pending_action(hass)
    if not snapshot.get("provider_selected"):
        return {**snapshot, "request_result": "provider_not_selected"}
    if existing is not None and existing.get("source") != SOURCE:
        return {
            **snapshot,
            "request_result": "pending_action_conflict",
            "conflicting_pending_action": existing,
        }
    if not snapshot["supervised_apply_enabled"]:
        return {**snapshot, "request_result": "supervised_apply_disabled"}
    if not snapshot["hardware_ready"]:
        return {**snapshot, "request_result": "not_ready"}
    if not snapshot["profile_target_ready"]:
        return {**snapshot, "request_result": "profile_target_required"}
    if snapshot["state"] == "no_change":
        return {**snapshot, "request_result": "no_change"}
    if snapshot["profile_target_temperature"] is None:
        return {**snapshot, "request_result": "profile_target_required"}

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
    requested = pending.get("profile_target_temperature")
    requested_source = pending.get("profile_target_source")
    live_profile_target = live.get("profile_target_temperature")
    live_profile_source = live.get("profile_target_source")

    if not live.get("provider_selected"):
        return {
            "supervised_confirmation_consumed": False,
            "apply_result": "provider_not_selected",
            "live_snapshot": live,
        }
    if not live.get("hardware_ready"):
        return {
            "supervised_confirmation_consumed": False,
            "apply_result": "not_ready",
            "live_snapshot": live,
        }
    if not live.get("profile_target_ready"):
        return {
            "supervised_confirmation_consumed": False,
            "apply_result": "profile_target_required",
            "live_snapshot": live,
        }
    if requested is None or live_profile_target is None:
        return {
            "supervised_confirmation_consumed": False,
            "apply_result": "profile_target_missing",
            "live_snapshot": live,
        }
    if requested_source != live_profile_source:
        return {
            "supervised_confirmation_consumed": False,
            "apply_result": "profile_source_changed",
            "live_snapshot": live,
        }
    if abs(float(requested) - float(live_profile_target)) > 0.01:
        return {
            "supervised_confirmation_consumed": False,
            "apply_result": "profile_target_changed",
            "live_snapshot": live,
        }

    device_id = int(live["device_id"])
    target = float(live_profile_target)
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
