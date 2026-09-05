"""Safe-down bridge around the BrewZilla mash-in transition.

When the brewer starts mash-in, BrewAssistant should stop treating the strike
water target as the active target.  The BrewZilla target may be lowered to the
real mash hold target while the pump remains paused for malt addition.

When the brewer confirms Mash-In Complete, BrewAssistant should also be allowed
to lower the BrewZilla target from any remaining latched strike temperature to
the real mash hold target even if Brewfather is still paused.  These are
safe-down operations, not positive heating, and they avoid leaving the unit
parked at strike target while the brewer is expected to resume Brewfather
manually.

If the brewer has marked Mash-In Started in BA, automatic completion requires a
real Brewfather pause observed after that operator boundary.  A later
paused -> running transition is treated as the Mash-In Complete confirmation.
If the exact edge is missed by a snapshot, BA may accept running only when a
post-start paused state was already observed.  A running state that pre-dates
Mash-In Started, or a target change by itself, is never enough to resume the
pump.
"""

from __future__ import annotations

from typing import Any

from homeassistant.util import dt as dt_util

from . import brewzilla_mash_in_gate as mash_in_gate
from . import brewzilla_orchestration as base

_INSTALLED = False
_ORIGINAL_APPLY = None
_ORIGINAL_START_MASH_CIRCULATION = None
_ORIGINAL_EFFECTIVE_MASH_IN_TARGET = None

_MASH_STAGE_WORDS = ("mash", "mäsk")
_MASH_HOLD_WORDS = ("hold", "mash", "mäsk")
_PAUSED_STATES = {"paused"}
_RUNNING_STATES = {"live", "running", "awaiting_snapshot"}
_BREWFATHER_STATUS_ENTITIES = (
    "sensor.brewfather_brew_tracker_status",
    "sensor.brewfather_brewtracker_status",
)
_AUTO_COMPLETE_DATA_KEY = "brewzilla_mash_in_bf_resume_auto_complete"


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _text(snapshot: dict[str, Any], *keys: str) -> str:
    return " ".join(str(snapshot.get(key) or "") for key in keys).lower()


def _runtime_state(snapshot: dict[str, Any]) -> str:
    return str(
        snapshot.get("brewday_state")
        or snapshot.get("runtime_state")
        or snapshot.get("status")
        or "idle"
    ).lower()


def _brewfather_status(hass) -> str:
    """Return the live Brewfather Brew Tracker status."""
    for entity_id in _BREWFATHER_STATUS_ENTITIES:
        state = hass.states.get(entity_id)
        if state is None:
            continue
        value = str(state.state or "").strip().lower()
        if value not in {"", "unknown", "unavailable", "none"}:
            return value
    return "unknown"


def _brewfather_transition(
    hass,
    snapshot: dict[str, Any],
) -> tuple[str | None, str, bool]:
    """Track BF status and require a pause observed after Mash-In Started."""
    data = hass.data.setdefault("brewassistant", {}).setdefault(
        _AUTO_COMPLETE_DATA_KEY,
        {
            "last_status": None,
            "mash_in_started_active_key": None,
            "seen_paused_after_mash_in_started": False,
        },
    )
    current = _brewfather_status(hass)
    previous = data.get("last_status")

    gate_state = str(snapshot.get("mash_in_gate_state") or "").strip().lower()
    gate_key = str(snapshot.get("mash_in_gate_active_key") or "")

    if gate_state == "mash_in_started":
        if data.get("mash_in_started_active_key") != gate_key:
            data["mash_in_started_active_key"] = gate_key
            data["seen_paused_after_mash_in_started"] = False
        if current in _PAUSED_STATES:
            data["seen_paused_after_mash_in_started"] = True
    else:
        data["mash_in_started_active_key"] = None
        data["seen_paused_after_mash_in_started"] = False

    seen_paused = bool(data.get("seen_paused_after_mash_in_started"))
    data["last_status"] = current
    return previous, current, seen_paused


def _runtime_allows_operator_safe_down(snapshot: dict[str, Any]) -> bool:
    state = _runtime_state(snapshot)
    return bool(
        state in {"live", "running", "paused", "awaiting_snapshot", "prepared", "awaiting_confirm"}
        and not snapshot.get("completed_runtime")
        and not snapshot.get("abort_lockout_active")
        and snapshot.get("connected", True)
        and not snapshot.get("rcl_degraded")
        and not snapshot.get("heat_strike_rcl_degraded")
        and not snapshot.get("rcl_freshness_guard_blocking")
    )


