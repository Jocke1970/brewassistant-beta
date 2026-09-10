"""Fail-passive Grainfather fermentation-device discovery/normalization backend.

The initial target is the Grainfather GF30 Conical Fermenter through the external
``grainfather`` Home Assistant integration. This backend consumes only Home
Assistant state/service surfaces exposed by that integration. It does not import
upstream code and it never sends commands in phase 1.
"""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant, State

EXTERNAL_DOMAIN = "grainfather"
ENTITY_TYPE_ATTRIBUTE = "grainfather_entity_type"
FERMENTATION_DEVICE_TYPE = "fermentation_device"
BREW_SESSION_TYPE = "brew_session"
PROFILE_TARGET_SERVICE = "adjust_current_step_temperature"
INVALID_STATES = {"unknown", "unavailable", "none", ""}


def _state_float(state: State | None) -> float | None:
    """Return a numeric state without inventing a fallback value."""
    if state is None or str(state.state).strip().lower() in INVALID_STATES:
        return None
    try:
        return float(str(state.state).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _optional_bool(value: Any) -> bool | None:
    """Normalize an optional boolean attribute."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "on", "yes", "1"}:
            return True
        if normalized in {"false", "off", "no", "0"}:
            return False
    return None


def _sensor_states(hass: HomeAssistant) -> list[State]:
    return [state for state in hass.states.async_all() if state.entity_id.startswith("sensor.")]


def _upstream_states(hass: HomeAssistant, entity_type: str) -> list[State]:
    """Find Grainfather states by public attributes instead of guessed entity IDs."""
    return [
        state
        for state in _sensor_states(hass)
        if state.attributes.get(ENTITY_TYPE_ATTRIBUTE) == entity_type
    ]


def _is_temperature_state(state: State) -> bool:
    attrs = state.attributes
    device_class = str(attrs.get("device_class") or "").lower()
    unit = str(attrs.get("unit_of_measurement") or "")
    return (
        device_class == "temperature"
        or unit in {"°C", "°F", "C", "F"}
        or state.entity_id.endswith("_temperature")
    )


def _is_gravity_state(state: State) -> bool:
    return "gravity" in state.entity_id.lower()


def _session_snapshots(hass: HomeAssistant) -> dict[str, dict[str, Any]]:
    sessions: dict[str, dict[str, Any]] = {}
    for state in _upstream_states(hass, BREW_SESSION_TYPE):
        attrs = state.attributes
        brew_session_id = attrs.get("brew_session_id")
        if brew_session_id is None:
            continue
        sessions[str(brew_session_id)] = {
            "entity_id": state.entity_id,
            "brew_session_id": brew_session_id,
            "recipe_id": attrs.get("recipe_id"),
            "batch_number": attrs.get("batch_number"),
            "session_name": attrs.get("session_name"),
            "recipe_name": attrs.get("recipe_name"),
            "status": attrs.get("status"),
            "fermentation_device_ids": list(attrs.get("fermentation_device_ids") or []),
            "fermentation_steps": list(attrs.get("fermentation_steps") or []),
        }
    return sessions


def _device_snapshots(hass: HomeAssistant) -> list[dict[str, Any]]:
    """Group upstream temperature/gravity entities by Grainfather device ID."""
    grouped: dict[str, dict[str, Any]] = {}
    for state in _upstream_states(hass, FERMENTATION_DEVICE_TYPE):
        attrs = state.attributes
        device_id = attrs.get("device_id")
        if device_id is None:
            continue
        key = str(device_id)
        device = grouped.setdefault(
            key,
            {
                "device_id": device_id,
                "name": attrs.get("friendly_name"),
                "linked_brew_session_id": attrs.get("linked_brew_session_id"),
                "linked_brew_session_name": attrs.get("linked_brew_session_name"),
                "last_heard": attrs.get("last_heard"),
                "is_controller_linked": _optional_bool(attrs.get("is_controller_linked")),
                "temperature": None,
                "temperature_entity": None,
                "gravity": None,
                "gravity_entity": None,
            },
        )

        for attr_key in ("linked_brew_session_id", "linked_brew_session_name", "last_heard"):
            if attrs.get(attr_key) is not None:
                device[attr_key] = attrs.get(attr_key)
        controller_linked = _optional_bool(attrs.get("is_controller_linked"))
        if controller_linked is not None:
            device["is_controller_linked"] = controller_linked

        if _is_temperature_state(state):
            device["temperature"] = _state_float(state)
            device["temperature_entity"] = state.entity_id
        elif _is_gravity_state(state):
            device["gravity"] = _state_float(state)
            device["gravity_entity"] = state.entity_id

    return sorted(grouped.values(), key=lambda item: str(item.get("device_id")))


def _select_candidate(devices: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, str]:
    """Select only an unambiguous fermentation-controller candidate."""
    controllers = [device for device in devices if device.get("is_controller_linked") is True]
    if len(controllers) == 1:
        return controllers[0], "single_controller_linked_device"
    if len(controllers) > 1:
        return None, "multiple_controller_linked_devices"
    if len(devices) == 1:
        return devices[0], "single_device_read_only"
    if devices:
        return None, "multiple_devices_no_unique_controller"
    return None, "no_fermentation_devices"


def build_grainfather_fermenter_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    """Build normalized Grainfather fermenter discovery diagnostics.

    The current upstream attributes identify fermentation devices and controller
    linkage, but do not prove that a controller-linked device is specifically a
    GF30. The backend therefore reports model_verified=False until live hardware
    provides a stable identifier.
    """
    sessions = _session_snapshots(hass)
    devices = _device_snapshots(hass)
    selected, selection_reason = _select_candidate(devices)
    integration_configured = bool(hass.config_entries.async_entries(EXTERNAL_DOMAIN))
    integration_available = integration_configured or bool(devices) or bool(sessions)
    profile_target_service_available = hass.services.has_service(
        EXTERNAL_DOMAIN,
        PROFILE_TARGET_SERVICE,
    )

    linked_session: dict[str, Any] | None = None
    if selected is not None and selected.get("linked_brew_session_id") is not None:
        linked_session = sessions.get(str(selected["linked_brew_session_id"]))

    controller_verified = selected is not None and selected.get("is_controller_linked") is True
    future_supervised_target_ready = bool(
        controller_verified
        and linked_session
        and linked_session.get("recipe_id") is not None
        and linked_session.get("status") == "fermenting"
        and profile_target_service_available
    )

    if not integration_available:
        status = "integration_missing"
        reason = "Grainfather integration is not configured or exposing states"
    elif not devices:
        status = "awaiting_fermentation_device"
        reason = "Grainfather is available but no fermentation device is exposed"
    elif selection_reason in {"multiple_controller_linked_devices", "multiple_devices_no_unique_controller"}:
        status = "ambiguous_device"
        reason = "More than one possible Grainfather fermentation device is present"
    elif selected is None:
        status = "awaiting_device_selection"
        reason = "No safe Grainfather fermentation-device candidate could be selected"
    elif not controller_verified:
        status = "ready_read_only"
        reason = "Telemetry is available but controller linkage is not verified"
    elif linked_session is None:
        status = "controller_unlinked"
        reason = "Controller telemetry is available but no matching brew session is exposed"
    elif future_supervised_target_ready:
        status = "ready_supervised_candidate"
        reason = "Telemetry and profile-target service are available; control remains disabled in backend v1"
    else:
        status = "ready_read_only"
        reason = "Controller/session telemetry is available; supervised target prerequisites are incomplete"

    return {
        "status": status,
        "reason": reason,
        "source": "grainfather_integration_state_surface",
        "control_mode": "read_only",
        "integration_configured": integration_configured,
        "integration_available": integration_available,
        "device_count": len(devices),
        "session_count": len(sessions),
        "selection_reason": selection_reason,
        "selected_device": selected,
        "linked_session": linked_session,
        "temperature": selected.get("temperature") if selected else None,
        "temperature_entity": selected.get("temperature_entity") if selected else None,
        "gravity": selected.get("gravity") if selected else None,
        "gravity_entity": selected.get("gravity_entity") if selected else None,
        "controller_linked": selected.get("is_controller_linked") if selected else None,
        "profile_target_service": f"{EXTERNAL_DOMAIN}.{PROFILE_TARGET_SERVICE}",
        "profile_target_service_available": profile_target_service_available,
        "future_supervised_target_ready": future_supervised_target_ready,
        "devices": devices,
        "sessions": list(sessions.values()),
        "model_verified": False,
        "model_note": "Current upstream Home Assistant attributes do not prove that the selected device is specifically a GF30.",
    }
