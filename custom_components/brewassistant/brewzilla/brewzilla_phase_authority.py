"""Authoritative physical-phase ownership for BrewZilla hot-side control.

Brewfather Play is the operator authorization for the pre-mash-in Heatstrike
phase.  Once that physical controller is active, generic Supervised Apply must
not turn every internal heat/pump modulation into a new operator confirmation.

This module deliberately sits *above* the generic supervised gate while keeping
all lower BrewZilla safety/ABORT guards intact.  It also keeps Brewday Advice in
observe-only mode while Heatstrike/Mash-In owns heat and pump.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from homeassistant.core import HomeAssistant

from ..brewday.brewday_runtime import build_brewday_runtime_snapshot
from ..const import DOMAIN
from ..supervised_apply import (
    clear_cancelled_action_from_source,
    clear_pending_action_from_source,
)
from . import brewzilla_learning as learning
from . import brewzilla_orchestration as base
from . import brewzilla_supervised_runtime_guard as supervised

_ACTIVE_RUNTIME_STATES = {"live", "running", "paused", "awaiting_snapshot"}
_PRE_MASH_IN_GATE_STATES = {"idle", "ready_for_mash_in", "mash_in_started"}
_MASH_IN_GATE_KEY = "brewzilla_mash_in_gate"
_CONTROLLER = "heatstrike_mash_in"

_ORIGINAL_APPLY: Callable[[HomeAssistant], Awaitable[dict[str, Any]]] | None = None
_ORIGINAL_BUILD: Callable[[HomeAssistant], dict[str, Any]] | None = None
_ORIGINAL_LEARNING_BUILD: Callable[[HomeAssistant], dict[str, Any]] | None = None
_INSTALLED = False


def _gate_store(hass: HomeAssistant) -> dict[str, Any]:
    value = hass.data.get(DOMAIN, {}).get(_MASH_IN_GATE_KEY)
    return value if isinstance(value, dict) else {}


def _gate_complete(hass: HomeAssistant) -> bool:
    gate = _gate_store(hass)
    return bool(
        gate.get("completed_once")
        or str(gate.get("state") or "").lower() == "mash_in_complete"
    )


def _brewtracker_pre_mash_in(hass: HomeAssistant) -> bool:
    """Return true while BrewTracker is physically before Mash-In Complete."""
    runtime = build_brewday_runtime_snapshot(hass)
    runtime_state = str(runtime.get("runtime_state") or "idle").lower()
    source = str(runtime.get("source") or "")
    stage = str(runtime.get("stage") or "").lower()
    gate = _gate_store(hass)
    gate_state = str(gate.get("state") or "idle").lower()

    return bool(
        source == "Brewfather Brew Tracker"
        and runtime_state in _ACTIVE_RUNTIME_STATES
        and ("mash" in stage or "mäsk" in stage)
        and not _gate_complete(hass)
        and gate_state in _PRE_MASH_IN_GATE_STATES
    )


def _phase_authority_active(hass: HomeAssistant, snapshot: dict[str, Any]) -> bool:
    """Return true when Play-authorized Heatstrike/Mash-In owns physical control."""
    runtime_state = str(snapshot.get("brewday_state") or "idle").lower()
    runtime_source = str(snapshot.get("runtime_source") or "")
    gate_state = str(_gate_store(hass).get("state") or "idle").lower()

    if (
        runtime_source != "Brewfather Brew Tracker"
        or runtime_state not in _ACTIVE_RUNTIME_STATES
        or snapshot.get("completed_runtime")
        or snapshot.get("abort_lockout_active")
        or _gate_complete(hass)
    ):
        return False

    # Clean Heatstrike is the authoritative pre-mash-in physical regulator.
    if snapshot.get("clean_heat_strike_active"):
        return True

    # During the dedicated Mash-In transition, keep using the same Play-granted
    # authority until Mash-In Complete.  The mash-in state machine itself is the
    # operator gate here; generic CONFIRM would only duplicate that decision.
    return gate_state in {"ready_for_mash_in", "mash_in_started"}


def _authority_diagnostics(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        **snapshot,
        "phase_authority_active": True,
        "phase_authority_controller": _CONTROLLER,
        "phase_authority_source": "brewfather_play",
        "phase_authority_requires_generic_confirmation": False,
        "has_pending_action": False,
        "pending_action": None,
        "pending_summary": None,
        "supervised_runtime_plan_pending": False,
    }


def build_orchestration_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    """Expose phase authority without stale generic confirmation UI."""
    assert _ORIGINAL_BUILD is not None
    out = _ORIGINAL_BUILD(hass)

    raw = supervised._BASE_BUILD(hass) if supervised._BASE_BUILD is not None else out
    if not _phase_authority_active(hass, raw):
        out.setdefault("phase_authority_active", False)
        return out

    clear_pending_action_from_source(hass, supervised.SOURCE)
    clear_cancelled_action_from_source(hass, supervised.SOURCE)
    out = _authority_diagnostics(out)
    # Supervised decoration may have changed this to awaiting_confirmation.
    out["safety_state"] = raw.get("safety_state")
    return out


async def async_apply_brewzilla_target_if_allowed(hass: HomeAssistant) -> dict[str, Any]:
    """Let the active physical phase regulate without per-write confirmation."""
    assert _ORIGINAL_APPLY is not None

    raw = supervised._BASE_BUILD(hass) if supervised._BASE_BUILD is not None else None
    if raw is None or not _phase_authority_active(hass, raw):
        return await _ORIGINAL_APPLY(hass)

    clear_pending_action_from_source(hass, supervised.SOURCE)
    clear_cancelled_action_from_source(hass, supervised.SOURCE)

    # _BASE_APPLY was captured immediately before Supervised Apply was installed.
    # It still contains the complete lower BrewZilla control/safety chain,
    # including explicit safe-down and ABORT final guards.
    if supervised._BASE_APPLY is None:
        return await _ORIGINAL_APPLY(hass)

    result = await supervised._BASE_APPLY(hass)
    result = _authority_diagnostics(result)
    result["phase_authority_apply_result"] = result.get("apply_result")
    hass.data.setdefault(DOMAIN, {})["brewzilla_last_apply_result"] = result
    return result


def build_brewzilla_learning_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    """Keep Advice observable but non-actionable while a physical controller owns IO."""
    assert _ORIGINAL_LEARNING_BUILD is not None
    snapshot = _ORIGINAL_LEARNING_BUILD(hass)

    if not _brewtracker_pre_mash_in(hass):
        snapshot.setdefault("controller_owned", False)
        return snapshot

    store = learning._learning_store(hass)
    store["pending"] = None

    reason = (
        "Heatstrike/Mash-In controller owns target, heat and pump until Mash-In "
        "Complete; Brewday Advice remains observation/learning only."
    )
    return {
        **snapshot,
        "mode": "observe_only_controller_owned",
        "status": "observing_controller_owned",
        "controller_owned": True,
        "controller_owner": _CONTROLLER,
        "recommendation_state": "controller_owned",
        "recommendation_id": None,
        "recommendation_kind": None,
        "recommendation_entity_id": None,
        "recommendation_current_value": None,
        "recommendation_recommended_value": None,
        "recommendation_reason": reason,
        "recommendation_action_label": None,
        "pending_recommendation": None,
        "auto_apply_allowed": False,
    }


def install_phase_authority() -> None:
    """Install physical phase authority after generic supervised wrappers."""
    global _ORIGINAL_APPLY, _ORIGINAL_BUILD, _ORIGINAL_LEARNING_BUILD, _INSTALLED
    if _INSTALLED:
        return

    _ORIGINAL_APPLY = base.async_apply_brewzilla_target_if_allowed
    _ORIGINAL_BUILD = base.build_orchestration_snapshot
    _ORIGINAL_LEARNING_BUILD = learning.build_brewzilla_learning_snapshot

    base.async_apply_brewzilla_target_if_allowed = async_apply_brewzilla_target_if_allowed
    base.build_orchestration_snapshot = build_orchestration_snapshot
    learning.build_brewzilla_learning_snapshot = build_brewzilla_learning_snapshot
    _INSTALLED = True
