"""Preserve BrewZilla local heat regulation while a target is active.

BrewZilla has its own thermostat/control loop once a target temperature has been
written. BA may still adjust targets, pump settings and request RCL refreshes,
but it should not use HA/RCL heat-off commands as the normal way to regulate
mash or heat-strike temperature.

Explicit process/safety safe-down is different: when a higher-level strategy
intentionally asks for 0% heat / heater OFF, local-target preservation must not
undo that request. Physical validation on 2026-08-29 showed that suppressing an
explicit Clean Heatstrike coast kept the previous 10% utilization active and
also kept positive heat after a 71.8 -> 66.0°C target downshift.
"""

from __future__ import annotations

from typing import Any

from . import brewzilla_orchestration as base

_BASE_BUILD = None
_INSTALLED = False

_ACTIVE_TARGET_STATES = {"live", "running", "paused", "awaiting_snapshot", "prepared", "awaiting_confirm"}
_PROCESS_ABOVE_TARGET_MARGIN_C = 0.3


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _valid_target(value: Any) -> bool:
    target = _num(value)
    return bool(target is not None and base.MIN_TARGET_TEMP <= target <= base.MAX_TARGET_TEMP)


def _target_known(snapshot: dict[str, Any]) -> bool:
    return bool(
        _valid_target(snapshot.get("applied_target"))
        or _valid_target(snapshot.get("brewzilla_device_target"))
        or (
            not snapshot.get("target_sync_needed")
            and _valid_target(snapshot.get("requested_target"))
        )
    )


def _heat_zero_requested(snapshot: dict[str, Any]) -> bool:
    desired_heat = _num(snapshot.get("desired_heat_utilization"))
    return bool(
        snapshot.get("heater_stop_needed")
        or snapshot.get("desired_heater_on") is False
        or (
            snapshot.get("heat_utilization_action_needed")
            and desired_heat is not None
            and desired_heat <= base.UTILIZATION_TOLERANCE
        )
    )


def _process_temperature(snapshot: dict[str, Any]) -> float | None:
    """Return the process/control temperature used for target safe-down.

    Prefer the external mash/process view when available. The internal BrewZilla
    temperature remains a fallback here; Clean Heatstrike separately carries its
    own hottest-view safety decision and is handled explicitly below.
    """
    for key in (
        "mash_temperature",
        "mash_in_gate_current_temperature",
        "advice_learning_temperature",
        "heat_strike_control_temperature",
        "current_temperature",
        "brewzilla_current_temp",
        "wort_temperature",
    ):
        value = _num(snapshot.get(key))
        if value is not None:
            return value
    return None


def _explicit_safe_down_reason(snapshot: dict[str, Any]) -> str | None:
    """Return why an intentional zero-heat request must bypass preservation."""
    desired_heat = _num(snapshot.get("desired_heat_utilization"))
    if desired_heat is None or desired_heat > base.UTILIZATION_TOLERANCE:
        return None

    # Clean Heatstrike's final-coast / hottest-view safety cap is authoritative.
    # A valid local target must never resurrect the previous positive utilization.
    if snapshot.get("clean_heat_strike_active") and snapshot.get("desired_heater_on") is False:
        return "clean_heatstrike_explicit_zero"

    # During physical malt addition the two-step mash-in gate may explicitly
    # request zero heat when the process is already above the real mash target.
    if snapshot.get("mash_in_started_hold_active") and snapshot.get("desired_heater_on") is False:
        return "mash_in_started_explicit_zero"

    # General target-downshift invariant: if the active process target is lower
    # than the process/control temperature, positive heat must not be preserved.
    requested_target = _num(snapshot.get("requested_target"))
    process_temperature = _process_temperature(snapshot)
    if (
        requested_target is not None
        and process_temperature is not None
        and process_temperature > requested_target + _PROCESS_ABOVE_TARGET_MARGIN_C
    ):
        return "process_above_active_target"

    return None


def _scope_active(snapshot: dict[str, Any]) -> bool:
    state = str(snapshot.get("brewday_state") or "idle").lower()
    return bool(
        state in _ACTIVE_TARGET_STATES
        and not snapshot.get("completed_runtime")
        and not snapshot.get("abort_lockout_active")
        and not snapshot.get("completion_stop_needed")
        and _target_known(snapshot)
    )


