"""Runtime patch for mash-in target resolution and pump/anti-drop behavior.

This patch is intentionally small and late-bound. The original mash-in gate is
kept as the owner of the two-button flow, while this module fixes the process
logic around the gate:

* ready for mash-in: keep the pump running/circulating until the operator
  presses Mash-In Started
* after Mash-In Started: prefer the active mash step target from Brewfather
  (`target_temperature` / `tracker_target`) over any latched strike target
* while mash-in is started and pump is paused: never apply anti-drop heat when
  the measured mash temperature is already at or above the effective mash target
"""

from __future__ import annotations

from typing import Any

from ..brewday.brewday_runtime import build_brewday_runtime_snapshot
from . import brewzilla_mash_in_gate as gate
from . import brewzilla_orchestration as orchestration

_INSTALLED = False
_ORIGINAL_EFFECTIVE_TARGET = None
_ORIGINAL_STARTED_HOLD = None
_ORIGINAL_FORCE_PUMP_PAUSE = None
_TARGET_TOLERANCE_C = 0.05
READY_PUMP_UTILIZATION = 50.0


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _text(snapshot: dict[str, Any], *keys: str) -> str:
    return " ".join(str(snapshot.get(key) or "") for key in keys).lower()


def _current_mash_step_target(hass, snapshot: dict[str, Any]) -> tuple[float | None, str | None]:
    """Return the active mash step target, not the latched strike target.

    BrewAssistant may keep `requested_target` on a strike/boost value while the
    Brewfather runtime has already advanced to the first real mash hold. In the
    event log this looked like `requested_target: 71.8` while the actual audit
    runtime step was `Hold 66°C` with `target_temperature: 66`.

    Important nuance: the orchestration snapshot does not always carry the raw
    Brewfather `target_temperature`. The audit layer can show it because it is
    recorded from Brewday Runtime separately. Therefore this function reads the
    current Brewday Runtime snapshot directly before falling back to fields that
    happen to be present in the orchestration snapshot.
    """
    runtime = build_brewday_runtime_snapshot(hass)

    stage_text = _text(snapshot, "runtime_stage", "stage") or _text(runtime, "stage")
    if stage_text and "mash" not in stage_text and "mäsk" not in stage_text:
        return None, None

    step_text = " ".join(
        part
        for part in (
            _text(snapshot, "runtime_step", "step", "runtime_raw_step_name", "raw_step_name"),
            _text(runtime, "step", "raw_step_name"),
        )
        if part
    )
    requested = _num(snapshot.get("requested_target"))

    candidates: tuple[tuple[Any, str], ...] = (
        (runtime.get("target_temperature"), "brewday_runtime:target_temperature"),
        (runtime.get("tracker_target"), "brewday_runtime:tracker_target"),
        (snapshot.get("target_temperature"), "target_temperature"),
        (snapshot.get("tracker_target"), "tracker_target"),
        (snapshot.get("runtime_target_temperature"), "runtime_target_temperature"),
        (snapshot.get("runtime_tracker_target"), "runtime_tracker_target"),
    )

    for raw_value, source in candidates:
        value = _num(raw_value)
        if value is None:
            continue

        # A lower active Brewfather target is almost certainly the real mash
        # target after strike water has been reached.
        if requested is None or value < requested - _TARGET_TOLERANCE_C:
            return value, source

        # Hold/mash steps should trust the runtime target even if it happens to
        # equal the requested value.
        if any(word in step_text for word in ("hold", "mash", "mäsk")):
            return value, source

    return None, None


def _effective_mash_in_target(hass, snapshot: dict[str, Any]) -> tuple[float | None, str | None, float | None, str | None]:
    assert _ORIGINAL_EFFECTIVE_TARGET is not None

    step_target, step_source = _current_mash_step_target(hass, snapshot)
    current_target = gate._target_for_gate(snapshot)
    next_target, next_source = gate._next_temperature_target(hass)

    if step_target is not None:
        return step_target, f"active_mash_step:{step_source}", next_target, next_source

    if current_target is not None and next_target is not None and next_target <= current_target + _TARGET_TOLERANCE_C:
        return next_target, "next_mash_step", next_target, next_source

    return current_target, "current_step", next_target, next_source


