"""Runtime safety wrapper for BrewZilla/RCL stale data and paused control."""

from __future__ import annotations

from typing import Any

from homeassistant.util import dt as dt_util

from . import brewzilla_orchestration as _base

_BASE_ASYNC_APPLY_BREWZILLA_TARGET_IF_ALLOWED = None
_INSTALLED = False

STALE_MAINTAIN_HOLD_MARGIN_C = 1.0


def _runtime_state(snapshot: dict[str, Any]) -> str:
    return str(snapshot.get("brewday_state") or "idle").lower()


def _runtime_active(snapshot: dict[str, Any]) -> bool:
    return _base._runtime_active(_runtime_state(snapshot))


def _runtime_paused(snapshot: dict[str, Any]) -> bool:
    return _runtime_state(snapshot) == "paused"


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _desired_positive(value: Any) -> bool:
    num = _num(value)
    return bool(num is not None and num > _base.UTILIZATION_TOLERANCE)


def _stale_guard_active(snapshot: dict[str, Any]) -> bool:
    return bool(
        snapshot.get("rcl_freshness_guard_blocking")
        and _runtime_active(snapshot)
        and not snapshot.get("completed_runtime")
        and not snapshot.get("abort_lockout_active")
    )


def _stale_maintain_hold_allowed(snapshot: dict[str, Any]) -> bool:
    """Allow BrewZilla to maintain an already-applied stable hold while temp is stale.

    The RCL temperature entity may not update its timestamp when the value is
    steady. In an already-synced mash hold that is at/near target, BA should not
    turn heat/pump off just because the sample age crossed the stale threshold.
    It should block new changes, request refresh, and leave the local BrewZilla
    controller to maintain the already-applied target.
    """
    if not _stale_guard_active(snapshot):
        return False
    if not snapshot.get("mash_hold_strategy_active"):
        return False
    if snapshot.get("mash_in_heat_strategy_active") or snapshot.get("boil_stage"):
        return False
    if snapshot.get("target_sync_needed"):
        return False

    requested = _num(snapshot.get("requested_target"))
    applied = _num(snapshot.get("applied_target"))
    current = _num(snapshot.get("current_temperature"))
    if requested is None or applied is None or current is None:
        return False
    if abs(requested - applied) > _base.TARGET_SYNC_TOLERANCE:
        return False

    return abs(current - requested) <= STALE_MAINTAIN_HOLD_MARGIN_C


def _paused_blocks_new_positive_control(snapshot: dict[str, Any]) -> bool:
    """Paused BrewTracker must not start/reassert new heat or pump actions."""
    if not _runtime_paused(snapshot) or snapshot.get("completed_runtime"):
        return False
    return bool(
        snapshot.get("heater_action_needed")
        or snapshot.get("pump_action_needed")
        or snapshot.get("ba_owned_reassert_action_needed")
        or (
            snapshot.get("heat_utilization_action_needed")
            and _desired_positive(snapshot.get("desired_heat_utilization"))
        )
        or (
            snapshot.get("pump_utilization_action_needed")
            and _desired_positive(snapshot.get("desired_pump_utilization"))
        )
    )


async def _record_no_action(hass, snapshot: dict[str, Any], apply_result: str, **extra: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        **snapshot,
        "applied": False,
        "apply_result": apply_result,
        "actions": [],
        "target_changed": False,
        "heater_started": False,
        "pump_started": False,
        "executed_at": dt_util.utcnow().isoformat(),
        **extra,
    }
    hass.data.setdefault("brewassistant", {})["brewzilla_last_apply_result"] = result
    await _base.async_record_brewday_audit_tick(hass, brewzilla_result=result)
    return result


async def async_apply_brewzilla_target_if_allowed(hass) -> dict[str, Any]:
    assert _BASE_ASYNC_APPLY_BREWZILLA_TARGET_IF_ALLOWED is not None
    snapshot = _base.build_orchestration_snapshot(hass)

    if _runtime_paused(snapshot) and snapshot.get("ba_owned_control_active"):
        _base.clear_owned_control(hass, reason="paused_runtime")
        snapshot = _base.build_orchestration_snapshot(hass)

    if _paused_blocks_new_positive_control(snapshot):
        return await _record_no_action(
            hass,
            snapshot,
            "paused_runtime_positive_control_blocked",
            paused_control_blocked=True,
            paused_control_block_reason="BrewTracker paused; BA will not start/reassert heat or pump.",
        )

    if _stale_guard_active(snapshot):
        if _stale_maintain_hold_allowed(snapshot):
            return await _record_no_action(
                hass,
                snapshot,
                "stale_rcl_maintain_existing_hold",
                stale_safe_hold_active=False,
                stale_maintain_hold_active=True,
                stale_maintain_hold_margin_c=STALE_MAINTAIN_HOLD_MARGIN_C,
                stale_maintain_hold_reason=(
                    "RCL temperature sample is stale, but target is already applied and "
                    "last sample is near target; leaving BrewZilla local hold unchanged."
                ),
            )

        result: dict[str, Any] = {
            **snapshot,
            "applied": False,
            "apply_result": "stale_rcl_safe_state_check",
            "actions": [],
            "stale_safe_hold_active": True,
            "stale_safe_hold_reason": snapshot.get("rcl_freshness_guard_reason"),
            "stale_maintain_hold_active": False,
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
    global _BASE_ASYNC_APPLY_BREWZILLA_TARGET_IF_ALLOWED, _INSTALLED
    if _INSTALLED:
        return
    _BASE_ASYNC_APPLY_BREWZILLA_TARGET_IF_ALLOWED = _base.async_apply_brewzilla_target_if_allowed
    _base.async_apply_brewzilla_target_if_allowed = async_apply_brewzilla_target_if_allowed
    _INSTALLED = True