def _action_needed(snapshot: dict[str, Any]) -> bool:
    return bool(
        snapshot.get("target_sync_needed")
        or snapshot.get("heater_action_needed")
        or snapshot.get("pump_action_needed")
        or snapshot.get("pump_stop_needed")
        or snapshot.get("pump_utilization_action_needed")
        or (
            snapshot.get("heat_utilization_action_needed")
            and _num(snapshot.get("desired_heat_utilization")) is not None
            and _num(snapshot.get("desired_heat_utilization")) > base.UTILIZATION_TOLERANCE
        )
        or snapshot.get("ba_owned_reassert_action_needed")
    )


def _apply_guard(snapshot: dict[str, Any]) -> dict[str, Any]:
    if not _scope_active(snapshot) or not _heat_zero_requested(snapshot):
        return snapshot

    safe_down_reason = _explicit_safe_down_reason(snapshot)
    if safe_down_reason is not None:
        guarded = dict(snapshot)
        original_reason = str(guarded.get("control_reason") or "BrewZilla local target active.")
        guarded.update(
            {
                "brewzilla_local_heat_preserve_active": False,
                "brewzilla_local_heat_preserve_bypassed": True,
                "brewzilla_local_heat_preserve_reason": safe_down_reason,
                "control_reason": (
                    f"{original_reason} BrewZilla local heat preserve bypassed: "
                    f"explicit safe-down wins ({safe_down_reason}); heat 0% / heater OFF may be applied."
                ),
            }
        )
        return guarded

    guarded = dict(snapshot)
    previous_desired_heat = _num(guarded.get("desired_heat_utilization"))
    current_heat = _num(guarded.get("heat_utilization"))
    preserved_heat_value = current_heat if current_heat is not None else previous_desired_heat
    original_reason = str(guarded.get("control_reason") or "BrewZilla local target active.")

    # Preserve ordinary thermostat/local-target regulation zeros caused only by
    # passive/stale-control interpretation. Intentional safety/process zeros were
    # returned above and therefore remain authoritative.
    if previous_desired_heat is not None and previous_desired_heat <= base.UTILIZATION_TOLERANCE:
        guarded["desired_heat_utilization"] = preserved_heat_value
        guarded["heat_utilization_action_needed"] = False
    guarded["desired_heater_on"] = True if guarded.get("heater_on") else guarded.get("desired_heater_on")
    guarded["heater_stop_needed"] = False

    action_needed = _action_needed(guarded)
    connected = bool(guarded.get("connected"))
    guarded.update(
        {
            "brewzilla_local_heat_preserve_active": True,
            "brewzilla_local_heat_preserve_bypassed": False,
            "brewzilla_local_heat_preserve_reason": "target_active_brewzilla_regulates_locally",
            "brewzilla_local_heat_preserve_original_desired_heat": previous_desired_heat,
            "brewzilla_local_heat_preserve_current_heat": current_heat,
            "brewzilla_local_heat_preserve_target": _num(guarded.get("applied_target"))
            or _num(guarded.get("brewzilla_device_target"))
            or _num(guarded.get("requested_target")),
            "can_apply_target": connected and action_needed,
            "orchestration_mode": "direct-control" if connected and action_needed else "local-control",
            "control_reason": (
                f"{original_reason} BrewZilla local heat preserve: active target is known, so BA does not send heat 0% "
                "or heater OFF for ordinary local-regulation/stale-readback decisions."
            ),
        }
    )
    return guarded


def build_orchestration_snapshot(hass) -> dict[str, Any]:
    assert _BASE_BUILD is not None
    return _apply_guard(_BASE_BUILD(hass))


def install_local_regulation_heat_guard() -> None:
    """Install final heat-preservation patch for active BrewZilla targets."""
    global _BASE_BUILD, _INSTALLED
    if _INSTALLED:
        return
    _BASE_BUILD = base.build_orchestration_snapshot
    base.build_orchestration_snapshot = build_orchestration_snapshot
    _INSTALLED = True