def _mash_context_active(snapshot: dict[str, Any]) -> bool:
    stage_text = _text(snapshot, "runtime_stage", "stage")
    return any(word in stage_text for word in _MASH_STAGE_WORDS)


def _current_brewfather_mash_target(snapshot: dict[str, Any]) -> tuple[float | None, str | None]:
    """Return the active BF mash target when it is safer than the strike latch.

    During the pre-mash-in pause BA may still have a requested/latched strike
    target such as 71.8°C, while Brewfather's active step has already moved to
    the real mash hold target such as 66°C.  Once the operator starts mash-in,
    that lower current BF target is the safe target to hand BrewZilla to.
    """
    if not _mash_context_active(snapshot):
        return None, None

    step_text = _text(snapshot, "runtime_step", "step", "runtime_raw_step_name", "raw_step_name")
    if step_text and not any(word in step_text for word in _MASH_HOLD_WORDS):
        return None, None

    for key in (
        "target_temperature",
        "tracker_target",
        "runtime_target_temperature",
        "runtime_tracker_target",
    ):
        value = _num(snapshot.get(key))
        if value is not None:
            return value, key
    return None, None


def _patched_effective_mash_in_target(hass, snapshot: dict[str, Any]) -> tuple[float | None, str | None, float | None, str | None]:
    assert _ORIGINAL_EFFECTIVE_MASH_IN_TARGET is not None
    effective, effective_source, next_target, next_source = _ORIGINAL_EFFECTIVE_MASH_IN_TARGET(hass, snapshot)

    requested = _num(snapshot.get("requested_target"))
    current_bf_target, current_bf_source = _current_brewfather_mash_target(snapshot)
    if current_bf_target is None:
        return effective, effective_source, next_target, next_source

    # Only override when this is a target downshift from a remaining strike or
    # boosted control target.  Raising target still follows the original logic.
    reference = requested if requested is not None else effective
    if reference is None:
        return effective, effective_source, next_target, next_source
    if current_bf_target > reference + base.TARGET_SYNC_TOLERANCE:
        return effective, effective_source, next_target, next_source
    if reference - current_bf_target <= base.TARGET_SYNC_TOLERANCE:
        return effective, effective_source, next_target, next_source

    return (
        round(current_bf_target, 1),
        "current_brewfather_mash_step",
        round(current_bf_target, 1),
        current_bf_source,
    )


def _safe_down_target(snapshot: dict[str, Any]) -> float | None:
    """Return the requested safe-down target after Mash-In Complete, if any."""
    if snapshot.get("mash_in_gate_state") != "mash_in_complete":
        return None
    if not snapshot.get("mash_in_gate_confirmed") and not snapshot.get("mash_in_resume_allowed"):
        return None
    if not _runtime_allows_operator_safe_down(snapshot):
        return None

    requested = _num(snapshot.get("requested_target"))
    applied = _num(snapshot.get("applied_target"))
    if requested is None or applied is None:
        return None

    # Only lower the target. Raising it while BF is paused remains blocked by the
    # normal orchestration guards.
    if requested > applied + base.TARGET_SYNC_TOLERANCE:
        return None
    if applied - requested <= base.TARGET_SYNC_TOLERANCE:
        return None

    return round(requested, 1)


async def _apply_safe_down_target(
    hass,
    snapshot: dict[str, Any],
    *,
    prefix: str = "mash_in_complete_safe_down",
) -> dict[str, Any] | None:
    target = _safe_down_target(snapshot)
    if target is None:
        return None

    target_changed = await base._set_number(hass, base.BREWZILLA_TARGET_NUMBER, target)
    actions = [f"{prefix}_set_target:{target}" if target_changed else f"{prefix}_target_unchanged:{target}"]
    reason = str(snapshot.get("control_reason") or "Direct production flow active")
    result = {
        **snapshot,
        "applied": True,
        "apply_result": f"{prefix}_applied",
        "actions": actions,
        "target_changed": bool(target_changed),
        "heater_started": False,
        "pump_started": False,
        "paused_target_rewind_blocked": False,
        "target_sync_needed": False if target_changed else snapshot.get("target_sync_needed"),
        "mash_in_complete_safe_down_active": True,
        "mash_in_waiting_for_brewfather_resume": _runtime_state(snapshot) == "paused",
        "orchestration_mode": "direct-control",
        "control_reason": (
            f"{reason}; Mash-In Complete safe-down: lowered BrewZilla target to "
            f"{target}°C while waiting for Brewfather to resume. Positive heating remains blocked by the normal paused/runtime guards."
        ),
        "executed_at": dt_util.utcnow().isoformat(),
    }
    hass.data.setdefault("brewassistant", {})["brewzilla_last_apply_result"] = result
    return result


