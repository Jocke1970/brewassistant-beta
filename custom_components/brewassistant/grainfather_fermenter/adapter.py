"""Read-only Grainfather fermentation-device discovery for BrewAssistant.

Phase 1 intentionally performs no service calls. It normalizes the public
Home Assistant state surface exposed by ``fidley/grainfather_integration`` so
future Grainfather fermenter control can be added behind BrewAssistant's
provider and Supervised Apply boundaries after live hardware validation.
"""

from __future__ import annotations

from typing import Any

EXTERNAL_DOMAIN = "grainfather"
ENTITY_TYPE_ATTRIBUTE = "grainfather_entity_type"
FERMENTATION_DEVICE_TYPE = "fermentation_device"
BREW_SESSION_TYPE = "brew_session"
PROFILE_TARGET_SERVICE = "adjust_current_step_temperature"
INVALID_STATES = {"unknown", "unavailable", "none", ""}


def _state_float(state: Any) -> float | None:
    """Return a numeric HA state without inventing a fallback value."""
    if state is None:
        return None
    raw = str(getattr(state, "state", "")).strip().lower()
    if raw in INVALID_STATES:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _optional_bool(value: Any) -> bool | None:
    """Normalize optional bool-like upstream attributes conservatively."""
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "on"}:
        return True
    if text in {"false", "0", "no", "off"}:
        return False
    return None


def _id_key(value: Any) -> str | None:
    """Normalize an upstream id for cross-entity matching."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _sensor_states(hass: Any) -> list[Any]:
    """Return sensor states without depending on guessed entity ids."""
    return [state for state in hass.states.async_all() if state.entity_id.startswith("sensor.")]


def _upstream_states(hass: Any, entity_type: str) -> list[Any]:
    """Discover Grainfather states by the integration's public type marker."""
    return [
        state
        for state in _sensor_states(hass)
        if state.attributes.get(ENTITY_TYPE_ATTRIBUTE) == entity_type
    ]


def _is_temperature_state(state: Any) -> bool:
    attrs = state.attributes
    entity_id = state.entity_id.lower()
    device_class = str(attrs.get("device_class") or "").lower()
    unit = str(attrs.get("unit_of_measurement") or "").lower()
    return (
        device_class == "temperature"
        or unit in {"°c", "c", "°f", "f"}
        or entity_id.endswith("_temperature")
        or "temperature" in entity_id
    )


def _is_gravity_state(state: Any) -> bool:
    entity_id = state.entity_id.lower()
    friendly_name = str(state.attributes.get("friendly_name") or "").lower()
    return "gravity" in entity_id or "gravity" in friendly_name


def _session_snapshots(hass: Any) -> dict[str, dict[str, Any]]:
    sessions: dict[str, dict[str, Any]] = {}
    for state in _upstream_states(hass, BREW_SESSION_TYPE):
        attrs = state.attributes
        brew_session_id = attrs.get("brew_session_id")
        key = _id_key(brew_session_id)
        if key is None:
            continue
        sessions[key] = {
            "entity_id": state.entity_id,
            "brew_session_id": brew_session_id,
            "recipe_id": attrs.get("recipe_id"),
            "batch_number": attrs.get("batch_number"),
            "session_name": attrs.get("session_name"),
            "recipe_name": attrs.get("recipe_name"),
            "status": attrs.get("status", state.state),
            "fermentation_device_ids": attrs.get("fermentation_device_ids"),
            "fermentation_steps": attrs.get("fermentation_steps"),
        }
    return sessions


def _device_snapshots(hass: Any) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}

    for state in _upstream_states(hass, FERMENTATION_DEVICE_TYPE):
        attrs = state.attributes
        device_id = attrs.get("device_id")
        key = _id_key(device_id)
        if key is None:
            continue

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
                "temperature_entity_id": None,
                "gravity": None,
                "gravity_entity_id": None,
                "entity_ids": [],
            },
        )

        if state.entity_id not in device["entity_ids"]:
            device["entity_ids"].append(state.entity_id)

        # Keep metadata fresh when multiple sensors represent the same device.
        for source_key in (
            "linked_brew_session_id",
            "linked_brew_session_name",
            "last_heard",
        ):
            if attrs.get(source_key) is not None:
                device[source_key] = attrs.get(source_key)
        controller_linked = _optional_bool(attrs.get("is_controller_linked"))
        if controller_linked is not None:
            device["is_controller_linked"] = controller_linked

        if _is_temperature_state(state):
            device["temperature"] = _state_float(state)
            device["temperature_entity_id"] = state.entity_id
        if _is_gravity_state(state):
            device["gravity"] = _state_float(state)
            device["gravity_entity_id"] = state.entity_id

    return sorted(grouped.values(), key=lambda item: str(item.get("device_id")))


