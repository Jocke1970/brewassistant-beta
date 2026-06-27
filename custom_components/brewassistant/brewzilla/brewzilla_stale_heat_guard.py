"""Late BrewZilla heat guard for stale temperature samples."""

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

    heater_on = bool(guarded.get("heater_on"))
    desired_heat = 0.0
    heat_action_needed = base._utilization_action_needed(_num(guarded.get("heat_utilization")), desired_heat)
    target_action_needed = bool(guarded.get("target_sync_needed"))
    needed = bool(target_action_needed or heater_on or heat_action_needed)
    connected = bool(guarded.get("connected"))

    guarded.update(
        {
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
                f"BrewZilla temperature is stale ({age}s). Heat is held at 0% until temperature is fresh. "
                "Target sync and heater-off remain allowed."
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
