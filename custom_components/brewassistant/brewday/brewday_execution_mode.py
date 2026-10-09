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
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from ..const import DOMAIN

MANUAL_BREWING = "Manual Brewing"
BREWFATHER_BREWING = "Brewfather Brewing"
RCL_BREWING = "RCL Brewing"
BREWDAY_MODES = (MANUAL_BREWING, BREWFATHER_BREWING, RCL_BREWING)

DATA_KEY = "brewday_execution_mode_runtime"
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
        },
    )


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
        current_mode=mode,
        last_external_mode=mode,
        fallback_active=False,
        fallback_from_mode=None,
        fallback_reason=None,
        fallback_started_at=None,
        reconnect_expected=False,
    )


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
    )


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
        session.state = ManualRuntimeState.RUNNING
        session.step_started_at = None
        session.paused_at = None
        session.remaining_when_paused = None
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
        store["manual_fallback_initial_position"] = current_position
        store["manual_fallback_anchor_target"] = (
            device_target if device_target is not None else retained_target
        )
    initial_position = tuple(store.get("manual_fallback_initial_position") or ())
    manual_plan_advanced = bool(
        manual_plan_loaded
        and len(initial_position) == 2
        and current_position != initial_position
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
            "runtime_state": "running",
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
            "paused_freeze": False,
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
            "direct_brewzilla_control_allowed": True,
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