def _select_candidate(
    devices: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, str]:
    """Select only when the upstream state gives an unambiguous candidate."""
    controller_linked = [
        device for device in devices if device.get("is_controller_linked") is True
    ]

    if len(controller_linked) == 1:
        return controller_linked[0], "single_controller_linked_device"
    if len(controller_linked) > 1:
        return None, "multiple_controller_linked_devices"
    if len(devices) == 1:
        return devices[0], "single_device_read_only"
    if len(devices) > 1:
        return None, "multiple_unverified_devices"
    return None, "no_fermentation_devices"


def _integration_configured(hass: Any) -> bool:
    try:
        return bool(hass.config_entries.async_entries(EXTERNAL_DOMAIN))
    except (AttributeError, TypeError):
        return False


def build_grainfather_fermenter_snapshot(hass: Any) -> dict[str, Any]:
    """Build a fail-passive Grainfather fermentation-provider snapshot."""
    devices = _device_snapshots(hass)
    sessions = _session_snapshots(hass)
    selected_device, selection_reason = _select_candidate(devices)

    integration_configured = _integration_configured(hass)
    integration_available = integration_configured or bool(devices) or bool(sessions)
    profile_target_service_available = hass.services.has_service(
        EXTERNAL_DOMAIN, PROFILE_TARGET_SERVICE
    )

    linked_session = None
    if selected_device is not None:
        linked_id = _id_key(selected_device.get("linked_brew_session_id"))
        if linked_id is not None:
            linked_session = sessions.get(linked_id)

    controller_verified = bool(
        selected_device is not None
        and selected_device.get("is_controller_linked") is True
    )
    session_status = str((linked_session or {}).get("status") or "").strip().lower()
    recipe_id = (linked_session or {}).get("recipe_id")

    future_supervised_target_ready = bool(
        controller_verified
        and linked_session is not None
        and recipe_id is not None
        and session_status == "fermenting"
        and profile_target_service_available
    )

    if not integration_available:
        status = "integration_missing"
        reason = "grainfather_integration_not_detected"
    elif not devices:
        status = "awaiting_fermentation_device"
        reason = "no_fermentation_device_state"
    elif selection_reason == "multiple_controller_linked_devices":
        status = "ambiguous_device"
        reason = selection_reason
    elif selected_device is None:
        status = "awaiting_device_selection"
        reason = selection_reason
    elif not controller_verified:
        status = "ready_read_only"
        reason = "device_discovered_but_controller_not_verified"
    elif linked_session is None:
        status = "controller_unlinked"
        reason = "controller_has_no_matching_brew_session"
    elif future_supervised_target_ready:
        status = "ready_supervised_candidate"
        reason = "live_prerequisites_visible_but_control_still_disabled"
    else:
        status = "ready_read_only"
        reason = "controller_detected_but_supervised_prerequisites_incomplete"

    return {
        "status": status,
        "reason": reason,
        "source": "fidley/grainfather_integration",
        "control_mode": "read_only",
        "integration_configured": integration_configured,
        "integration_available": integration_available,
        "device_count": len(devices),
        "session_count": len(sessions),
        "selection_reason": selection_reason,
        "selected_device": selected_device,
        "linked_session": linked_session,
        "temperature": (selected_device or {}).get("temperature"),
        "temperature_entity_id": (selected_device or {}).get("temperature_entity_id"),
        "gravity": (selected_device or {}).get("gravity"),
        "gravity_entity_id": (selected_device or {}).get("gravity_entity_id"),
        "controller_linked": controller_verified,
        "profile_target_service": f"{EXTERNAL_DOMAIN}.{PROFILE_TARGET_SERVICE}",
        "profile_target_service_available": profile_target_service_available,
        "future_supervised_target_ready": future_supervised_target_ready,
        "model_verified": False,
        "model_note": (
            "Current upstream Home Assistant attributes identify a Grainfather "
            "fermentation device/controller relationship but do not prove that "
            "the selected device is specifically a GF30."
        ),
        "devices": devices,
        "sessions": list(sessions.values()),
    }