def _force_pump_run_until_mash_in_started(snapshot: dict[str, Any], store: dict[str, Any]) -> dict[str, Any]:
    """Keep pump ON while strike temp is reached and BA waits for mash-in start.

    The original gate paused the pump as soon as mash-in was ready. That made the
    strike water stratify while waiting for the operator. Desired process:

    * heat strike / ready_for_mash_in: pump ON, circulate normally
    * Mash-In Started pressed: pump OFF while malt is added
    * Mash-In Complete pressed: pump ON again
    """
    current_pump_utilization = _num(snapshot.get("pump_utilization"))
    pump_on = bool(snapshot.get("pump_on"))
    pump_utilization_action_needed = bool(
        current_pump_utilization is None
        or abs(float(current_pump_utilization) - READY_PUMP_UTILIZATION) > gate.UTILIZATION_TOLERANCE
    )
    pump_action_needed = not pump_on
    action_needed = bool(pump_action_needed or pump_utilization_action_needed)
    can_apply_gate = gate._can_apply_gate(snapshot, action_needed=action_needed)
    reason = str(snapshot.get("control_reason") or "Direct production flow active")

    return {
        **snapshot,
        "pump_recommended": True,
        "desired_pump_on": True,
        "desired_pump_utilization": READY_PUMP_UTILIZATION,
        "pump_action_needed": pump_action_needed,
        "pump_stop_needed": False,
        "pump_utilization_action_needed": pump_utilization_action_needed,
        "can_apply_target": can_apply_gate,
        "orchestration_mode": "direct-control" if can_apply_gate else snapshot.get("orchestration_mode"),
        **gate._gate_fields(store, snapshot, pending=True),
        "control_reason": (
            f"{reason}; mash-in ready gate active, pump remains ON/circulating until "
            "Mash-In Started is pressed."
        ),
    }


def _mash_in_started_hold_snapshot(hass, snapshot: dict[str, Any], store: dict[str, Any]) -> dict[str, Any]:
    assert _ORIGINAL_STARTED_HOLD is not None
    out = _ORIGINAL_STARTED_HOLD(hass, snapshot, store)

    if not out.get("mash_in_started_hold_active"):
        return out

    effective_target = _num(out.get("requested_target") or out.get("mash_in_effective_target") or store.get("effective_target"))
    current = gate._temperature_for_gate(snapshot)
    if effective_target is None or current is None:
        return out

    # Anti-drop heat is only allowed when the mash is below target. At or above
    # target, explicitly suppress heat and stop the heater if needed.
    if current < effective_target:
        return out

    heat_utilization = _num(snapshot.get("heat_utilization"))
    heater_on = bool(snapshot.get("heater_on"))
    heat_action_needed = orchestration._utilization_action_needed(heat_utilization, 0.0)
    heater_stop_needed = heater_on

    action_needed = bool(
        out.get("target_sync_needed")
        or heat_action_needed
        or out.get("pump_utilization_action_needed")
        or out.get("pump_stop_needed")
        or heater_stop_needed
    )
    can_apply = bool(
        snapshot.get("connected", True)
        and action_needed
        and not snapshot.get("abort_lockout_active")
        and gate._runtime_active_enough(snapshot)
        and effective_target is not None
    )

    reason = str(out.get("control_reason") or "Direct production flow active")
    return {
        **out,
        "heating_needed": False,
        "desired_heat_utilization": 0.0,
        "desired_heater_on": False,
        "heat_utilization_action_needed": heat_action_needed,
        "heater_action_needed": False,
        "heater_stop_needed": heater_stop_needed,
        "mash_in_started_hold_phase": "at_or_above_effective_target",
        "mash_in_started_delta_to_effective_target": round(effective_target - current, 2),
        "can_apply_target": can_apply,
        "orchestration_mode": "direct-control" if can_apply else "monitor",
        "control_reason": (
            f"{reason}; mash-in target patch: current mash temperature {round(current, 2)}°C "
            f"is at/above effective target {round(effective_target, 2)}°C, so anti-drop heat is suppressed."
        ),
    }


def install_mash_in_target_patch() -> None:
    """Install late-bound mash-in target/pump/heat corrections."""
    global _INSTALLED, _ORIGINAL_EFFECTIVE_TARGET, _ORIGINAL_STARTED_HOLD, _ORIGINAL_FORCE_PUMP_PAUSE
    if _INSTALLED:
        return

    _ORIGINAL_EFFECTIVE_TARGET = gate._effective_mash_in_target
    _ORIGINAL_STARTED_HOLD = gate._mash_in_started_hold_snapshot
    _ORIGINAL_FORCE_PUMP_PAUSE = gate._force_pump_pause
    gate._effective_mash_in_target = _effective_mash_in_target
    gate._mash_in_started_hold_snapshot = _mash_in_started_hold_snapshot
    gate._force_pump_pause = _force_pump_run_until_mash_in_started
    _INSTALLED = True
