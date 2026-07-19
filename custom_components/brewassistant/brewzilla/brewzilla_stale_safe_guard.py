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


def _utilization_reduction(current: Any, desired: Any) -> bool:
    current_num = _num(current)
    desired_num = _num(desired)
    if current_num is None or desired_num is None:
        return False
    return desired_num < current_num - _base.UTILIZATION_TOLERANCE


def _utilization_not_increase(current: Any, desired: Any) -> bool:
    current_num = _num(current)
    desired_num = _num(desired)
    if current_num is None or desired_num is None:
        return False
    return desired_num <= current_num + _base.UTILIZATION_TOLERANCE


def _heat_strike_paused_context(snapshot: dict[str, Any]) -> bool:
    phase = str(snapshot.get("advice_physical_phase") or "").lower()
    return bool(
        snapshot.get("heat_strike_latch_active")
        or snapshot.get("mash_in_heat_strategy_active")
        or phase.startswith("pre_mash_in")
    )


def _paused_heat_safety_reduction_allowed(snapshot: dict[str, Any]) -> bool:
    if not _heat_strike_paused_context(snapshot):
        return False
    if snapshot.get("heater_stop_needed"):
        return True
    if not snapshot.get("heat_utilization_action_needed"):
        return False
    return _utilization_reduction(
        snapshot.get("heat_utilization"),
        snapshot.get("desired_heat_utilization"),
    ) or not _desired_positive(snapshot.get("desired_heat_utilization"))


def _paused_pump_safety_change_allowed(snapshot: dict[str, Any]) -> bool:
    """Allow safe pump changes while paused in heat-strike/mash-in wait.

    Pump circulation is not a heat source.  During pre-mash-in it is used to
    equalize kettle/wort temperature and reduce overshoot risk.  The paused gate
    should still block unrelated pump starts, but it must not block heat-strike
    mixing or pump reductions.
    """
    if not _heat_strike_paused_context(snapshot):
        return False
    if snapshot.get("pump_stop_needed"):
        return True
    if snapshot.get("pump_action_needed") and snapshot.get("desired_pump_on") is True:
        return True
    if not snapshot.get("pump_utilization_action_needed"):
        return False
    desired = snapshot.get("desired_pump_utilization")
    current = snapshot.get("pump_utilization")
    return _desired_positive(desired) or _utilization_not_increase(current, desired)


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
    """Paused BrewTracker must not start/reassert new heat actions.

    Safety reductions are different from positive control.  When BF pauses at
    the post-strike mash-in/additions step, BA must still be able to reduce heat
    utilization, turn the heater off, and increase pump circulation for mixing.
    Otherwise an earlier full-power heat-strike command can remain latched until
    BrewZilla local regulation catches up.
    """
    if not _runtime_paused(snapshot) or snapshot.get("completed_runtime"):
        return False

    blocked = False

    if snapshot.get("heater_action_needed") and not _paused_heat_safety_reduction_allowed(snapshot):
        blocked = True

    if snapshot.get("heater_stop_needed") and _heat_strike_paused_context(snapshot):
        blocked = blocked or False

    if snapshot.get("pump_action_needed") and not _paused_pump_safety_change_allowed(snapshot):
        blocked = True

    if snapshot.get("pump_stop_needed") and not _paused_pump_safety_change_allowed(snapshot):
        blocked = True

    if snapshot.get("ba_owned_reassert_action_needed"):
        blocked = True

    if snapshot.get("heat_utilization_action_needed"):
        if not _paused_heat_safety_reduction_allowed(snapshot) and _desired_positive(snapshot.get("desired_heat_utilization")):
            blocked = True

    if snapshot.get("pump_utilization_action_needed"):
        if not _paused_pump_safety_change_allowed(snapshot) and _desired_positive(snapshot.get("desired_pump_utilization")):
            blocked = True

    return blocked


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
            paused_control_block_reason="BrewTracker paused; BA will not start/reassert heat or unrelated pump actions.",
            paused_heat_safety_reduction_allowed=_paused_heat_safety_reduction_allowed(snapshot),
            paused_pump_safety_change_allowed=_paused_pump_safety_change_allowed(snapshot),
        )

    if _runtime_paused(snapshot) and _heat_strike_paused_context(snapshot):
        snapshot = {
            **snapshot,
            "paused_control_blocked": False,
            "paused_heat_safety_reduction_allowed": _paused_heat_safety_reduction_allowed(snapshot),
            "paused_pump_safety_change_allowed": _paused_pump_safety_change_allowed(snapshot),
        }

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
