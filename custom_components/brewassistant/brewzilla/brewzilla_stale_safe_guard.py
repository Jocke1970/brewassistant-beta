"""Hard safe-hold wrapper for stale BrewZilla/RCL data."""

from __future__ import annotations

from typing import Any

from homeassistant.util import dt as dt_util

from . import brewzilla_orchestration as _base

_BASE_ASYNC_APPLY_BREWZILLA_TARGET_IF_ALLOWED = _base.async_apply_brewzilla_target_if_allowed
_INSTALLED = False


def _runtime_active(snapshot: dict[str, Any]) -> bool:
    return _base._runtime_active(str(snapshot.get("brewday_state") or "idle"))


def _stale_safe_hold_required(snapshot: dict[str, Any]) -> bool:
    """Return true when BA must actively hold BrewZilla outputs safe.

    Freshness guard blocks normal target/heat strategy when RCL temperature is
    stale. That is not enough in production because the BrewZilla/RAPT controller
    may still heat locally if it already has a target. During stale active
    runtime, BA therefore reasserts heater OFF, pump OFF and utilization 0 on
    every executor pass until fresh data is available or the operator aborts.
    """
    return bool(
        snapshot.get("rcl_freshness_guard_blocking")
        and _runtime_active(snapshot)
        and not snapshot.get("completed_runtime")
        and not snapshot.get("abort_lockout_active")
    )


async def async_apply_brewzilla_target_if_allowed(hass) -> dict[str, Any]:
    snapshot = _base.build_orchestration_snapshot(hass)

    if _stale_safe_hold_required(snapshot):
        result: dict[str, Any] = {
            **snapshot,
            "applied": False,
            "apply_result": "stale_rcl_safe_state_check",
            "actions": [],
            "stale_safe_hold_active": True,
            "stale_safe_hold_reason": snapshot.get("rcl_freshness_guard_reason"),
            "target_changed": False,
            "heater_started": False,
            "pump_started": False,
            "executed_at": dt_util.utcnow().isoformat(),
        }
        await _base._enforce_brewzilla_safe_state(
            hass,
            result,
            action_prefix="stale_rcl",
            force=True,
        )
        actions = list(result.get("actions") or [])
        result["applied"] = bool(actions)
        result["apply_result"] = (
            "stale_rcl_safe_state_enforced" if actions else "stale_rcl_safe_state_already_safe"
        )
        hass.data.setdefault("brewassistant", {})["brewzilla_last_apply_result"] = result
        await _base.async_record_brewday_audit_tick(hass, brewzilla_result=result)
        return result

    return await _BASE_ASYNC_APPLY_BREWZILLA_TARGET_IF_ALLOWED(hass)


def install_stale_safe_guard() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _base.async_apply_brewzilla_target_if_allowed = async_apply_brewzilla_target_if_allowed
    _INSTALLED = True
