"""Explicit operator emergency ABORT: independent of BA read-only and source owner.

Only this operator-triggered entry point may bypass BA's ordinary write boundary.
It never grants positive control, does not run on telemetry/STOP transitions and
cannot certify the physical outputs OFF from a cloud command acknowledgement.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..brewday.brewday_operator_abort import async_latch_brewday_operator_abort
from ..brewday.brewday_runtime import build_brewday_runtime_snapshot
from ..brewday import rapt_profile_runtime
from ..supervised_apply import clear_pending_action
from .brewzilla_owned_control import clear_owned_control
from . import brewzilla_orchestration as base

_INSTALLED = False
_ORIGINAL_ABORT = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _fresh_after(hass: Any, entity_id: str, since: datetime) -> Any | None:
    """A reported state after ABORT is readback, never physical certification."""
    state = hass.states.get(entity_id)
    if state is None or str(state.state).lower() in {"unknown", "unavailable", "none", ""}:
        return None
    reported = getattr(state, "last_reported", None) or getattr(state, "last_updated", None)
    if reported is None:
        return None
    try:
        from homeassistant.util import dt as dt_util
        timestamp = dt_util.as_utc(reported)
        age = (_now() - timestamp).total_seconds()
        return state if timestamp >= since and 0 <= age <= 90 else None
    except (TypeError, ValueError, OverflowError):
        return None


async def _command(hass: Any, result: dict[str, Any], key: str, domain: str,
                   service: str, data: dict[str, Any]) -> None:
    """Continue emergency attempts if any individual output or RCL call fails."""
    try:
        if not hass.services.has_service(domain, service):
            result["emergency_commands"][key] = "service_unavailable"
            result["errors"].append(f"{key}: service unavailable")
            return
        await hass.services.async_call(domain, service, data, blocking=True)
    except Exception as exc:  # Emergency best effort: never skip remaining outputs.
        result["emergency_commands"][key] = "failed"
        result["errors"].append(f"{key}: {type(exc).__name__}: {exc}")
    else:
        result["emergency_commands"][key] = "requested_not_physically_verified"
        result["actions"].append(f"emergency_request:{key}")


async def async_emergency_abort(hass: Any) -> dict[str, Any]:
    """Latch and attempt STOP + output OFF/zero regardless of current owner.

    This deliberately calls HA's service registry directly, unlike ordinary
    BA orchestration, which remains denied in observation mode. A network or
    hardware failure cannot be converted into a successful physical STOP.
    """
    started = _now()
    result: dict[str, Any] = {
        "source": "brewzilla_emergency_abort",
        "status": "emergency_abort_requested",
        "aborted_at": started.isoformat(),
        "abort_lockout_seconds": base.ABORT_LOCKOUT_SECONDS,
        "actions": [], "errors": [], "emergency_commands": {},
        "safe_state_enforced": False, "safe_state_ok": False,
        "outputs_physically_off_verified": False,
        "physical_outputs_off_verified": False,
        "readback_safe_after_abort": False,
    }
    # ABORT takes precedence over all source/read-only/positive commands.
    # Establish the in-memory positive-action lockout BEFORE any awaited call.
    # The physical OFF/0 requests must not wait for RAPT cloud STOP, storage,
    # runtime snapshots, or non-critical cleanup.
    hass.data.setdefault("brewassistant", {})[base.ABORT_DATA_KEY] = result
    try:
        base.clear_owned_control(hass, reason="emergency_abort")
    except Exception as exc:
        # A stale owned-control lease must never prevent physical OFF requests.
        result["errors"].append(f"abort_owned_control_cleanup: {type(exc).__name__}: {exc}")

    # Leave the BrewZilla main controller powered for feedback. Disconnecting
    # it prevents us from checking the actual heater/pump/utilization readbacks.
    result["main_power_command"] = "preserve_current_state_for_telemetry"
    output_commands = (
        ("heater_off", "switch", "turn_off", {"entity_id": base.BREWZILLA_HEATER_SWITCH}),
        ("pump_off", "switch", "turn_off", {"entity_id": base.BREWZILLA_PUMP_SWITCH}),
        ("heat_utilization_zero", "number", "set_value",
         {"entity_id": base.BREWZILLA_HEAT_UTILIZATION, "value": 0}),
        ("pump_utilization_zero", "number", "set_value",
         {"entity_id": base.BREWZILLA_PUMP_UTILIZATION, "value": 0}),
    )
    for key, domain, service, payload in output_commands:
        await _command(hass, result, key, domain, service, payload)

    # STOP the profile as well. Do not allow a slow or broken cloud STOP to
    # postpone local OFF/0 requests. A returned service call is NOT proof that
    # a running external RAPT controller has stopped.
    try:
        profile = rapt_profile_runtime._profile_state(hass)
        attrs = getattr(profile, "attributes", {}) if profile is not None else {}
        device_id = attrs.get("raw_device_id") if hasattr(attrs, "get") else None
        active = bool(profile is not None and str(getattr(profile, "state", "")).lower() == "on")
        if active and device_id:
            await _command(hass, result, "rapt_profile_end", "rapt_cloud_link",
                           "end_brewzilla_profile", {"brewzilla_id": str(device_id)})
        elif active:
            result["emergency_commands"]["rapt_profile_end"] = "device_id_unverified"
            result["errors"].append("Active RAPT profile: verified device ID unavailable")
        else:
            result["emergency_commands"]["rapt_profile_end"] = "no_active_profile_verified"
    except Exception as exc:
        result["emergency_commands"]["rapt_profile_end"] = "profile_discovery_failed"
        result["errors"].append(f"rapt_profile_discovery: {type(exc).__name__}: {exc}")

    # Reassert OFF/0 after attempting RAPT STOP. The source may have tried to
    # reapply utilization while the remote STOP request was in flight. Neither
    # acknowledgement proves hardware safe, so also require fresh readbacks.
    for key, domain, service, payload in output_commands:
        await _command(hass, result, f"reassert_{key}", domain, service, payload)

    # Persist the operator ABORT latch after critical device commands. The
    # in-memory lockout above already blocked BA positive writes immediately.
    try:
        runtime = build_brewday_runtime_snapshot(hass)
    except Exception as exc:
        runtime = {}
        result["errors"].append(f"runtime_snapshot: {type(exc).__name__}")
    try:
        await async_latch_brewday_operator_abort(
            hass, source=str(runtime.get("source") or "None"),
            stage=str(runtime.get("stage") or "Idle"),
            step=str(runtime.get("step") or "Idle"),
            reason="operator_emergency_abort",
        )
    except Exception as exc:
        result["errors"].append(f"abort_latch_persistence: {type(exc).__name__}: {exc}")

    # Best-effort housekeeping after OFF requests. Never let cleanup prevent
    # the emergency request, or silently restart a pending positive action.
    try:
        clear_owned_control(hass, reason="emergency_abort")
        clear_pending_action(hass, reason="emergency_abort")
    except Exception as exc:
        result["errors"].append(f"abort_cleanup: {type(exc).__name__}: {exc}")

    # Requested/acknowledged is NOT a physical safety guarantee.
    result["output_off_requests_sent"] = all(
        result["emergency_commands"].get(key) == "requested_not_physically_verified"
        for key in ("heater_off", "pump_off", "heat_utilization_zero", "pump_utilization_zero")
    )
    result["safe_state_enforced"] = False
    readbacks = {
        "heater": _fresh_after(hass, base.BREWZILLA_HEATER_SWITCH, started),
        "pump": _fresh_after(hass, base.BREWZILLA_PUMP_SWITCH, started),
        "heat_utilization": _fresh_after(hass, base.BREWZILLA_HEAT_UTILIZATION, started),
        "pump_utilization": _fresh_after(hass, base.BREWZILLA_PUMP_UTILIZATION, started),
        "main_power": _fresh_after(hass, base.BREWZILLA_MAIN_SWITCH, started),
    }
    result["emergency_readbacks"] = {
        key: (state.state if state is not None else "unverified")
        for key, state in readbacks.items()
    }
    try:
        readback_safe = (readbacks["heater"] is not None and readbacks["heater"].state == "off"
                         and readbacks["pump"] is not None and readbacks["pump"].state == "off"
                         and readbacks["heat_utilization"] is not None
                         and float(readbacks["heat_utilization"].state) <= 0.1
                         and readbacks["pump_utilization"] is not None
                         and float(readbacks["pump_utilization"].state) <= 0.1)
    except (TypeError, ValueError):
        readback_safe = False
    result["readback_safe_after_abort"] = bool(readback_safe)
    result["safe_state_ok"] = bool(readback_safe)
    result["status"] = (
        "outputs_zero_off_in_ha_stop_still_requires_confirmation"
        if readback_safe else "emergency_unverified_check_device"
    )
    # Main power remains readable; ON is acceptable for telemetry, but not
    # evidence that heater/pump are safe. Unavailable main power is a warning.
    result["controller_telemetry_available_after_abort"] = (
        readbacks["main_power"] is not None and readbacks["main_power"].state == "on"
    )
    result["rapt_stop_confirmed"] = False  # Cloud ACK is never verified STOP.
    result["physical_safe_state_certified"] = False
    # Never claim that RCL/HA readbacks prove the physical device is safe.
    result["outputs_physically_off_verified"] = False
    result["physical_outputs_off_verified"] = False
    hass.data.setdefault("brewassistant", {})[base.ABORT_DATA_KEY] = result
    return result


def install_emergency_abort() -> None:
    """Register the sole explicit emergency entry point after normal guards."""
    global _INSTALLED, _ORIGINAL_ABORT
    if _INSTALLED:
        return
    _ORIGINAL_ABORT = base.async_abort_brewzilla
    base.async_abort_brewzilla = async_emergency_abort
    _INSTALLED = True
