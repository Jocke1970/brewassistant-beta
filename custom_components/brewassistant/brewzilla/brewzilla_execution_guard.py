"""BrewZilla runtime execution-desync guard and actionable safety state."""

from __future__ import annotations

from typing import Any

from . import brewzilla_orchestration as _base

DATA_KEY = "brewzilla_execution_guard"
_BASE_BUILD_ORCHESTRATION_SNAPSHOT = None
_INSTALLED = False


def _runtime_state(snapshot: dict[str, Any]) -> str:
    return str(snapshot.get("brewday_state") or "idle").lower()


def _runtime_active(snapshot: dict[str, Any]) -> bool:
    return _base._runtime_active(_runtime_state(snapshot))


def _target(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return round(float(value), 1)
    except (TypeError, ValueError):
        return None


def _runtime_identity(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Return the normalized execution identity BA expects BrewZilla to follow."""
    return {
        "source": snapshot.get("runtime_source"),
        "stage": snapshot.get("runtime_stage"),
        "step": snapshot.get("runtime_step"),
        "raw_step_name": snapshot.get("runtime_raw_step_name"),
        "raw_step_index": snapshot.get("runtime_raw_step_index"),
        "resolved_step_index": snapshot.get("runtime_resolved_step_index"),
        "target": _target(snapshot.get("requested_target")),
    }


def _identity_key(identity: dict[str, Any]) -> tuple[Any, ...]:
    """Return a stable key that changes when BF/Manual runtime advances."""
    step_index = identity.get("resolved_step_index")
    if step_index is None:
        step_index = identity.get("raw_step_index")
    return (
        identity.get("source"),
        step_index,
        identity.get("stage"),
        identity.get("step"),
        identity.get("target"),
    )


def _same_identity(left: dict[str, Any] | None, right: dict[str, Any] | None) -> bool:
    if not left or not right:
        return False
    return _identity_key(left) == _identity_key(right)


def _store(hass) -> dict[str, Any]:
    return hass.data.setdefault("brewassistant", {}).setdefault(DATA_KEY, {})


def _clear_store(hass, reason: str) -> None:
    store = _store(hass)
    store.clear()
    store["last_clear_reason"] = reason


def _should_track_block(snapshot: dict[str, Any]) -> bool:
    return bool(
        _runtime_active(snapshot)
        and not snapshot.get("completed_runtime")
        and not snapshot.get("abort_lockout_active")
        and snapshot.get("rcl_freshness_guard_blocking")
    )


def _sync_execution_guard(hass, snapshot: dict[str, Any]) -> dict[str, Any]:
    guarded = dict(snapshot)
    store = _store(hass)
    identity = _runtime_identity(guarded)

    if guarded.get("abort_lockout_active"):
        _clear_store(hass, "abort_lockout")
        return guarded

    if not _runtime_active(guarded) or guarded.get("completed_runtime"):
        _clear_store(hass, "runtime_inactive_or_completed")
        return guarded

    blocked_identity = store.get("blocked_identity")
    desync_active = bool(store.get("execution_desync_active"))
    current_blocking = _should_track_block(guarded)

    if desync_active:
        if _same_identity(identity, blocked_identity):
            # Same step came back; keep the gate until a fresh, non-blocked snapshot is seen.
            if not current_blocking:
                _clear_store(hass, "desync_resolved_same_step_fresh")
                return guarded
        return _apply_execution_desync(guarded, store, identity)

    if blocked_identity and not _same_identity(identity, blocked_identity):
        store["execution_desync_active"] = True
        store["desync_identity"] = identity
        store["desync_reason"] = (
            "Runtime advanced while BrewZilla execution was blocked or unverified."
        )
        return _apply_execution_desync(guarded, store, identity)

    if current_blocking:
        if not blocked_identity:
            store["blocked_identity"] = identity
            store["blocked_reason"] = guarded.get("rcl_freshness_guard_reason") or guarded.get("control_reason")
            store["blocked_temperature_age_seconds"] = guarded.get("rcl_freshness_age_seconds")
            store["blocked_runtime_remaining_seconds"] = guarded.get("runtime_step_remaining_seconds")
        return guarded

    if blocked_identity:
        _clear_store(hass, "blocked_step_recovered_before_advance")

    return guarded


def _apply_execution_desync(
    snapshot: dict[str, Any],
    store: dict[str, Any],
    current_identity: dict[str, Any],
) -> dict[str, Any]:
    blocked_identity = store.get("blocked_identity") or {}
    reason = store.get("desync_reason") or "Runtime execution desync detected."

    snapshot.update(
        {
            "execution_desync": True,
            "execution_desync_active": True,
            "execution_desync_reason": reason,
            "execution_desync_blocked_identity": blocked_identity,
            "execution_desync_current_identity": current_identity,
            "execution_desync_blocked_step": blocked_identity.get("step"),
            "execution_desync_current_step": current_identity.get("step"),
            "execution_desync_blocked_target": blocked_identity.get("target"),
            "execution_desync_current_target": current_identity.get("target"),
            "operator_action_required": True,
            "target_sync_needed": False,
            "heating_needed": False,
            "heater_action_needed": False,
            "heater_stop_needed": False,
            "pump_action_needed": False,
            "pump_stop_needed": False,
            "heat_utilization_action_needed": False,
            "pump_utilization_action_needed": False,
            "ba_owned_reassert_action_needed": False,
            "can_apply_target": False,
            "orchestration_mode": "blocked",
            "control_reason": reason,
            "safety_state": "execution_desync",
        }
    )
    return snapshot


def _safety_state(snapshot: dict[str, Any]) -> str:
    state = _runtime_state(snapshot)
    if snapshot.get("execution_desync_active") or snapshot.get("execution_desync"):
        return "execution_desync"
    if snapshot.get("abort_lockout_active"):
        return "abort_lockout"
    if state in {"idle", "inactive", "unknown", "unavailable", "none", ""}:
        return "idle"
    if snapshot.get("completed_runtime"):
        return "completed"
    if snapshot.get("rcl_freshness_guard_blocking"):
        return "rcl_stale_blocked"
    if snapshot.get("rcl_freshness_guard_active"):
        return "rcl_stale_warning"
    if state == "paused":
        return "paused"
    if snapshot.get("paused_control_blocked"):
        return "paused_blocked"
    if snapshot.get("target_sync_needed"):
        return "target_desync"
    if snapshot.get("orchestration_mode") == "direct-control":
        return "action_ready"
    return "ready"


def _apply_actionable_safety_state(snapshot: dict[str, Any]) -> dict[str, Any]:
    guarded = dict(snapshot)
    guarded["safety_mode"] = "operator_supervised"
    guarded["safety_state"] = _safety_state(guarded)
    return guarded


def build_orchestration_snapshot(hass) -> dict[str, Any]:
    assert _BASE_BUILD_ORCHESTRATION_SNAPSHOT is not None
    snapshot = _BASE_BUILD_ORCHESTRATION_SNAPSHOT(hass)
    snapshot = _sync_execution_guard(hass, snapshot)
    return _apply_actionable_safety_state(snapshot)


def install_execution_guard() -> None:
    global _BASE_BUILD_ORCHESTRATION_SNAPSHOT, _INSTALLED
    if _INSTALLED:
        return
    _BASE_BUILD_ORCHESTRATION_SNAPSHOT = _base.build_orchestration_snapshot
    _base.build_orchestration_snapshot = build_orchestration_snapshot
    _INSTALLED = True
