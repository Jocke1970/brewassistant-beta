"""Brewfather/BrewTracker hot-side ownership policy.

Brewfather may be connected and useful before it owns BrewAssistant's hot-side
runtime. Planning is therefore a visible/ready state. A batch in Brewing also
remains ready-only while BrewTracker is parked on its initial ``Start`` step;
physical hot-side ownership begins only after there is positive evidence that
the BrewTracker timer has actually started. Fermenting is outside BrewZilla
hot-side ownership.
"""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from . import brewday_runtime_core as core
from .brewday_operator_abort import brewday_operator_abort_active

PLANNING = "planning"
BREWING = "brewing"
FERMENTING = "fermenting"
INACTIVE = "inactive"

_OWNERSHIP_STATE_KEY = "brewassistant_brewfather_hot_side_ownership"
_BASE_RESOLVE_STEP_INDEX = core.resolve_step_index_from_remaining


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


def _tracker_identity(hass: HomeAssistant) -> str:
    """Return a stable identity for the current BrewTracker/batch when possible."""
    for attribute in ("tracker_id", "brew_tracker_batch_id", "batch_id"):
        value = str(core.live_attr(hass, attribute) or "").strip()
        if value:
            return value
    return "unknown"


def _start_step_marker(step: dict) -> bool:
    """Return true when Brewfather explicitly exposes its initial Start step."""
    name = str(step.get("name") or "").strip().lower()
    description = str(step.get("description") or "").strip().lower()
    return name == "start" or "starta mäsktimer" in description or "start mash timer" in description


def brewfather_tracker_prestart(hass: HomeAssistant) -> bool:
    """Return true for Brewing batches whose BrewTracker timer has not started.

    Brewfather exposes this state as an enabled/active tracker with ``paused``
    status, first stage/step, zero progress and an explicit ``Start`` current
    step. ``active: true`` alone is therefore not evidence that the timer runs.
    """
    if brewfather_batch_phase(hass) != BREWING:
        return False

    source_status = str(core.state(hass, core.BF_STATUS, INACTIVE) or INACTIVE).strip().lower()
    if source_status != "paused":
        return False

    stage = core.live_current_stage(hass)
    step = core.live_current_step(hass)
    if not stage or not step:
        return False

    stage_index = core.as_int(core.live_attr(hass, "stage_index"), -1)
    step_index = core.as_int(stage.get("step"), -1)
    stage_paused = core.as_bool(stage.get("paused")) is True
    progress = core.as_float(stage.get("progressPercent"))
    remaining = core.as_float(stage.get("remainingSeconds"))
    duration = core.as_float(stage.get("duration"))

    at_full_duration = (
        remaining is not None
        and duration is not None
        and duration > 0
        and abs(remaining - duration) <= 1.0
    )
    zero_progress = progress is None or progress <= 0.01

    return bool(
        stage_index == 0
        and step_index == 0
        and stage_paused
        and zero_progress
        and at_full_duration
        and _start_step_marker(step)
    )


def _tracker_started_evidence(hass: HomeAssistant) -> bool:
    """Return true only for positive evidence that BrewTracker has left pre-start."""
    source_status = str(core.state(hass, core.BF_STATUS, INACTIVE) or INACTIVE).strip().lower()
    if source_status == core.BREWDAY_ACTIVE_STATUS:
        return True

    stage = core.live_current_stage(hass)
    step = core.live_current_step(hass)
    if not stage:
        return False

    stage_index = core.as_int(core.live_attr(hass, "stage_index"), -1)
    step_index = core.as_int(stage.get("step"), -1)
    progress = core.as_float(stage.get("progressPercent"))
    remaining = core.as_float(stage.get("remainingSeconds"))
    duration = core.as_float(stage.get("duration"))

    if stage_index > 0 or step_index > 0:
        return True
    if progress is not None and progress > 0.01:
        return True
    if remaining is not None and duration is not None and duration > 0 and remaining < duration - 1.0:
        return True
    if step and not _start_step_marker(step):
        return True
    return False


def brewfather_hot_side_active(hass: HomeAssistant) -> bool:
    """Return true only after a Brewing BrewTracker has actually started.

    The started latch is keyed to the tracker/batch identity. It preserves
    ownership when an already-started BrewTracker is later paused, while a new
    Brewing batch parked on ``Starta mäsktimer`` remains ready-only. An explicit
    Brewday operator ABORT outranks that latch and blocks ownership until rearm.
    """
    if brewday_operator_abort_active(hass):
        return False

    if brewfather_batch_phase(hass) != BREWING:
        return False

    identity = _tracker_identity(hass)
    state = hass.data.setdefault(_OWNERSHIP_STATE_KEY, {})
    if state.get("tracker_id") != identity:
        state.clear()
        state["tracker_id"] = identity
        state["started"] = False

    if state.get("started") is True:
        return True

    if brewfather_tracker_prestart(hass):
        return False

    if _tracker_started_evidence(hass):
        state["started"] = True
        return True

    # Ambiguous Brewing payloads fail safe: visible/ready, but no hot-side owner
    # until BrewTracker publishes positive start evidence.
    return False


def brewfather_cards_visible(hass: HomeAssistant) -> bool:
    """Return true while Brewfather should be shown as ready or active in the UI."""
    return brewfather_batch_phase(hass) in {PLANNING, BREWING}


def _resolve_step_index_with_paused_live_step(
    stage: dict,
    stage_remaining: int,
    fallback: int | None,
) -> int | None:
    """Keep Brewfather's explicit live step authoritative while paused.

    The first ``Start`` step and the following ramp can share the same time
    anchor. The running-time heuristic intentionally resolves forward between
    sparse snapshots, but while paused there is no timer progression to infer,
    so advancing on an equal anchor is incorrect.
    """
    if core.as_bool(stage.get("paused")) is True and fallback is not None:
        return fallback
    return _BASE_RESOLVE_STEP_INDEX(stage, stage_remaining, fallback)


def install_core_ownership_policy() -> None:
    """Make existing core callers share authoritative Brewfather semantics."""
    core.brewfather_session_active = brewfather_hot_side_active
    core.resolve_step_index_from_remaining = _resolve_step_index_with_paused_live_step