async def _patched_start_mash_circulation(hass, snapshot: dict[str, Any], *, action_name: str) -> dict[str, Any]:
    assert _ORIGINAL_START_MASH_CIRCULATION is not None
    result = await _ORIGINAL_START_MASH_CIRCULATION(hass, snapshot, action_name=action_name)
    if action_name not in {"mash_in_complete", "mash_in_complete_brewfather_resume"}:
        return result

    safe_down = await _apply_safe_down_target(
        hass,
        result,
        prefix="mash_in_complete_safe_down" if action_name == "mash_in_complete" else "mash_in_complete_bf_resume_safe_down",
    )
    if safe_down is None:
        return result

    merged_actions = [*(result.get("actions") or []), *(safe_down.get("actions") or [])]
    merged = {
        **safe_down,
        "actions": merged_actions,
        "apply_result": "mash_circulation_started_safe_down_applied"
        if action_name == "mash_in_complete"
        else "mash_in_brewfather_resume_auto_complete_safe_down_applied",
        "pump_started": result.get("pump_started", False),
        "pump_utilization_changed": result.get("pump_utilization_changed", False),
        "mash_in_resume_allowed": result.get("mash_in_resume_allowed"),
        "mash_in_gate_confirmed": result.get("mash_in_gate_confirmed"),
        "mash_in_gate_confirmed_at": result.get("mash_in_gate_confirmed_at"),
    }
    hass.data.setdefault("brewassistant", {})["brewzilla_last_apply_result"] = merged
    return merged


def _auto_complete_allowed(
    snapshot: dict[str, Any],
    previous_status: str | None,
    current_status: str,
    seen_paused_after_mash_in_started: bool,
) -> tuple[bool, str]:
    if snapshot.get("mash_in_gate_state") != "mash_in_started":
        return False, "gate_not_mash_in_started"
    if current_status not in _RUNNING_STATES:
        return False, "brewfather_not_running"
    if not _runtime_allows_operator_safe_down(snapshot):
        return False, "safe_down_not_allowed"
    if not _mash_context_active(snapshot):
        return False, "mash_context_not_active"

    # Automatic completion is intentionally edge-triggered. A Brewfather
    # running state that already existed when Mash-In Started was pressed must
    # not be interpreted as the operator's later GO/Continue action.
    if not seen_paused_after_mash_in_started:
        return False, "waiting_for_brewfather_pause_after_mash_in_started"

    if previous_status in _PAUSED_STATES:
        return True, "paused_to_running_after_mash_in_started"

    # Snapshot polling can miss the exact adjacent paused -> running edge. Once
    # a post-start pause has definitely been observed, a later running state is
    # sufficient progression evidence.
    return True, "running_after_observed_mash_in_pause"


