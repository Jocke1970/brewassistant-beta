"""Brewfather/BrewTracker hot-side ownership policy.

Brewfather may be connected and useful before it owns BrewAssistant's hot-side
runtime.  Planning is therefore a visible/ready state, while only Brewing is an
authoritative Brewday source. Fermenting is outside BrewZilla hot-side ownership.
"""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from . import brewday_runtime_core as core

PLANNING = "planning"
BREWING = "brewing"
FERMENTING = "fermenting"
INACTIVE = "inactive"


def brewfather_batch_phase(hass: HomeAssistant) -> str:
    """Return the normalized Brewfather batch phase relevant to BrewAssistant."""
    for attribute in ("brew_tracker_batch_status", "batch_status"):
        value = str(core.live_attr(hass, attribute) or "").strip().lower()
        if value in {PLANNING, BREWING, FERMENTING}:
            return value

    source_state = str(core.state(hass, core.BF_STATUS, INACTIVE) or INACTIVE).strip().lower()
    active = core.as_bool(core.live_attr(hass, "active"))
    enabled = core.as_bool(core.live_attr(hass, "enabled"))
    completed = core.as_bool(core.live_attr(hass, "completed"))

    if completed is True or enabled is False:
        return INACTIVE

    # Compatibility fallback for older BrewTracker payloads that expose no
    # batch-status attribute. An explicitly active session is treated as brewing.
    if source_state == core.BREWDAY_ACTIVE_STATUS or active is True:
        return BREWING

    return INACTIVE


def brewfather_hot_side_active(hass: HomeAssistant) -> bool:
    """Return true only while Brewfather is authoritative for hot-side brewing."""
    return brewfather_batch_phase(hass) == BREWING


def brewfather_cards_visible(hass: HomeAssistant) -> bool:
    """Return true while Brewfather should be shown as ready or active in the UI."""
    return brewfather_batch_phase(hass) in {PLANNING, BREWING}


def install_core_ownership_policy() -> None:
    """Make all existing core callers share the same authoritative predicate."""
    core.brewfather_session_active = brewfather_hot_side_active
