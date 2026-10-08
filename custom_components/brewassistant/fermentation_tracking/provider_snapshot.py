"""Normalized read-only fermentation provider snapshot.

The process target belongs to fermentation_tracking. This module only reads
already-published Home Assistant states for the selected physical provider. It
must never create pending actions or invoke hardware/service paths.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from homeassistant.core import HomeAssistant

from .models import (
    PROVIDER_FERMENTATION_CHAMBER,
    PROVIDER_GRAINFATHER_GF30,
    PROVIDER_LABELS,
)
from .storage import get_runtime

CHAMBER_SUPERVISOR_ENTITY = (
    "switch.brewassistant_fermentation_climate_supervisor_enabled"
)
GF30_TARGET_STATE_ENTITY = "sensor.brewassistant_gf30_target_apply_state"
INVALID_STATES = {"unknown", "unavailable", "none", ""}


def _age_seconds(iso_value: Any) -> float | None:
    if not iso_value:
        return None
    try:
        observed = datetime.fromisoformat(str(iso_value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=timezone.utc)
    age = (datetime.now(timezone.utc) - observed.astimezone(timezone.utc)).total_seconds()
    return round(max(0.0, age), 1)


def _state_snapshot(hass: HomeAssistant, entity_id: str) -> dict[str, Any]:
    state = hass.states.get(entity_id)
    if state is None:
        return {
            "entity_id": entity_id,
            "available": False,
            "state": None,
            "attributes": {},
        }
    state_value = str(state.state)
    return {
        "entity_id": entity_id,
        "available": state_value.lower() not in INVALID_STATES,
        "state": state_value,
        "attributes": dict(state.attributes),
    }


def build_fermentation_provider_snapshot(
    hass: HomeAssistant,
    tracking: dict[str, Any],
) -> dict[str, Any]:
    """Return one normalized, side-effect-free provider snapshot."""
    runtime = get_runtime(hass)
    provider = runtime.fermentation_provider
    label = PROVIDER_LABELS.get(provider, provider)

    common = {
        "provider_id": provider,
        "provider_label": label,
        "provider_selected": True,
        "beer_temperature_c": tracking.get("current_temperature_c"),
        "beer_temperature_source": tracking.get("temperature_source"),
        "beer_temperature_age_s": _age_seconds(tracking.get("temperature_observed_at")),
        "desired_beer_target_c": tracking.get("recommended_temperature_c"),
        "desired_beer_target_source": tracking.get("recommended_temperature_source"),
        "physical_target_c": None,
        "physical_target_source": None,
        "target_delta_c": None,
        "heating_state": None,
        "cooling_state": None,
        "temperature_control_state": None,
        "supervised_apply_state": None,
        "safe_to_propose_target": False,
        "provider_ready": False,
        "provider_status": "unknown",
        "reason": "provider telemetry unavailable",
    }

    if provider == PROVIDER_FERMENTATION_CHAMBER:
        source = _state_snapshot(hass, CHAMBER_SUPERVISOR_ENTITY)
        attrs = source["attributes"]
        provider_selected = attrs.get("provider_selected") is True
        ready = bool(
            provider_selected
            and attrs.get("ready") is True
            and attrs.get("scope_active") is True
        )
        return {
            **common,
            "provider_selected": provider_selected,
            "provider_ready": ready,
            "provider_status": attrs.get("status") or source["state"],
            "physical_target_c": attrs.get("controller_target_temperature"),
            "physical_target_source": attrs.get("controller_entity"),
            "target_delta_c": attrs.get("target_delta"),
            "temperature_control_state": attrs.get("demand"),
            "supervised_apply_state": (
                "pending_confirmation"
                if attrs.get("has_pending_action")
                else attrs.get("action")
            ),
            "safe_to_propose_target": bool(
                provider_selected
                and attrs.get("enabled") is True
                and attrs.get("ready") is True
                and attrs.get("scope_active") is True
                and attrs.get("supervised_apply_enabled") is True
            ),
            "reason": attrs.get("reason"),
            "provider_details": source,
        }

    if provider == PROVIDER_GRAINFATHER_GF30:
        source = _state_snapshot(hass, GF30_TARGET_STATE_ENTITY)
        attrs = source["attributes"]
        provider_selected = attrs.get("provider_selected") is True
        return {
            **common,
            "provider_selected": provider_selected,
            "provider_ready": bool(provider_selected and attrs.get("ready") is True),
            "provider_status": source["state"],
            "physical_target_c": attrs.get("controller_target_temperature"),
            "physical_target_source": attrs.get("target_temperature_entity"),
            "target_delta_c": attrs.get("target_delta"),
            "temperature_control_state": attrs.get("controller_state"),
            "supervised_apply_state": (
                "pending_confirmation"
                if attrs.get("has_pending_action")
                else source["state"]
            ),
            "safe_to_propose_target": bool(
                provider_selected
                and attrs.get("hardware_ready") is True
                and attrs.get("profile_target_ready") is True
                and attrs.get("supervised_apply_enabled") is True
            ),
            "reason": attrs.get("reason"),
            "provider_details": source,
        }

    return {
        **common,
        "provider_selected": False,
        "provider_status": "invalid_selection",
        "reason": f"unsupported fermentation provider {provider}",
    }
