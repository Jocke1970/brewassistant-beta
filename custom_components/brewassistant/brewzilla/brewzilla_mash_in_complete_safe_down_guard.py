"""Safe-down bridge after confirmed BrewZilla mash-in.

When the brewer confirms Mash-In Complete, BrewAssistant should be allowed to
lower the BrewZilla target from the latched strike temperature to the real mash
hold target even if Brewfather is still paused.  This is a safe-down operation,
not positive heating, and it avoids leaving the unit parked at strike target
while the brewer is expected to resume Brewfather manually.
"""

from __future__ import annotations

from typing import Any

from homeassistant.util import dt as dt_util

from . import brewzilla_mash_in_gate as mash_in_gate
from . import brewzilla_orchestration as base

_INSTALLED = False
_ORIGINAL_APPLY = None
_ORIGINAL_START_MASH_CIRCULATION = None


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _runtime_allows_operator_safe_down(snapshot: dict[str, Any]) -> bool:
    state = str(snapshot.get("brewday_state") or "idle").lower()
    return bool(
        state in {"live", "running", "paused", "awaiting_snapshot", "prepared", "awaiting_confirm"}
        and not snapshot.get("completed_runtime")
        and not snapshot.get("abort_lockout_active")
        and snapshot.get("connected", True)
        and not snapshot.get("rcl_degraded")
        and not snapshot.get("heat_strike_rcl_degraded")
        and not snapshot.get("rcl_freshness_guard_blocking")
    )


def _safe_down_target(snapshot: dict[str, Any]) -> float | None:
    """Return the requested safe-down target after Mash-In Complete, if any."""
    if snapshot.get("mash_in_gate_state") != "mash_in_complete":
        return None
    if not snapshot.get("mash_in_gate_confirmed") and not snapshot.get("mash_in_resume_allowed"):
        return None
    if not _runtime_allows_operator_safe_down(snapshot):
        return None

    requested = _num(snapshot.get("requested_target"))
    applied = _num(snapshot.get("applied_target"))
    if requested is None or applied is None:
        return None

    # Only lower the target. Raising it while BF is paused remains blocked by the
    # normal orchestration guards.
    if requested > applied + base.TARGET_SYNC_TOLERANCE:
        return None
    if applied - requested <= base.TARGET_SYNC_TOLERANCE:
        return None

    return round(requested, 1)


async def _apply_safe_down_target(
    hass,
    snapshot: dict[str, Any],
    *,
    prefix: str = "mash_in_complete_safe_down",
) -> dict[str, Any] | None:
    target = _safe_down_target(snapshot)
    if target is None:
        return None

    target_changed = await base._set_number(hass, base.BREWZILLA_TARGET_NUMBER, target)
    actions = [f"{prefix}_set_target:{target}" if target_changed else f"{prefix}_target_unchanged:{target}"]
    reason = str(snapshot.get("control_reason") or "Direct production flow active")
    result = {
        **snapshot,
        "applied": True,
        "apply_result": f"{prefix}_applied",
        "actions": actions,
        "target_changed": bool(target_changed),
        "heater_started": False,
        "pump_started": False,
        "paused_target_rewind_blocked": False,
        "target_sync_needed": False if target_changed else snapshot.get("target_sync_needed"),
        "mash_in_complete_safe_down_active": True,
        "mash_in_waiting_for_brewfather_resume": str(snapshot.get("brewday_state") or "").lower() == "paused",
        "orchestration_mode": "direct-control",
        "control_reason": (
            f"{reason}; Mash-In Complete safe-down: lowered BrewZilla target to "
            f"{target}°C while waiting for Brewfather to resume. Positive heating remains blocked by the normal paused/runtime guards."
        ),
        "executed_at": dt_util.utcnow().isoformat(),
    }
    hass.data.setdefault("brewassistant", {})["brewzilla_last_apply_result"] = result
    return result


async def _patched_start_mash_circulation(hass, snapshot: dict[str, Any], *, action_name: str) -> dict[str, Any]:
    assert _ORIGINAL_START_MASH_CIRCULATION is not None
    result = await _ORIGINAL_START_MASH_CIRCULATION(hass, snapshot, action_name=action_name)
    if action_name != "mash_in_complete":
        return result

    safe_down = await _apply_safe_down_target(
        hass,
        result,
        prefix="mash_in_complete_safe_down",
    )
    if safe_down is None:
        return result

    merged_actions = [*(result.get("actions") or []), *(safe_down.get("actions") or [])]
    merged = {
        **safe_down,
        "actions": merged_actions,
        "apply_result": "mash_circulation_started_safe_down_applied",
        "pump_started": result.get("pump_started", False),
        "pump_utilization_changed": result.get("pump_utilization_changed", False),
        "mash_in_resume_allowed": result.get("mash_in_resume_allowed"),
        "mash_in_gate_confirmed": result.get("mash_in_gate_confirmed"),
        "mash_in_gate_confirmed_at": result.get("mash_in_gate_confirmed_at"),
    }
    hass.data.setdefault("brewassistant", {})["brewzilla_last_apply_result"] = merged
    return merged


async def _patched_apply(hass) -> dict[str, Any]:
    assert _ORIGINAL_APPLY is not None
    snapshot = base.build_orchestration_snapshot(hass)
    safe_down = await _apply_safe_down_target(
        hass,
        snapshot,
        prefix="mash_in_complete_safe_down_tick",
    )
    if safe_down is not None:
        await base.async_record_brewday_audit_tick(hass, brewzilla_result=safe_down)
        return safe_down
    return await _ORIGINAL_APPLY(hass)


def install_mash_in_complete_safe_down_guard() -> None:
    """Install safe-down handling after mash-in completion."""
    global _INSTALLED, _ORIGINAL_APPLY, _ORIGINAL_START_MASH_CIRCULATION
    if _INSTALLED:
        return

    _ORIGINAL_APPLY = base.async_apply_brewzilla_target_if_allowed
    _ORIGINAL_START_MASH_CIRCULATION = mash_in_gate._start_mash_circulation
    base.async_apply_brewzilla_target_if_allowed = _patched_apply
    mash_in_gate._start_mash_circulation = _patched_start_mash_circulation
    _INSTALLED = True
