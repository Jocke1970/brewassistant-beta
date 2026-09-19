"""Explicit BrewTracker temperature-checkpoint guard for BrewZilla.

Brewfather/Brew Tracker may use a zero-minute step whose name starts with
``PAUS``/``PAUSE`` as a deliberate operator checkpoint after a temperature ramp.
While that checkpoint is paused, BrewAssistant must keep controlling only the
checkpoint's current BrewTracker target.  It must never pre-actuate a later
``next_step`` target.

This is intentionally narrower than generic BrewTracker pause handling.  The
existing pre-mash-in Mash-In/additions pause keeps its dedicated strike-water
latch semantics and is not reinterpreted unless the recipe step is explicitly
named as a PAUS/PAUSE checkpoint.
"""

from __future__ import annotations

from typing import Any

from ..brewday.brewday_runtime import build_brewday_runtime_snapshot
from . import brewzilla_advice_control as advice_control
from . import brewzilla_orchestration as base

_BASE_BUILD = None
_INSTALLED = False

_CHECKPOINT_PREFIXES = ("paus", "pause")
_READY_TOLERANCE_C = 0.3


def _num(value: Any) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def _checkpoint_name(runtime: dict[str, Any], snapshot: dict[str, Any]) -> str:
    return str(
        runtime.get("raw_step_name")
        or snapshot.get("runtime_raw_step_name")
        or ""
    ).strip()


def _is_explicit_checkpoint(runtime: dict[str, Any], snapshot: dict[str, Any]) -> bool:
    """Return true only for the documented BrewTracker PAUS/PAUSE convention."""
    if str(runtime.get("source") or snapshot.get("runtime_source") or "") != "Brewfather Brew Tracker":
        return False
    if str(runtime.get("runtime_state") or snapshot.get("brewday_state") or "").lower() != "paused":
        return False

    name = _checkpoint_name(runtime, snapshot).lower()
    if not name.startswith(_CHECKPOINT_PREFIXES):
        return False

    target = _num(runtime.get("target_temperature"))
    if target is None:
        return False

    # A real checkpoint is expected to be sitting at the zero-time boundary.
    # The name prefix is the semantic contract; the zero-time check prevents an
    # ordinary long PAUS-labelled rest from silently gaining this behavior.
    remaining = _num(runtime.get("time_remaining_seconds"))
    return remaining is None or remaining <= 0.0


def _process_temperature(snapshot: dict[str, Any]) -> tuple[float | None, str | None]:
    """Return the physical temperature used to decide checkpoint readiness."""
    for key in (
        "mash_temperature",
        "advice_learning_temperature",
        "current_temperature",
        "brewzilla_current_temp",
    ):
        value = _num(snapshot.get(key))
        if value is not None:
            return value, key
    return None, None


def _only_paused_rewind_block(snapshot: dict[str, Any]) -> bool:
    reason = str(snapshot.get("control_reason") or "")
    return bool(
        snapshot.get("paused_target_rewind_blocked")
        and reason == "Paused target rewind guard active"
    )


def _independent_block(snapshot: dict[str, Any]) -> bool:
    """Keep independent safety/telemetry blocks authoritative."""
    if snapshot.get("abort_lockout_active") or snapshot.get("completed_runtime"):
        return True
    if snapshot.get("execution_desync_active") or snapshot.get("execution_desync"):
        return True
    if snapshot.get("rcl_freshness_guard_blocking"):
        return True
    if snapshot.get("rcl_degraded") or snapshot.get("heat_strike_rcl_degraded"):
        return True
    if not snapshot.get("connected"):
        return True
    return bool(
        snapshot.get("orchestration_mode") == "blocked"
        and not _only_paused_rewind_block(snapshot)
    )


def _checkpoint_heat_cap(snapshot: dict[str, Any], delta_to_target: float | None) -> tuple[float | None, str | None]:
    """Return a safe ramp heat cap for the checkpoint's own target.

    Existing downstream safety may already request less heat.  The guard only
    caps that value further; it never increases heat above another layer's
    request.  This makes a stale/higher latched target unable to keep heating
    once the checkpoint target itself has been reached.
    """
    if delta_to_target is None:
        return None, None
    temp_rate = _num(snapshot.get("advice_temp_rate_c_per_min"))
    return advice_control._base_heat_profile("ramp", delta_to_target, temp_rate)


