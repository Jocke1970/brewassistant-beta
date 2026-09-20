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
    if not hass.services.has_service(domain, service):
        result["emergency_commands"][key] = "service_unavailable"
        result["errors"].append(f"{key}: service unavailable")
        return
    try:
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
    # Persist the positive-command lockout before awaiting any external service.
    base.clear_owned_control(hass, reason="emergency_abort")
    clear_owned_control(hass, reason="emergency_abort")
    clear_pending_action(hass, reason="emergency_abort")
    hass.data.setdefault("brewassistant", {})[base.ABORT_DATA_KEY] = result
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
        # The in-memory latch is already set by the persistence helper.
        result["errors"].append(f"abort_latch_persistence: {type(exc).__name__}: {exc}")

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

    # Do not rely on potentially stale HA states to skip an emergency request.
    # In particular an ON readback can be absent and still require OFF attempt.
    for key, domain, service, payload in (
        ("heater_off", "switch", "turn_off", {"entity_id": base.BREWZILLA_HEATER_SWITCH}),
        ("pump_off", "switch", "turn_off", {"entity_id": base.BREWZILLA_PUMP_SWITCH}),
        ("heat_utilization_zero", "number", "set_value",
         {"entity_id": base.BREWZILLA_HEAT_UTILIZATION, "value": 0}),
        ("pump_utilization_zero", "number", "set_value",
         {"entity_id": base.BREWZILLA_PUMP_UTILIZATION, "value": 0}),
        ("main_power_off", "switch", "turn_off", {"entity_id": base.BREWZILLA_MAIN_SWITCH}),
    ):
        await _command(hass, result, key, domain, service, payload)

    result["safe_state_enforced"] = bool(result["actions"])
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
                         and readbacks["main_power"] is not None and readbacks["main_power"].state == "off"
                         and readbacks["heat_utilization"] is not None
                         and float(readbacks["heat_utilization"].state) <= 0.1
                         and readbacks["pump_utilization"] is not None
                         and float(readbacks["pump_utilization"].state) <= 0.1)
    except (TypeError, ValueError):
        readback_safe = False
    result["readback_safe_after_abort"] = bool(readback_safe)
    result["safe_state_ok"] = bool(readback_safe)
    result["status"] = "emergency_readback_safe_not_physical_proof" if readback_safe else "emergency_unverified_check_device"
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
