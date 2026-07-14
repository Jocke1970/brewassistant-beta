"""Late BrewZilla heat guard for stale temperature samples.

A stale RCL temperature should make BA cautious about *new* heat decisions, but
it must not turn BrewZilla heating off after BA has already handed BrewZilla a
valid target.  BrewZilla regulates locally against its target; BA's stale-data
response is to observe/request refresh, not to zero the heat channel.
"""

from __future__ import annotations

from typing import Any

from . import brewzilla_orchestration as base

_BASE_BUILD = None
_INSTALLED = False
MAX_HEAT_TEMP_AGE_SECONDS = 90


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _positive(value: Any) -> bool:
    num = _num(value)
    return bool(num is not None and num > base.UTILIZATION_TOLERANCE)


def _valid_target(value: Any) -> bool:
    target = _num(value)
    return bool(target is not None and base.MIN_TARGET_TEMP <= target <= base.MAX_TARGET_TEMP)


def _local_target_known(snapshot: dict[str, Any]) -> bool:
    """Return true when BrewZilla has, or should already have, a valid target."""
    return bool(
        _valid_target(snapshot.get("applied_target"))
        or _valid_target(snapshot.get("brewzilla_device_target"))
        or (
            not snapshot.get("target_sync_needed")
            and _valid_target(snapshot.get("requested_target"))
        )
    )


def _temp_age(snapshot: dict[str, Any]) -> int | None:
    for key in (
        "rapt_brewzilla_temperature_age_seconds",
        "rcl_freshness_age_seconds",
        "brewzilla_rapt_control_age_seconds",
    ):
        value = _num(snapshot.get(key))
        if value is not None:
            return int(value)
    return None


def _wants_heat(snapshot: dict[str, Any]) -> bool:
    return bool(
        snapshot.get("heater_action_needed")
        or _positive(snapshot.get("desired_heat_utilization"))
        or (
            snapshot.get("heat_utilization_action_needed")
            and _positive(snapshot.get("desired_heat_utilization"))
        )
    )


def _action_needed_without_stale_heat_change(snapshot: dict[str, Any]) -> bool:
    return bool(
        snapshot.get("target_sync_needed")
        or snapshot.get("heater_action_needed")
        or snapshot.get("pump_action_needed")
        or snapshot.get("pump_stop_needed")
        or snapshot.get("pump_utilization_action_needed")
        or snapshot.get("ba_owned_reassert_action_needed")
    )


def _apply_guard(snapshot: dict[str, Any]) -> dict[str, Any]:
    guarded = dict(snapshot)
    age = _temp_age(guarded)
    active = bool(
        age is not None
        and age > MAX_HEAT_TEMP_AGE_SECONDS
        and base._runtime_active(str(guarded.get("brewday_state") or "idle"))
        and not guarded.get("completed_runtime")
        and not guarded.get("abort_lockout_active")
        and _wants_heat(guarded)
    )

    guarded["stale_heat_guard_active"] = active
    guarded["stale_heat_guard_temperature_age_seconds"] = age
    guarded["stale_heat_guard_max_age_seconds"] = MAX_HEAT_TEMP_AGE_SECONDS

    if not active:
        return guarded

    if _local_target_known(guarded):
        action_needed = _action_needed_without_stale_heat_change(guarded)
        connected = bool(guarded.get("connected"))
        original_reason = str(guarded.get("control_reason") or "Direct production flow active")
        guarded.update(
            {
                "stale_heat_guard_mode": "preserve_brewzilla_local_regulation",
                "stale_heat_guard_local_target_known": True,
                "stale_heat_guard_preserved_heat": True,
                "stale_heat_guard_prevented_heat_zero": False,
                "ba_owned_reassert_action_needed": bool(guarded.get("ba_owned_reassert_action_needed")),
                "can_apply_target": connected and action_needed,
                "orchestration_mode": "direct-control" if connected and action_needed else "local-control",
                "rapt_critical_refresh_recommended": True,
                "control_reason": (
                    f"{original_reason} RCL temperature is stale ({age}s), but BrewZilla already has a valid local target. "
                    "BA preserves BrewZilla local heat regulation and does not force heat to 0% or turn the heater off."
                ),
            }
        )
        return guarded

    heater_on = bool(guarded.get("heater_on"))
    desired_heat = 0.0
    heat_action_needed = base._utilization_action_needed(_num(guarded.get("heat_utilization")), desired_heat)
    target_action_needed = bool(guarded.get("target_sync_needed"))
    needed = bool(target_action_needed or heater_on or heat_action_needed)
    connected = bool(guarded.get("connected"))

    guarded.update(
        {
            "stale_heat_guard_mode": "block_new_heat_without_local_target",
            "stale_heat_guard_local_target_known": False,
            "heating_needed": False,
            "desired_heat_utilization": desired_heat,
            "desired_heater_on": False,
            "heater_action_needed": False,
            "heater_stop_needed": heater_on,
            "heat_utilization_action_needed": heat_action_needed,
            "ba_owned_reassert_action_needed": False,
            "can_apply_target": connected and needed,
            "orchestration_mode": "direct-control" if connected and needed else "monitor",
            "control_reason": (
                f"BrewZilla temperature is stale ({age}s) and no trusted local target is known. "
                "New heat is blocked until temperature or target readback is fresh."
            ),
        }
    )
    return guarded


def build_orchestration_snapshot(hass) -> dict[str, Any]:
    assert _BASE_BUILD is not None
    return _apply_guard(_BASE_BUILD(hass))


def install_stale_heat_guard() -> None:
    global _BASE_BUILD, _INSTALLED
    if _INSTALLED:
        return
    _BASE_BUILD = base.build_orchestration_snapshot
    base.build_orchestration_snapshot = build_orchestration_snapshot
    _INSTALLED = True
