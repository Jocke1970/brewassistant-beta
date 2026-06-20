"""BrewZilla orchestration helpers for BA-owned desired values."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .brewzilla_owned_control import clear_owned_control, get_owned_control


def owned_control_overlay(
    hass: HomeAssistant,
    *,
    runtime_active: bool,
    completed_runtime: bool,
    abort_lockout_active: bool,
    desired_heat_utilization: float | None,
    desired_pump_utilization: float | None,
) -> dict[str, Any]:
    """Return BA-owned desired utilization overlay diagnostics.

    ABORT and completed runtime clear the volatile owner store. Otherwise, when
    runtime is active, a stored BA-owned desired value overlays the stage strategy.
    """
    if abort_lockout_active:
        owned = clear_owned_control(hass, reason="abort_lockout")
    elif completed_runtime:
        owned = clear_owned_control(hass, reason="completed_runtime")
    else:
        owned = get_owned_control(hass)

    active = bool(owned.get("active") and runtime_active and not completed_runtime and not abort_lockout_active)
    owned_heat = owned.get("desired_heat_utilization") if active else None
    owned_pump = owned.get("desired_pump_utilization") if active else None

    return {
        "ba_owned_control_active": active,
        "ba_owned_control_source": owned.get("source"),
        "ba_owned_control_recommendation_id": owned.get("recommendation_id"),
        "ba_owned_desired_heat_utilization": owned_heat,
        "ba_owned_desired_pump_utilization": owned_pump,
        "ba_owned_control_created_at": owned.get("created_at"),
        "ba_owned_control_updated_at": owned.get("updated_at"),
        "ba_owned_control_cleared_at": owned.get("cleared_at"),
        "ba_owned_control_clear_reason": owned.get("clear_reason"),
        "desired_heat_utilization": owned_heat if owned_heat is not None else desired_heat_utilization,
        "desired_pump_utilization": owned_pump if owned_pump is not None else desired_pump_utilization,
    }


def utilization_action_label(
    *,
    owned_active: bool,
    kind: str,
    value: float,
) -> str:
    """Return action log label for utilization writes."""
    if owned_active:
        return f"ba_owned_reassert_{kind}_utilization:{value}"
    return f"set_{kind}_utilization:{value}"
