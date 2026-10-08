"""Normalized read-only fermentation provider snapshot.

The process target belongs to fermentation_tracking. This module only normalizes
the currently selected physical provider for UI and outbound telemetry.
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


def build_fermentation_provider_snapshot(
    hass: HomeAssistant,
    tracking: dict[str, Any],
) -> dict[str, Any]:
    """Return one normalized snapshot for the selected physical provider."""
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
        "reason": "provider snapshot unavailable",
    }

    if provider == PROVIDER_FERMENTATION_CHAMBER:
        from ..fermentation_chamber.supervisor import (
            build_fermentation_climate_supervisor_snapshot,
        )

        chamber = build_fermentation_climate_supervisor_snapshot(hass)
        pending = bool(chamber.get("has_pending_action"))
        return {
            **common,
            "provider_ready": bool(
                chamber.get("provider_selected")
                and chamber.get("ready")
                and chamber.get("scope_active")
            ),
            "provider_status": chamber.get("status"),
            "physical_target_c": chamber.get("controller_target_temperature"),
            "physical_target_source": chamber.get("controller_entity"),
            "target_delta_c": chamber.get("target_delta"),
            "temperature_control_state": chamber.get("demand"),
            "supervised_apply_state": (
                "pending_confirmation" if pending else chamber.get("action")
            ),
            "safe_to_propose_target": bool(
                chamber.get("provider_selected")
                and chamber.get("enabled")
                and chamber.get("ready")
                and chamber.get("scope_active")
                and chamber.get("supervised_apply_enabled")
            ),
            "reason": chamber.get("reason"),
            "provider_details": chamber,
        }

    if provider == PROVIDER_GRAINFATHER_GF30:
        from ..grainfather_fermenter.supervised_target import (
            build_gf30_target_adapter_snapshot,
        )

        gf30 = build_gf30_target_adapter_snapshot(hass)
        return {
            **common,
            "provider_ready": bool(gf30.get("ready")),
            "provider_status": gf30.get("state"),
            "physical_target_c": gf30.get("controller_target_temperature"),
            "physical_target_source": gf30.get("target_temperature_entity"),
            "target_delta_c": gf30.get("target_delta"),
            "temperature_control_state": gf30.get("controller_state"),
            "supervised_apply_state": (
                "pending_confirmation"
                if gf30.get("has_pending_action")
                else gf30.get("state")
            ),
            "safe_to_propose_target": bool(
                gf30.get("provider_selected")
                and gf30.get("hardware_ready")
                and gf30.get("profile_target_ready")
                and gf30.get("supervised_apply_enabled")
            ),
            "reason": gf30.get("reason"),
            "provider_details": gf30,
        }

    return {
        **common,
        "provider_selected": False,
        "provider_status": "invalid_selection",
        "reason": f"unsupported fermentation provider {provider}",
    }