def _apply_checkpoint_target(
    snapshot: dict[str, Any],
    runtime: dict[str, Any],
) -> dict[str, Any]:
    out = dict(snapshot)
    if not _is_explicit_checkpoint(runtime, out):
        out["brewtracker_pause_checkpoint_active"] = False
        return out

    target = _num(runtime.get("target_temperature"))
    assert target is not None
    target = round(target, 1)
    applied = _num(out.get("applied_target"))
    process_temp, process_source = _process_temperature(out)
    target_delta = None if applied is None else round(target - applied, 2)
    process_delta = None if process_temp is None else round(target - process_temp, 2)
    target_sync_needed = bool(
        target_delta is not None and abs(target_delta) > base.TARGET_SYNC_TOLERANCE
    )
    ready = bool(
        process_temp is not None
        and process_temp >= target - _READY_TOLERANCE_C
    )

    existing_heat = _num(out.get("desired_heat_utilization"))
    heat_cap, heat_phase = _checkpoint_heat_cap(out, process_delta)
    desired_heat = existing_heat
    if heat_cap is not None:
        desired_heat = heat_cap if existing_heat is None else min(existing_heat, heat_cap)
        desired_heat = round(max(0.0, desired_heat), 1)

    desired_heater_on = out.get("desired_heater_on")
    if desired_heat is not None:
        if desired_heat <= base.UTILIZATION_TOLERANCE:
            desired_heater_on = False
        elif desired_heater_on is None:
            desired_heater_on = True

    heat_utilization_action_needed = base._utilization_action_needed(
        _num(out.get("heat_utilization")), desired_heat
    )
    heater_on = bool(out.get("heater_on"))
    heater_action_needed = bool(desired_heater_on is True and not heater_on)
    heater_stop_needed = bool(desired_heater_on is False and heater_on)

    out.update(
        {
            "brewtracker_pause_checkpoint_active": True,
            "brewtracker_pause_checkpoint_name": _checkpoint_name(runtime, out),
            "brewtracker_pause_checkpoint_target": target,
            "brewtracker_pause_checkpoint_temperature": process_temp,
            "brewtracker_pause_checkpoint_temperature_source": process_source,
            "brewtracker_pause_checkpoint_delta_to_target": process_delta,
            "brewtracker_pause_checkpoint_ready": ready,
            "brewtracker_pause_checkpoint_ready_tolerance_c": _READY_TOLERANCE_C,
            "brewtracker_pause_checkpoint_heat_cap": heat_cap,
            "brewtracker_pause_checkpoint_heat_phase": heat_phase,
            # The paused tracker target is authoritative. Never derive control
            # from next_step while the explicit checkpoint is held.
            "requested_target": target,
            "requested_target_source": "brewtracker_paused_checkpoint",
            "target_delta": target_delta,
            "target_sync_needed": target_sync_needed,
            "paused_target_rewind_blocked": False,
            "heating_needed": bool(process_delta is not None and process_delta > base.TARGET_SYNC_TOLERANCE),
            "desired_heat_utilization": desired_heat,
            "desired_heater_on": desired_heater_on,
            "heat_utilization_action_needed": heat_utilization_action_needed,
            "heater_action_needed": heater_action_needed,
            "heater_stop_needed": heater_stop_needed,
        }
    )

    if _independent_block(out):
        out["brewtracker_pause_checkpoint_control_allowed"] = False
        return out

    action_needed = bool(
        target_sync_needed
        or heat_utilization_action_needed
        or heater_action_needed
        or heater_stop_needed
        or out.get("pump_action_needed")
        or out.get("pump_stop_needed")
        or out.get("pump_utilization_action_needed")
    )
    out.update(
        {
            "brewtracker_pause_checkpoint_control_allowed": True,
            "can_apply_target": bool(out.get("connected") and action_needed),
            "orchestration_mode": "direct-control" if action_needed else "monitor",
            "control_reason": (
                f"BrewTracker PAUS checkpoint: hold target {target:.1f}°C; "
                f"physical temperature {process_temp if process_temp is not None else 'unknown'}°C. "
                "Next-step target is not eligible until Brewfather resumes."
            ),
        }
    )
    return out


def build_orchestration_snapshot(hass) -> dict[str, Any]:
    assert _BASE_BUILD is not None
    snapshot = _BASE_BUILD(hass)
    runtime = build_brewday_runtime_snapshot(hass)
    return _apply_checkpoint_target(snapshot, runtime)


def install_brewtracker_pause_checkpoint_guard() -> None:
    global _BASE_BUILD, _INSTALLED
    if _INSTALLED:
        return
    _BASE_BUILD = base.build_orchestration_snapshot
    base.build_orchestration_snapshot = build_orchestration_snapshot
    _INSTALLED = True
