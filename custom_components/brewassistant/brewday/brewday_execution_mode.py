"""Brewday execution mode and retained recipe-context helpers.

Execution mode may change without changing batch identity. External sources are
cached while healthy so a transient RCL/BrewTracker outage can fall back to
Manual Brewing without discarding the recipe context.

The cache is runtime-local in this first implementation. While HA remains
running, retained external context is converted into the existing ManualPlan
engine so the operator can continue the same batch locally. A full Home
Assistant restart without a trustworthy external source remains fail-closed.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from ..const import DOMAIN

MANUAL_BREWING = "Manual Brewing"
BREWFATHER_BREWING = "Brewfather Brewing"
RCL_BREWING = "RCL Brewing"
BREWDAY_MODES = (MANUAL_BREWING, BREWFATHER_BREWING, RCL_BREWING)

DATA_KEY = "brewday_execution_mode_runtime"
STORAGE_KEY = "brewassistant_brewday_recipe_context"
STORAGE_VERSION = 1
STORAGE_INSTANCE_KEY = "brewday_context_storage_instance"
BREWZILLA_TARGET = "number.brewzilla_target_temperature"
BREWZILLA_TEMP = "sensor.brewzilla_temperature"
MAX_FALLBACK_READBACK_AGE_SECONDS = 90


def _store(hass: HomeAssistant) -> dict[str, Any]:
    return hass.data.setdefault(DOMAIN, {}).setdefault(
        DATA_KEY,
        {
            "current_mode": MANUAL_BREWING,
            "last_external_mode": None,
            "external_snapshots": {},
            "fallback_active": False,
            "fallback_from_mode": None,
            "fallback_reason": None,
            "fallback_started_at": None,
            "reconnect_expected": False,
            "resync_required": False,
            "resync_reason": None,
            "resync_from_mode": None,
        },
    )


def _storage(hass: HomeAssistant) -> Store:
    domain_data = hass.data.setdefault(DOMAIN, {})
    if STORAGE_INSTANCE_KEY not in domain_data:
        domain_data[STORAGE_INSTANCE_KEY] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    return domain_data[STORAGE_INSTANCE_KEY]


def _persisted_context(hass: HomeAssistant) -> dict[str, Any]:
    store = _store(hass)
    return {
        "external_snapshots": deepcopy(store.get("external_snapshots", {})),
        "last_external_mode": store.get("last_external_mode"),
        "manual_fallback_initial_indices": store.get("manual_fallback_initial_indices"),
        "manual_fallback_progress": store.get("manual_fallback_progress"),
        "resync_required": bool(store.get("resync_required")),
        "resync_reason": store.get("resync_reason"),
    }


def _schedule_context_save(hass: HomeAssistant) -> None:
    """Coalesce context writes; retained snapshots are data, not actuation grants."""
    _storage(hass).async_delay_save(lambda: _persisted_context(hass), 2)


async def async_load_brewday_recipe_context(hass: HomeAssistant) -> None:
    """Restore recipe only; a restart MUST NOT restore permission to actuate."""
    state = _store(hass)
    if state.get("persistent_context_loaded"):
        return
    stored = await _storage(hass).async_load()
    state["persistent_context_loaded"] = True
    if not isinstance(stored, dict):
        return
    mode = stored.get("last_external_mode")
    records = stored.get("external_snapshots")
    if mode not in {RCL_BREWING, BREWFATHER_BREWING} or not isinstance(records, dict):
        return
    record = records.get(mode)
    if not isinstance(record, dict) or not isinstance(record.get("snapshot"), dict):
        return
    # Reject malformed/cross-source persisted claims. This is fallback context
    # only, never a fresh external observation or automatic reconnection proof.
    expected_source = "RAPT BrewZilla Profile" if mode == RCL_BREWING else "Brewfather Brew Tracker"
    if record["snapshot"].get("source") != expected_source:
        return
    state["external_snapshots"] = {mode: deepcopy(record)}
    state["last_external_mode"] = mode
    state["fallback_restored_after_restart"] = True
    state["restored_manual_progress"] = stored.get("manual_fallback_progress")
    state.update(
        resync_required=True,
        resync_reason="ha_restart_requires_external_reconciliation",
        resync_from_mode=mode,
        # Normal fallback will import the retained ManualPlan PAUSED.
        fallback_active=False, reconnect_expected=False,
    )


def persist_manual_fallback_progress(hass: HomeAssistant) -> None:
    """Remember only local recipe progress, never an authorization token."""
    store = _store(hass)
    if not store.get("fallback_active"):
        return
    from .manual_brewday_store import get_manual_brewday_session
    session = get_manual_brewday_session(hass)
    store["manual_fallback_progress"] = {
        "stage": session.active_stage_index,
        "step": session.active_step_index,
        "state": str(session.state),
        "remaining": session.remaining_seconds(),
    }
    _schedule_context_save(hass)


def current_mode(hass: HomeAssistant) -> str:
    mode = str(_store(hass).get("current_mode") or MANUAL_BREWING)
    return mode if mode in BREWDAY_MODES else MANUAL_BREWING


def fallback_active(hass: HomeAssistant) -> bool:
    return bool(_store(hass).get("fallback_active"))


def last_external_mode(hass: HomeAssistant) -> str | None:
    value = _store(hass).get("last_external_mode")
    return str(value) if value in {BREWFATHER_BREWING, RCL_BREWING} else None


def has_external_snapshot(hass: HomeAssistant, mode: str) -> bool:
    record = _store(hass).get("external_snapshots", {}).get(mode)
    return isinstance(record, dict) and isinstance(record.get("snapshot"), dict)


def remember_external_snapshot(hass: HomeAssistant, snapshot: dict[str, Any], mode: str) -> None:
    if mode not in {BREWFATHER_BREWING, RCL_BREWING}:
        return
    now = dt_util.utcnow().isoformat()
    store = _store(hass)
    store.setdefault("external_snapshots", {})[mode] = {
        "snapshot": deepcopy(snapshot),
        "seen_at": now,
    }
    store.update(
        fallback_restored_after_restart=False,
        restored_manual_progress=None,
        current_mode=mode,
        last_external_mode=mode,
        fallback_active=False,
        fallback_from_mode=None,
        fallback_reason=None,
        fallback_started_at=None,
        reconnect_expected=False,
        resync_required=False,
        resync_reason=None,
        resync_from_mode=None,
    )
    _schedule_context_save(hass)


def external_ended(hass: HomeAssistant, mode: str, *, reason: str) -> None:
    store = _store(hass)
    if store.get("last_external_mode") == mode:
        store["last_external_mode"] = None
    store.update(
        fallback_active=False,
        fallback_from_mode=None,
        fallback_reason=reason,
        fallback_started_at=None,
        reconnect_expected=False,
        resync_required=False,
        resync_reason=None,
        resync_from_mode=None,
    )
    _schedule_context_save(hass)


def resync_required(hass: HomeAssistant) -> bool:
    """Sticky mismatch latch: never automatically reclaim a changed recipe."""
    return bool(_store(hass).get("resync_required"))


def _manual_fallback_has_advanced(hass: HomeAssistant) -> bool:
    from .manual_brewday_store import get_manual_brewday_session
    from .manual_brewday_runtime import ManualRuntimeState

    store = _store(hass)
    initial = store.get("manual_fallback_initial_indices")
    if not store.get("manual_fallback_plan_loaded") or not isinstance(initial, tuple):
        return True  # No verifiable local position: fail closed.
    session = get_manual_brewday_session(hass)
    return (
        (session.active_stage_index, session.active_step_index) != initial
        or session.state == ManualRuntimeState.COMPLETED
    )


def _identity_mismatch(cached: dict[str, Any], live: dict[str, Any], mode: str) -> str | None:
    if mode == RCL_BREWING:
        for key in ("profile_session_id", "profile_id"):
            previous = str(cached.get(key) or "").strip()
            current = str(live.get(key) or "").strip()
            if key == "profile_session_id" and (not previous or not current):
                return "rcl_session_identity_unverified"
            if previous and current != previous:
                return "rcl_profile_or_session_changed"
        # A matching session does not imply a matching *step*. Do not silently
        # replace the locally retained recipe or re-enable RCL Assist writes.
        old_id = str(cached.get("profile_step_id") or "").strip()
        new_id = str(live.get("profile_step_id") or "").strip()
        old_number = cached.get("profile_step_number")
        new_number = live.get("profile_step_number")
        if old_id and (not new_id or old_id != new_id):
            return "rcl_step_changed_during_outage"
        if old_number is not None and (new_number is None or str(old_number) != str(new_number)):
            return "rcl_step_changed_during_outage"
        if not old_id and old_number is None:
            return "rcl_step_identity_unverified"
    elif mode == BREWFATHER_BREWING:
        # The legacy Brew Tracker snapshot usually has no stable batch ID.
        # Match IDs only if BOTH observations genuinely provide one.
        old = str(cached.get("brewfather_batch_identity") or "").strip()
        new = str(live.get("brewfather_batch_identity") or "").strip()
        if not old or not new:
            return "brewfather_batch_identity_unverified"
        if old != new:
            return "brewfather_batch_changed"
    if (
        str(cached.get("stage") or "").strip() != str(live.get("stage") or "").strip()
        or str(cached.get("raw_step_name") or cached.get("step") or "").strip()
        != str(live.get("raw_step_name") or live.get("step") or "").strip()
    ):
        return "external_stage_or_step_changed"
    return None


def _block_reconnect(hass: HomeAssistant, mode: str, reason: str) -> None:
    _store(hass).update(
        resync_required=True, resync_reason=reason,
        resync_from_mode=mode,
        current_mode=MANUAL_BREWING, fallback_active=True,
        fallback_from_mode=mode, reconnect_expected=False,
    )
    _schedule_context_save(hass)


def external_reconnect_allowed(
    hass: HomeAssistant, live: dict[str, Any], mode: str,
) -> bool:
    """Check frozen external identity and local progress before source reclaim."""
    store = _store(hass)
    if store.get("resync_required"):
        return False
    if not (store.get("fallback_active") and store.get("fallback_from_mode") == mode):
        return True
    record = store.get("external_snapshots", {}).get(mode)
    cached = record.get("snapshot") if isinstance(record, dict) else None
    reason = (
        "external_recipe_cache_missing" if not isinstance(cached, dict)
        else "manual_plan_advanced_during_outage"
        if _manual_fallback_has_advanced(hass)
        else _identity_mismatch(cached, live, mode)
    )
    if reason:
        _block_reconnect(hass, mode, reason)
        return False
    return True


def reconnect_lockout_snapshot(
    hass: HomeAssistant, live: dict[str, Any], mode: str,
) -> dict[str, Any]:
    """Present conflict without granting Manual OR external actuator authority."""
    store = _store(hass)
    reason = str(store.get("resync_reason") or "manual_reconciliation_required")
    snapshot = dict(live)
    snapshot.update(
        source="None", status="resync_required", runtime_state="resync_required",
        target_temperature=None, target_temperature_source=None,
        direct_brewzilla_control_allowed=False, live_timer_active=False,
        refresh_recommended=False, reconnect_expected=False,
        resync_required=True, resync_reason=reason,
        resync_from_mode=mode,
        summary=f"RECONNECT BLOCKED · {mode} · {reason} · operator acknowledgement required",
    )
    result = decorate_snapshot(
        hass, snapshot, MANUAL_BREWING, fallback_from=mode,
        fallback_reason=reason, reconnect_expected=False,
        recipe_context_retained=True,
    )
    result.update(resync_required=True, resync_reason=reason, resync_from_mode=mode)
    return result


def acknowledge_external_reconnect(
    hass: HomeAssistant, *, mode: str, expected_step: str,
    expected_session_id: str | None = None,
) -> None:
    """Explicit operator reconciliation against the CURRENT fresh external state.

    Never trust a previously displayed session/step without live rechecking.
    This only lifts the BA resync latch; it sends no hardware command.
    """
    from homeassistant.exceptions import HomeAssistantError
    from .brewday_operator_abort import brewday_operator_abort_active

    store = _store(hass)
    if brewday_operator_abort_active(hass):
        raise HomeAssistantError("Global Brewday ABORT is active")
    if not store.get("resync_required") or store.get("resync_from_mode") != mode:
        raise HomeAssistantError("No matching external reconnection awaits acknowledgement")
    if mode == RCL_BREWING:
        from .rapt_profile_runtime import build_rapt_profile_runtime_snapshot
        live = build_rapt_profile_runtime_snapshot(hass)
        if not live or live.get("profile_active") is not True or live.get("profile_source_available") is not True:
            raise HomeAssistantError("Fresh active RCL profile is required")
        session = str(live.get("profile_session_id") or "").strip()
        if not session or session != str(expected_session_id or "").strip():
            raise HomeAssistantError("RCL session ID changed or was not confirmed")
    elif mode == BREWFATHER_BREWING:
        from . import brewday_runtime_core as core
        if str(core.state(hass, core.BF_STATUS)).lower() != "active":
            raise HomeAssistantError("Fresh active Brewfather status is required")
        live = core.brewfather_snapshot(hass)
        if live.get("source") != "Brewfather Brew Tracker" or live.get("snapshot_age_seconds", 999999) > 90:
            raise HomeAssistantError("Fresh Brewfather snapshot is required")
    else:
        raise HomeAssistantError("Invalid external source mode")
    current_step = str(live.get("raw_step_name") or live.get("step") or "").strip()
    if not expected_step or current_step.casefold() != expected_step.strip().casefold():
        raise HomeAssistantError("External step differs from the operator-confirmed step")
    remember_external_snapshot(hass, live, mode)


def _fresh_float(hass: HomeAssistant, entity_id: str) -> float | None:
    state = hass.states.get(entity_id)
    if state is None or str(state.state).strip().lower() in {"unknown", "unavailable", "none", ""}:
        return None
    reported = getattr(state, "last_reported", None) or getattr(state, "last_updated", None)
    if reported is None:
        return None
    try:
        age = (dt_util.utcnow() - dt_util.as_utc(reported)).total_seconds()
        if age < 0 or age > MAX_FALLBACK_READBACK_AGE_SECONDS:
            return None
        return float(str(state.state).replace(",", "."))
    except (TypeError, ValueError, OverflowError):
        return None


def _owners(mode: str, fallback_from: str | None) -> dict[str, Any]:
    if mode == RCL_BREWING:
        return {
            "recipe_owner": "rapt_brewzilla_profile",
            "step_timer_owner": "rapt_brewzilla_profile",
            "target_owner": "rapt_brewzilla_profile",
            "heat_owner": "brewassistant_learning",
            "pump_owner": "brewassistant_learning",
            "target_write_allowed_by_mode": False,
            "heater_switch_write_allowed_by_mode": False,
            "heat_utilization_write_allowed_by_mode": True,
            "pump_write_allowed_by_mode": True,
        }
    if mode == BREWFATHER_BREWING:
        return {
            "recipe_owner": "brewfather",
            "step_timer_owner": "brewfather_brew_tracker",
            "target_owner": "brewassistant_from_brewfather",
            "heat_owner": "brewassistant_learning",
            "pump_owner": "brewassistant_learning",
            "target_write_allowed_by_mode": True,
            "heater_switch_write_allowed_by_mode": True,
            "heat_utilization_write_allowed_by_mode": True,
            "pump_write_allowed_by_mode": True,
        }
    recipe_owner = (
        "cached_rapt_recipe" if fallback_from == RCL_BREWING
        else "cached_brewfather_recipe" if fallback_from == BREWFATHER_BREWING
        else "brewassistant_manual_recipe"
    )
    return {
        "recipe_owner": recipe_owner,
        "step_timer_owner": "brewassistant_manual",
        "target_owner": "brewassistant_manual",
        "heat_owner": "brewassistant_learning",
        "pump_owner": "brewassistant_learning",
        "target_write_allowed_by_mode": True,
        "heater_switch_write_allowed_by_mode": True,
        "heat_utilization_write_allowed_by_mode": True,
        "pump_write_allowed_by_mode": True,
    }


def decorate_snapshot(
    hass: HomeAssistant,
    snapshot: dict[str, Any],
    mode: str,
    *,
    fallback_from: str | None = None,
    fallback_reason: str | None = None,
    reconnect_expected: bool = False,
    recipe_context_retained: bool = False,
) -> dict[str, Any]:
    out = dict(snapshot)
    store = _store(hass)
    store["current_mode"] = mode
    if fallback_from is None:
        store.update(
            fallback_active=False,
            fallback_from_mode=None,
            fallback_started_at=None,
            reconnect_expected=False,
        )
    out.update(
        {
            "brewday_mode": mode,
            **_owners(mode, fallback_from),
            "fallback_active": fallback_from is not None,
            "fallback_from_mode": fallback_from,
            "fallback_reason": fallback_reason,
            "recipe_context_retained": recipe_context_retained,
            "reconnect_expected": reconnect_expected,
            "resync_required": bool(store.get("resync_required")),
            "resync_reason": store.get("resync_reason"),
            "resync_from_mode": store.get("resync_from_mode"),
        }
    )
    return out


def _prime_manual_fallback_plan(
    hass: HomeAssistant,
    snapshot: dict[str, Any],
) -> bool:
    """Load retained external recipe context into the existing Manual engine.

    This is an internal source-loss handoff, not an operator takeover bypass.
    It is only called after Brewday has already classified the external source
    as unavailable. The external timeline itself remains frozen in the cache;
    Manual Brewday receives a conservative operator-led copy.
    """
    from .brewday_recipe_fallback import (
        active_position_from_snapshot,
        plan_from_external_snapshot,
    )
    from .manual_brewday_runtime import ManualRuntimeState
    from .manual_brewday_store import get_manual_brewday_session

    plan = plan_from_external_snapshot(snapshot)
    if plan is None or not plan.stages:
        return False

    stage_index, step_index = active_position_from_snapshot(snapshot, plan)
    session = get_manual_brewday_session(hass)

    # GuardedManualRuntimeSession protects ordinary operator takeover while an
    # external source owns Brewday. Source-loss fallback is a trusted internal
    # transition, so update the already-existing session atomically without
    # calling prepare/start/next.
    guarded = bool(getattr(session, "_guard_enabled", False))
    object.__setattr__(session, "_guard_enabled", False)
    try:
        session.plan = plan
        session.active_stage_index = max(0, min(stage_index, len(plan.stages) - 1))
        active_stage = plan.stages[session.active_stage_index]
        session.active_step_index = max(0, min(step_index, len(active_stage.steps) - 1))
        previous_state = str(snapshot.get("runtime_state") or "").lower()
        if _store(hass).get("fallback_restored_after_restart"):
            previous_state = "paused"  # never revive a timer on a stale restored snapshot
        paused = (previous_state == "paused"
                  or snapshot.get("paused_freeze") is True
                  or snapshot.get("stage_paused") is True)
        uncertain = previous_state not in {"live", "running", "paused"}
        session.state = (
            ManualRuntimeState.PAUSED if paused or uncertain
            else ManualRuntimeState.RUNNING
        )
        session.step_started_at = None
        session.paused_at = dt_util.utcnow() if paused or uncertain else None
        session.remaining_when_paused = None
        step = session.active_step
        raw_remaining = snapshot.get("current_step_remaining_seconds")
        if raw_remaining is None:
            raw_remaining = snapshot.get("time_remaining_seconds")
        try:
            remaining = int(raw_remaining) if raw_remaining is not None else None
        except (TypeError, ValueError, OverflowError):
            remaining = None
        duration = step.duration_seconds if step else None
        if duration is not None and remaining is not None and 0 <= remaining <= duration:
            if paused or uncertain:
                session.remaining_when_paused = remaining
            else:
                session.step_started_at = dt_util.utcnow() - timedelta(seconds=duration - remaining)
    finally:
        object.__setattr__(session, "_guard_enabled", guarded)
    return True


def build_manual_fallback_snapshot(
    hass: HomeAssistant,
    *,
    from_mode: str,
    reason: str,
) -> dict[str, Any] | None:
    store = _store(hass)
    record = store.get("external_snapshots", {}).get(from_mode)
    if not isinstance(record, dict) or not isinstance(record.get("snapshot"), dict):
        return None

    cached = deepcopy(record["snapshot"])
    entering_fallback = (
        not store.get("fallback_active")
        or store.get("fallback_from_mode") != from_mode
    )
    if entering_fallback:
        store["fallback_started_at"] = dt_util.utcnow().isoformat()

    manual_plan_loaded = bool(
        _prime_manual_fallback_plan(hass, cached)
        if entering_fallback
        else store.get("manual_fallback_plan_loaded")
    )
    store.update(
        current_mode=MANUAL_BREWING,
        last_external_mode=from_mode,
        fallback_active=True,
        fallback_from_mode=from_mode,
        fallback_reason=reason,
        reconnect_expected=True,
        manual_fallback_plan_loaded=manual_plan_loaded,
    )

    manual_snapshot: dict[str, Any] | None = None
    if manual_plan_loaded:
        from .manual_brewday_adapter import build_manual_engine_snapshot

        manual_snapshot = build_manual_engine_snapshot(hass)
        cached.update(manual_snapshot)

    device_target = _fresh_float(hass, BREWZILLA_TARGET)
    retained_target = cached.get("target_temperature")
    current_position = (
        str(cached.get("stage") or ""),
        str(cached.get("step") or ""),
    )
    if entering_fallback:
        if manual_plan_loaded:
            from .manual_brewday_store import get_manual_brewday_session
            session = get_manual_brewday_session(hass)
            store["manual_fallback_initial_indices"] = (
                session.active_stage_index, session.active_step_index
            )
            restored = store.pop("restored_manual_progress", None)
            if store.get("fallback_restored_after_restart") and isinstance(restored, dict):
                try:
                    si = int(restored["stage"])
                    ti = int(restored["step"])
                    if 0 <= si < len(session.plan.stages) and 0 <= ti < len(session.plan.stages[si].steps):
                        guarded = bool(getattr(session, "_guard_enabled", False))
                        object.__setattr__(session, "_guard_enabled", False)
                        try:
                            session.active_stage_index, session.active_step_index = si, ti
                            session.state = ManualRuntimeState.PAUSED
                            session.step_started_at = None
                            session.paused_at = dt_util.utcnow()
                            session.remaining_when_paused = None
                        finally:
                            object.__setattr__(session, "_guard_enabled", guarded)
                except (KeyError, TypeError, ValueError, OverflowError):
                    pass
        store["manual_fallback_initial_position"] = current_position
        store["manual_fallback_anchor_target"] = (
            device_target if device_target is not None else retained_target
        )
    initial_position = tuple(store.get("manual_fallback_initial_position") or ())
    manual_plan_advanced = bool(
        manual_plan_loaded and _manual_fallback_has_advanced(hass)
    )
    anchor_target = store.get("manual_fallback_anchor_target")
    target = (
        retained_target
        if manual_plan_advanced
        else device_target if device_target is not None
        else anchor_target if anchor_target is not None
        else retained_target
    )
    device_temp = _fresh_float(hass, BREWZILLA_TEMP)

    cached.update(
        {
            "source": "Manual Brewday",
            "status": "fallback",
            "source_status": "manual_fallback",
            "runtime_state": (
                manual_snapshot.get("runtime_state") if manual_snapshot is not None else "paused"
            ),
            "target_temperature": target,
            "target_temperature_source": (
                "manual_retained_recipe_progression" if manual_plan_advanced
                else "fresh_brewzilla_readback" if device_target is not None
                else "manual_fallback_anchor" if anchor_target is not None
                else "manual_retained_recipe" if manual_plan_loaded
                else "cached_external_recipe"
            ),
            "manual_fallback_plan_advanced": manual_plan_advanced,
            "actual_temperature": device_temp if device_temp is not None else cached.get("actual_temperature"),
            "live_timer_active": False,
            "paused_freeze": (
                manual_snapshot is None
                or manual_snapshot.get("runtime_state") in {"paused", "awaiting_confirm"}
            ),
            "awaiting_snapshot": False,
            "refresh_recommended": True,
            "process_executor": (
                "manual_fallback_retained_plan"
                if manual_plan_loaded
                else "manual_fallback_cached_recipe"
            ),
            "control_owner": "brewassistant_manual_fallback",
            "brewassistant_role": "manual_fallback_with_retained_recipe",
            "manual_fallback_recipe_active": True,
            "manual_fallback_plan_loaded": manual_plan_loaded,
            "direct_brewzilla_control_allowed": False,
            "fallback_actuation_blocked": True,
            "fallback_external_last_seen_at": record.get("seen_at"),
            "fallback_started_at": store.get("fallback_started_at"),
            "fallback_external_timeline_frozen": True,
            "fallback_timeline_frozen": not manual_plan_loaded,
            "fallback_progression_policy": (
                "manual_plan_operator_progression_until_source_recovers"
                if manual_plan_loaded
                else "freeze_external_timeline_until_source_recovers"
            ),
            "summary": (
                f"Manual Brewing fallback · {from_mode} unavailable · "
                f"{cached.get('stage') or 'Unknown'} · {cached.get('step') or 'Unknown'}"
            ),
        }
    )
    if entering_fallback:
        persist_manual_fallback_progress(hass)
    if from_mode == RCL_BREWING:
        cached["profile_source_available"] = False
        cached["profile_active"] = None

    return decorate_snapshot(
        hass, cached, MANUAL_BREWING,
        fallback_from=from_mode,
        fallback_reason=reason,
        reconnect_expected=True,
        recipe_context_retained=True,
    )