async def _apply_brewfather_resume_auto_complete(
    hass,
    snapshot: dict[str, Any],
    *,
    previous_status: str | None,
    current_status: str,
    seen_paused_after_mash_in_started: bool,
) -> dict[str, Any] | None:
    assert _ORIGINAL_START_MASH_CIRCULATION is not None
    allowed, auto_complete_reason = _auto_complete_allowed(
        snapshot,
        previous_status,
        current_status,
        seen_paused_after_mash_in_started,
    )
    if not allowed:
        return None

    confirmed_at = dt_util.utcnow().isoformat()
    store = mash_in_gate._gate_store(hass)
    store["state"] = "mash_in_complete"
    store["completed_once"] = True
    store["confirmed_at"] = confirmed_at

    await hass.services.async_call(
        "persistent_notification",
        "dismiss",
        {"notification_id": mash_in_gate.NOTIFICATION_ID},
        blocking=False,
    )

    resume_result = await _patched_start_mash_circulation(
        hass,
        snapshot,
        action_name="mash_in_complete_brewfather_resume",
    )
    actions = ["brewfather_resume_auto_mash_in_complete", *(resume_result.get("actions") or [])]
    result = {
        **resume_result,
        "actions": actions,
        "apply_result": (
            "mash_in_brewfather_resume_auto_complete_safe_down_applied"
            if resume_result.get("mash_in_complete_safe_down_active")
            else "mash_in_brewfather_resume_auto_complete_applied"
        ),
        "mash_in_gate_state": "mash_in_complete",
        "mash_in_gate_pending": False,
        "mash_in_gate_latched": False,
        "mash_in_gate_confirmed": True,
        "mash_in_gate_confirmed_at": confirmed_at,
        "mash_in_auto_completed_by_brewfather_resume": True,
        "mash_in_auto_complete_reason": auto_complete_reason,
        "mash_in_auto_complete_previous_brewfather_status": previous_status,
        "mash_in_auto_complete_current_brewfather_status": current_status,
        "mash_in_auto_complete_seen_paused_after_start": seen_paused_after_mash_in_started,
        "mash_in_waiting_for_brewfather_resume": False,
        "control_reason": (
            f"{resume_result.get('control_reason') or 'Direct production flow active'}; "
            f"Brewfather progression was confirmed after a post-start pause ({auto_complete_reason}), so BA marked Mash-In Complete automatically."
        ),
        "executed_at": dt_util.utcnow().isoformat(),
    }
    store["last_resume_result"] = {
        "apply_result": result.get("apply_result"),
        "actions": result.get("actions"),
        "pump_started": result.get("pump_started"),
        "pump_utilization_changed": result.get("pump_utilization_changed"),
        "resume_allowed": result.get("mash_in_resume_allowed"),
        "auto_completed_by_brewfather_resume": True,
        "auto_complete_reason": auto_complete_reason,
        "previous_brewfather_status": previous_status,
        "current_brewfather_status": current_status,
        "seen_paused_after_mash_in_started": seen_paused_after_mash_in_started,
        "executed_at": result.get("executed_at"),
    }
    hass.data.setdefault("brewassistant", {})["brewzilla_last_apply_result"] = result
    return result


async def _patched_apply(hass) -> dict[str, Any]:
    assert _ORIGINAL_APPLY is not None
    snapshot = base.build_orchestration_snapshot(hass)
    previous_status, current_status, seen_paused_after_start = _brewfather_transition(
        hass,
        snapshot,
    )

    auto_complete = await _apply_brewfather_resume_auto_complete(
        hass,
        snapshot,
        previous_status=previous_status,
        current_status=current_status,
        seen_paused_after_mash_in_started=seen_paused_after_start,
    )
    if auto_complete is not None:
        await base.async_record_brewday_audit_tick(hass, brewzilla_result=auto_complete)
        return auto_complete

    safe_down = await _apply_safe_down_target(
        hass,
        snapshot,
        prefix="mash_in_complete_safe_down_tick",
    )
    if safe_down is not None:
        await base.async_record_brewday_audit_tick(hass, brewzilla_result=safe_down)
        return safe_down
    return await _ORIGINAL_APPLY(hass)


def install_mash_in_complete_safe_down_guard() -> None:
    """Install safe-down handling around the mash-in transition."""
    global _INSTALLED, _ORIGINAL_APPLY, _ORIGINAL_START_MASH_CIRCULATION, _ORIGINAL_EFFECTIVE_MASH_IN_TARGET
    if _INSTALLED:
        return

    _ORIGINAL_APPLY = base.async_apply_brewzilla_target_if_allowed
    _ORIGINAL_START_MASH_CIRCULATION = mash_in_gate._start_mash_circulation
    _ORIGINAL_EFFECTIVE_MASH_IN_TARGET = mash_in_gate._effective_mash_in_target
    base.async_apply_brewzilla_target_if_allowed = _patched_apply
    mash_in_gate._start_mash_circulation = _patched_start_mash_circulation
    mash_in_gate._effective_mash_in_target = _patched_effective_mash_in_target
    _INSTALLED = True
