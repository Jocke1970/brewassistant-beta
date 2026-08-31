"""Mash-In readiness contract for realistic strike tolerances and cloud-stale override.

The automatic gate must use the canonical external mash/process temperature and
must never silently replace it with BrewZilla internal temperature.  When RAPT
Cloud makes the process probe stale, BrewZilla remains the local regulator and
an operator may explicitly accept strike readiness after physically verifying
that the local system is near the strike target.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from ..brewday.brewday_audit import async_record_brewday_audit_event
from . import brewzilla_mash_in_gate as gate
from . import brewzilla_orchestration as orchestration
from . import brewzilla_temperature as temperature

AUTO_READY_TOLERANCE_C = 1.0
MANUAL_OVERRIDE_TOLERANCE_C = 2.0
LOCAL_TARGET_TOLERANCE_C = 0.5
MAX_AUTO_PROCESS_AGE_SECONDS = 90

_INSTALLED = False
_ORIGINAL_AUGMENT: Callable[[HomeAssistant, dict[str, Any]], dict[str, Any]] | None = None


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _canonical_process_temperature(snapshot: dict[str, Any]) -> float | None:
    """Use only canonical mash/process fields; never internal/wort fallback."""
    for key in ("mash_temperature", "brewzilla_mash_temperature"):
        value = _num(snapshot.get(key))
        if value is not None:
            return value
    return None


def _automatic_ready(snapshot: dict[str, Any]) -> bool:
    """Return true only for fresh canonical process data inside ±1.0 °C."""
    if not snapshot.get("mash_in_process_temperature_fresh"):
        return False
    if not gate._runtime_active_enough(snapshot):
        return False

    stage_text = gate._text(snapshot, "runtime_stage", "stage")
    step_text = gate._text(snapshot, "runtime_step", "step", "runtime_raw_step_name", "raw_step_name")
    if "mash" not in stage_text and "mäsk" not in stage_text:
        return False
    if not any(word in step_text for word in ("ramp", "hold", "mash", "mäsk")):
        return False
    if not gate._early_mash_step(snapshot):
        return False

    target = gate._target_for_gate(snapshot)
    process = _canonical_process_temperature(snapshot)
    if target is None or process is None:
        return False
    return abs(process - target) <= AUTO_READY_TOLERANCE_C


def _locked_external_candidate(resolved: dict[str, Any]) -> dict[str, Any] | None:
    """Return the latched external candidate even when it is stale.

    This is diagnostics only. A stale candidate must never become automatic
    Mash-In readiness input, but keeping its last value/age makes the operator
    UI useful during RAPT Cloud gaps.
    """
    lock_entity = resolved.get("mash_temperature_source_lock_entity")
    candidates = resolved.get("external_temperature_candidates")
    if not lock_entity or not isinstance(candidates, dict):
        return None
    for candidate in candidates.values():
        if isinstance(candidate, dict) and candidate.get("entity_id") == lock_entity:
            return candidate
    return None


def _resolved_process(hass: HomeAssistant) -> dict[str, Any]:
    resolved = temperature.brewzilla_temperature_snapshot(hass)
    locked = _locked_external_candidate(resolved)

    value = _num(resolved.get("mash_temperature"))
    age = _num(resolved.get("mash_temperature_age_seconds"))
    source = resolved.get("mash_temperature_source")
    entity = resolved.get("mash_temperature_entity")
    external = bool(resolved.get("mash_temperature_external_mash_candidate"))

    # The fail-passive ownership wrapper intentionally returns no active process
    # source while the cloud value is degraded. Retain the latched candidate only
    # as stale diagnostics so the UI can show last value + age to the operator.
    if locked is not None and (value is None or age is None or not external):
        value = _num(locked.get("value"))
        age = _num(locked.get("age_seconds"))
        source = locked.get("source") or source
        entity = locked.get("entity_id") or entity
        external = bool(locked.get("external_mash_candidate", True))

    degraded = resolved.get("mash_temperature_source_lock_degraded_reason")
    owned = bool(resolved.get("hot_side_process_sensor_owned"))
    fresh = bool(
        value is not None
        and external
        and (age is None or age <= MAX_AUTO_PROCESS_AGE_SECONDS)
        and not degraded
    )
    return {
        "value": value,
        "age_seconds": age,
        "source": source,
        "entity": entity,
        "fresh": fresh,
        "degraded_reason": degraded,
        "owned": owned,
        "wort_temperature": _num(resolved.get("wort_temperature")),
        "wort_age_seconds": _num(resolved.get("wort_temperature_age_seconds")),
    }


def _manual_override_diagnostics(
    snapshot: dict[str, Any],
    process: dict[str, Any],
) -> dict[str, Any]:
    target = gate._target_for_gate(snapshot)
    state = str(snapshot.get("mash_in_gate_state") or "idle")
    process_value = _num(process.get("value"))
    wort = _num(process.get("wort_temperature"))
    local_target = _num(snapshot.get("brewzilla_device_target"))
    if local_target is None:
        local_target = _num(snapshot.get("applied_target"))

    process_delta = None if target is None or process_value is None else round(process_value - target, 2)
    wort_delta = None if target is None or wort is None else round(wort - target, 2)
    local_target_delta = None if target is None or local_target is None else round(local_target - target, 2)

    in_scope = bool(
        gate._runtime_active_enough(snapshot)
        and gate._mash_scope_active(snapshot)
        and gate._early_mash_step(snapshot)
        and state not in {gate.READY_STATE, gate.STARTED_STATE, gate._COMPLETE_STATE}
        and not snapshot.get("abort_lockout_active")
        and snapshot.get("connected", True)
        and target is not None
    )

    wort_safe = bool(wort_delta is not None and abs(wort_delta) <= MANUAL_OVERRIDE_TOLERANCE_C)
    local_target_ok = bool(local_target_delta is not None and abs(local_target_delta) <= LOCAL_TARGET_TOLERANCE_C)
    fresh_process_near = bool(
        process.get("fresh")
        and process_delta is not None
        and abs(process_delta) <= MANUAL_OVERRIDE_TOLERANCE_C
        and not abs(process_delta) <= AUTO_READY_TOLERANCE_C
        and (wort is None or wort_safe)
    )
    stale_local_near = bool(
        not process.get("fresh")
        and wort_safe
        and local_target_ok
    )

    available = bool(in_scope and (fresh_process_near or stale_local_near))
    if fresh_process_near:
        reason = "fresh_process_within_manual_strike_distance"
    elif stale_local_near:
        reason = "cloud_process_stale_local_brewzilla_near_strike"
    elif not in_scope:
        reason = "outside_pre_mash_in_scope"
    elif process.get("fresh"):
        reason = "fresh_process_outside_manual_strike_distance"
    elif not local_target_ok:
        reason = "local_target_not_verified_near_strike"
    elif not wort_safe:
        reason = "wort_not_within_manual_strike_distance"
    else:
        reason = "override_not_available"

    return {
        "mash_in_auto_ready_tolerance_c": AUTO_READY_TOLERANCE_C,
        "mash_in_override_tolerance_c": MANUAL_OVERRIDE_TOLERANCE_C,
        "mash_in_override_in_scope": in_scope,
        "mash_in_override_available": available,
        "mash_in_override_reason": reason,
        "mash_in_override_warning_required": bool(available and stale_local_near),
        "mash_in_override_process_temperature": process_value,
        "mash_in_override_process_temperature_age_seconds": process.get("age_seconds"),
        "mash_in_override_process_temperature_fresh": bool(process.get("fresh")),
        "mash_in_override_process_source": process.get("source"),
        "mash_in_override_process_entity": process.get("entity"),
        "mash_in_override_process_degraded_reason": process.get("degraded_reason"),
        "mash_in_override_process_delta_c": process_delta,
        "mash_in_override_wort_temperature": wort,
        "mash_in_override_wort_temperature_age_seconds": process.get("wort_age_seconds"),
        "mash_in_override_wort_delta_c": wort_delta,
        "mash_in_override_local_target": local_target,
        "mash_in_override_local_target_delta_c": local_target_delta,
        "mash_in_override_local_target_verified": local_target_ok,
    }


def _augment_snapshot(hass: HomeAssistant, snapshot: dict[str, Any]) -> dict[str, Any]:
    assert _ORIGINAL_AUGMENT is not None
    process = _resolved_process(hass)
    sanitized = dict(snapshot)
    sanitized.update(
        {
            "mash_temperature": process.get("value") if process.get("fresh") else None,
            "brewzilla_mash_temperature": process.get("value") if process.get("fresh") else None,
            "mash_in_process_temperature_fresh": bool(process.get("fresh")),
            "mash_in_process_temperature_age_seconds": process.get("age_seconds"),
            "mash_in_process_temperature_source": process.get("source"),
            "mash_in_process_temperature_entity": process.get("entity"),
            # Prevent legacy readiness paths from bypassing the canonical fresh
            # process requirement. The dedicated contract below is authoritative.
            "mash_in_confirmation_recommended": False,
            "mash_in_heat_strategy_active": False,
        }
    )
    result = _ORIGINAL_AUGMENT(hass, sanitized)
    return {**result, **_manual_override_diagnostics(result, process)}


def build_mash_in_readiness_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    snapshot = orchestration.build_orchestration_snapshot(hass)
    process = _resolved_process(hass)
    gate_snapshot = gate.build_mash_in_gate_snapshot(hass)
    return {
        **gate_snapshot,
        **_manual_override_diagnostics(snapshot, process),
    }


async def async_override_mash_in_ready(hass: HomeAssistant) -> dict[str, Any]:
    """Explicitly latch Mash-In READY when the backend says override is eligible."""
    snapshot = orchestration.build_orchestration_snapshot(hass)
    process = _resolved_process(hass)
    diagnostics = _manual_override_diagnostics(snapshot, process)
    store = gate._gate_store(hass)

    if not diagnostics.get("mash_in_override_available"):
        result = {
            **diagnostics,
            "applied": False,
            "apply_result": "mash_in_override_rejected",
            "executed_at": dt_util.utcnow().isoformat(),
        }
        store["last_override_result"] = result
        await async_record_brewday_audit_event(
            hass,
            "mash_in_override_rejected",
            note=f"Operator Mash-In override rejected: {diagnostics.get('mash_in_override_reason')}",
            brewzilla_result=result,
            always_record=True,
        )
        return build_mash_in_readiness_snapshot(hass)

    store = gate._ensure_gate_for_snapshot(hass, snapshot)
    now = dt_util.utcnow().isoformat()
    store["last_trigger"] = "operator_override"
    store["last_phase"] = "operator_override"
    store["override_used"] = True
    store["override_at"] = now
    store["override_reason"] = diagnostics.get("mash_in_override_reason")
    result = {
        **diagnostics,
        "applied": True,
        "apply_result": "mash_in_ready_operator_override",
        "mash_in_gate_state": gate.READY_STATE,
        "executed_at": now,
    }
    store["last_override_result"] = result
    gate._schedule_notification_if_needed(hass, snapshot, store)
    await async_record_brewday_audit_event(
        hass,
        "mash_in_ready_operator_override",
        note=(
            "Operator accepted strike readiness within the bounded Mash-In override contract; "
            f"reason={diagnostics.get('mash_in_override_reason')}."
        ),
        brewzilla_result=result,
        always_record=True,
    )
    return build_mash_in_readiness_snapshot(hass)


def install_mash_in_readiness_contract() -> None:
    """Make realistic readiness tolerance + explicit override authoritative."""
    global _INSTALLED, _ORIGINAL_AUGMENT
    if _INSTALLED:
        return

    _ORIGINAL_AUGMENT = gate._augment_snapshot

    gate.READY_TOLERANCE_C = AUTO_READY_TOLERANCE_C
    gate._temperature_for_gate = _canonical_process_temperature
    gate._ready_for_mash_in = _automatic_ready
    gate._augment_snapshot = _augment_snapshot

    _INSTALLED = True
