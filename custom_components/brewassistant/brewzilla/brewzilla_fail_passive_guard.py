"""Fail-passive BrewZilla fallback for active hot-side control.

BrewAssistant is allowed to be the smarter supervisory regulator while RAPT/
BrewZilla telemetry is current.  A telemetry outage is not, by itself, a reason
to turn BrewZilla off: the appliance already has a local target and local
regulator.

During an active hot-side phase this guard therefore turns ordinary data loss
into a *no new writes* state.  The last target/utilization/switch state is left
untouched so BrewZilla can continue locally.  ABORT and explicit hard-safety
paths remain outside this contract and retain authority.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import brewzilla_orchestration as base
from . import brewzilla_temperature as temperature

_INSTALLED = False
_ORIGINAL_BUILD: Callable[[HomeAssistant], dict[str, Any]] | None = None
_ORIGINAL_APPLY = None
_ORIGINAL_AUTO_RESOLVE = None

MAX_ACTIVE_CONTROL_DATA_AGE_SECONDS = 90
_ACTIVE_STATES = {"live", "running", "paused", "awaiting_snapshot", "prepared", "awaiting_confirm"}


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _runtime_active(snapshot: dict[str, Any]) -> bool:
    state = str(snapshot.get("brewday_state") or snapshot.get("runtime_state") or "idle").strip().lower()
    return state in _ACTIVE_STATES and not snapshot.get("completed_runtime")


def _age_stale(value: Any) -> bool:
    age = _num(value)
    return bool(age is not None and age > MAX_ACTIVE_CONTROL_DATA_AGE_SECONDS)


def _resolved_temperature_health(hass: HomeAssistant) -> dict[str, Any]:
    resolved = temperature.brewzilla_temperature_snapshot(hass)
    mash_age = resolved.get("mash_temperature_age_seconds")
    wort_age = resolved.get("wort_temperature_age_seconds")
    lock_active = bool(resolved.get("mash_temperature_source_lock_active"))
    lock_degraded = resolved.get("mash_temperature_source_lock_degraded_reason")
    process_available = resolved.get("mash_temperature") is not None

    reason = None
    if lock_active and lock_degraded:
        reason = f"owned_process_probe_degraded:{lock_degraded}"
    elif not process_available and resolved.get("hot_side_process_sensor_owned"):
        reason = "owned_process_probe_unavailable"
    elif _age_stale(mash_age):
        reason = f"process_temperature_stale:{int(float(mash_age))}s"
    elif _age_stale(wort_age):
        reason = f"wort_temperature_stale:{int(float(wort_age))}s"

    return {
        "fail_passive_temperature_reason": reason,
        "fail_passive_process_temperature_age_seconds": mash_age,
        "fail_passive_wort_temperature_age_seconds": wort_age,
        "fail_passive_process_source": resolved.get("mash_temperature_source"),
        "fail_passive_process_entity": resolved.get("mash_temperature_entity"),
        "fail_passive_process_lock_active": lock_active,
        "fail_passive_process_lock_degraded_reason": lock_degraded,
    }


def _fail_passive_reason(hass: HomeAssistant, snapshot: dict[str, Any]) -> tuple[str | None, dict[str, Any]]:
    health = _resolved_temperature_health(hass)
    if not _runtime_active(snapshot):
        return None, health
    if snapshot.get("abort_lockout_active"):
        return None, health

    # Explicit hard-safety/ABORT paths must still be allowed to safe-down.
    safety = str(snapshot.get("safety_state") or "").strip().lower()
    if safety in {"abort", "aborted", "emergency", "hard_stop", "hard-stop"}:
        return None, health

    if snapshot.get("connected") is False:
        return "brewzilla_or_rcl_disconnected", health

    if health.get("fail_passive_temperature_reason"):
        return str(health["fail_passive_temperature_reason"]), health

    # Older layers may expose these diagnostics.  They are treated as a reason
    # to stop *BA writes*, never as an instruction to zero BrewZilla outputs.
    if snapshot.get("rcl_degraded") or snapshot.get("heat_strike_rcl_degraded"):
        return "rcl_control_surface_degraded", health
    if snapshot.get("clean_heat_strike_process_temperature_missing"):
        return "canonical_process_temperature_missing", health

    return None, health


def _hold_last_observed(snapshot: dict[str, Any], *, reason: str, health: dict[str, Any]) -> dict[str, Any]:
    """Return a no-write snapshot while BrewZilla continues local regulation."""
    out = dict(snapshot)
    observed_heat = _num(out.get("heat_utilization"))
    observed_pump = _num(out.get("pump_utilization"))
    observed_heater_on = out.get("heater_on")
    observed_pump_on = out.get("pump_on")
    preserved_target = _num(out.get("applied_target"))
    if preserved_target is None:
        preserved_target = _num(out.get("brewzilla_device_target"))

    out.update(
        {
            **health,
            "fail_passive_active": True,
            "fail_passive_reason": reason,
            "fail_passive_mode": "brewzilla_local_regulation",
            "fail_passive_preserved_target": preserved_target,
            "fail_passive_no_new_writes": True,
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
            "orchestration_mode": "local-control",
            "desired_heat_utilization": observed_heat,
            "desired_pump_utilization": observed_pump,
            "desired_heater_on": observed_heater_on,
            "desired_pump_on": observed_pump_on,
            "rapt_critical_refresh_recommended": True,
            "control_reason": (
                f"Fail-passive active ({reason}). BA sends no new BrewZilla commands; "
                f"the last local target {preserved_target}°C and current BrewZilla outputs are left untouched "
                "until trustworthy telemetry returns."
            ),
        }
    )
    return out


def _augment_snapshot(hass: HomeAssistant, snapshot: dict[str, Any]) -> dict[str, Any]:
    reason, health = _fail_passive_reason(hass, snapshot)
    if reason is None:
        return {
            **snapshot,
            **health,
            "fail_passive_active": False,
            "fail_passive_reason": None,
            "fail_passive_no_new_writes": False,
        }
    return _hold_last_observed(snapshot, reason=reason, health=health)


def build_orchestration_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    assert _ORIGINAL_BUILD is not None
    return _augment_snapshot(hass, _ORIGINAL_BUILD(hass))


async def async_apply_brewzilla_target_if_allowed(hass: HomeAssistant) -> dict[str, Any]:
    assert _ORIGINAL_APPLY is not None
    snapshot = base.build_orchestration_snapshot(hass)
    if not snapshot.get("fail_passive_active"):
        return await _ORIGINAL_APPLY(hass)

    result = {
        **snapshot,
        "applied": False,
        "apply_result": "fail_passive_brewzilla_local_control",
        "actions": [],
        "target_changed": False,
        "heater_started": False,
        "pump_started": False,
        "executed_at": dt_util.utcnow().isoformat(),
    }
    hass.data.setdefault("brewassistant", {})["brewzilla_last_apply_result"] = result
    await base.async_record_brewday_audit_tick(hass, brewzilla_result=result)
    return result


def _resolve_auto_without_internal_takeover(
    hass: HomeAssistant,
    ble: dict[str, Any],
    control: dict[str, Any],
    internal: dict[str, Any],
):
    """Do not silently replace an owned external process probe with internal."""
    assert _ORIGINAL_AUTO_RESOLVE is not None
    resolved, lock_active, degraded_reason = _ORIGINAL_AUTO_RESOLVE(hass, ble, control, internal)
    if lock_active and degraded_reason:
        return None, True, degraded_reason
    return resolved, lock_active, degraded_reason


def install_fail_passive_guard() -> None:
    """Install the outermost ordinary-data-loss fallback contract."""
    global _INSTALLED, _ORIGINAL_BUILD, _ORIGINAL_APPLY, _ORIGINAL_AUTO_RESOLVE
    if _INSTALLED:
        return

    _ORIGINAL_AUTO_RESOLVE = temperature._resolve_auto_with_hot_side_ownership
    temperature._resolve_auto_with_hot_side_ownership = _resolve_auto_without_internal_takeover

    _ORIGINAL_BUILD = base.build_orchestration_snapshot
    _ORIGINAL_APPLY = base.async_apply_brewzilla_target_if_allowed
    base.build_orchestration_snapshot = build_orchestration_snapshot
    base.async_apply_brewzilla_target_if_allowed = async_apply_brewzilla_target_if_allowed
    _INSTALLED = True
