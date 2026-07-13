"""Transition refresh and overshoot brake for BrewZilla heat-strike handoff.

Brewfather can leave the strike-water ramp and pause on the first mash hold /
mash-additions step while BrewZilla/RCL still echoes the previous boosted
control target.  In that handoff window BrewAssistant should refresh the RCL
surface and stop using boosted strike targets aggressively.  Mash/BLE may still
be useful for the ready gate, but the hottest available kettle/wort reading must
be allowed to brake heating early.

When mash-in has been completed and BA is handing BrewZilla to the real mash
hold, BA should also force a fresh RCL readback so the new mash target, pump
state and heat state are visible before normal mash control continues.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant

from . import brewzilla_advice_control as advice_control
from . import brewzilla_heat_strike_profile as heat_strike

_INSTALLED = False
_ORIGINAL_APPLY_PRE_MASH_IN_HEAT_STRIKE_PROFILE = None

_RCL_TRANSITION_REFRESH_MIN_INTERVAL_SECONDS = 20
_RCL_REFRESH_ENTITY_IDS = [
    "sensor.brewzilla_temperature",
    "sensor.brewzilla_power",
    "sensor.brewzilla_connection",
    "number.brewzilla_target_temperature",
    "number.brewzilla_heat_utilization",
    "number.brewzilla_pump_utilization",
    "switch.brewzilla_heater",
    "switch.brewzilla_pump",
    "sensor.brewzilla_ble_thermometer_temperature",
    "sensor.brewzilla_control_device_temperature",
]


# Conservative brake thresholds for the post-ramp / pre-mash-in paused window.
# The log from real BrewZilla testing showed 2+ °C/min temperature rise and a
# large wort overshoot while mash/BLE lagged.  These values deliberately prefer
# slowing down a little too early over carrying boosted heat into the mash-in
# pause.
_FAST_RISE_C_PER_MIN = 1.0
_VERY_FAST_RISE_C_PER_MIN = 2.0
_BRAKE_FAST_WINDOW_C = 8.0
_BRAKE_VERY_FAST_WINDOW_C = 15.0
_BRAKE_NEAR_WINDOW_C = 5.0
_BRAKE_FINAL_WINDOW_C = 1.0
_TRANSITION_FAST_HOLD_HEAT = 20.0
_TRANSITION_NEAR_HOLD_HEAT = 10.0
_TRANSITION_FINAL_HOLD_HEAT = 0.0


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _rcl_store(hass: HomeAssistant) -> dict[str, Any]:
    return hass.data.setdefault("brewassistant", {}).setdefault(
        "brewzilla_heat_strike_transition_guard",
        {
            "last_transition_key": None,
            "last_requested_at": None,
            "last_entity_ids": [],
            "last_error": None,
        },
    )


def _known_refresh_entity_ids(hass: HomeAssistant) -> list[str]:
    return [entity_id for entity_id in _RCL_REFRESH_ENTITY_IDS if hass.states.get(entity_id) is not None]


def _transition_key(out: dict[str, Any], reason: str) -> str:
    return "|".join(
        [
            reason,
            *(
                str(out.get(key) or "")
                for key in (
                    "source",
                    "runtime_stage",
                    "runtime_step",
                    "target_temperature",
                    "tracker_target",
                    "heat_strike_target",
                    "heat_strike_next_mash_target",
                    "mash_in_gate_state",
                    "requested_target",
                    "applied_target",
                )
            ),
        ]
    )


def _request_transition_rcl_refresh(hass: HomeAssistant, out: dict[str, Any], *, reason: str) -> dict[str, Any]:
    store = _rcl_store(hass)
    now = datetime.now(UTC)
    key = _transition_key(out, reason)
    last_requested = store.get("last_requested_at")
    recently_requested = bool(
        isinstance(last_requested, datetime)
        and now - last_requested < timedelta(seconds=_RCL_TRANSITION_REFRESH_MIN_INTERVAL_SECONDS)
    )

    if store.get("last_transition_key") == key and recently_requested:
        return {
            "rcl_transition_refresh_requested": False,
            "rcl_transition_refresh_reason": "already_requested",
            "rcl_transition_refresh_trigger": reason,
            "rcl_transition_refresh_last_requested_at": last_requested.isoformat() if last_requested else None,
            "rcl_transition_refresh_entity_ids": list(store.get("last_entity_ids") or []),
            "rcl_transition_refresh_error": store.get("last_error"),
        }

    entity_ids = _known_refresh_entity_ids(hass)
    store["last_transition_key"] = key
    store["last_requested_at"] = now
    store["last_entity_ids"] = entity_ids

    if not entity_ids:
        store["last_error"] = "no_known_rcl_entities"
        return {
            "rcl_transition_refresh_requested": False,
            "rcl_transition_refresh_reason": "no_known_rcl_entities",
            "rcl_transition_refresh_trigger": reason,
            "rcl_transition_refresh_last_requested_at": now.isoformat(),
            "rcl_transition_refresh_entity_ids": [],
            "rcl_transition_refresh_error": store["last_error"],
        }

    try:
        hass.async_create_task(
            hass.services.async_call(
                "homeassistant",
                "update_entity",
                {"entity_id": entity_ids},
                blocking=False,
            )
        )
    except Exception as exc:  # pragma: no cover - defensive HA runtime guard
        store["last_error"] = f"{type(exc).__name__}: {exc}"
        return {
            "rcl_transition_refresh_requested": False,
            "rcl_transition_refresh_reason": "service_error",
            "rcl_transition_refresh_trigger": reason,
            "rcl_transition_refresh_last_requested_at": now.isoformat(),
            "rcl_transition_refresh_entity_ids": entity_ids,
            "rcl_transition_refresh_error": store["last_error"],
        }

    store["last_error"] = None
    return {
        "rcl_transition_refresh_requested": True,
        "rcl_transition_refresh_reason": reason,
        "rcl_transition_refresh_trigger": reason,
        "rcl_transition_refresh_last_requested_at": now.isoformat(),
        "rcl_transition_refresh_entity_ids": entity_ids,
        "rcl_transition_refresh_error": None,
    }


def _hottest_transition_temperature(out: dict[str, Any]) -> tuple[float | None, str | None]:
    candidates: list[tuple[str, float]] = []
    for key in (
        "wort_temperature",
        "current_temperature",
        "brewzilla_current_temp",
        "advice_learning_temperature",
        "mash_temperature",
    ):
        value = _num(out.get(key))
        if value is not None:
            candidates.append((key, value))
    if not candidates:
        return None, None
    source, value = max(candidates, key=lambda item: item[1])
    return value, source


def _braked_heat(original_heat: float, strike_target: float, guard_temp: float | None, temp_rate: float | None) -> tuple[float, str, float | None]:
    if guard_temp is None:
        return min(original_heat, _TRANSITION_FAST_HOLD_HEAT), "transition_unknown_temp_no_boost", None

    delta_to_strike = round(strike_target - guard_temp, 2)
    rate = temp_rate if temp_rate is not None else 0.0

    if delta_to_strike <= _BRAKE_FINAL_WINDOW_C:
        return min(original_heat, _TRANSITION_FINAL_HOLD_HEAT), "transition_final_coast", delta_to_strike
    if rate >= _FAST_RISE_C_PER_MIN and delta_to_strike <= _BRAKE_FAST_WINDOW_C:
        return min(original_heat, _TRANSITION_FINAL_HOLD_HEAT), "transition_fast_rise_coast", delta_to_strike
    if rate >= _VERY_FAST_RISE_C_PER_MIN and delta_to_strike <= _BRAKE_VERY_FAST_WINDOW_C:
        return min(original_heat, _TRANSITION_FAST_HOLD_HEAT), "transition_very_fast_rise_low_hold", delta_to_strike
    if delta_to_strike <= _BRAKE_NEAR_WINDOW_C:
        return min(original_heat, _TRANSITION_NEAR_HOLD_HEAT), "transition_near_strike_low_hold", delta_to_strike
    if delta_to_strike <= _BRAKE_FAST_WINDOW_C:
        return min(original_heat, _TRANSITION_FAST_HOLD_HEAT), "transition_approach_low_hold", delta_to_strike

    return original_heat, "transition_no_brake", delta_to_strike


def _transition_brake_active(out: dict[str, Any]) -> bool:
    return bool(
        out.get("advice_physical_phase") == "pre_mash_in_paused_wait"
        and _num(out.get("heat_strike_target")) is not None
        and _num(out.get("heat_strike_next_mash_target")) is not None
        and str(out.get("brewday_state") or "").lower() in {"paused", "awaiting_confirm", "prepared", "awaiting_snapshot"}
    )


def _post_mash_in_refresh_active(out: dict[str, Any]) -> bool:
    gate_state = str(out.get("mash_in_gate_state") or "").lower()
    runtime_state = str(out.get("brewday_state") or "idle").lower()
    stage_text = " ".join(str(out.get(key) or "") for key in ("runtime_stage", "runtime_step", "runtime_raw_step_name")).lower()
    return bool(
        gate_state == "mash_in_complete"
        and runtime_state in {"live", "running", "paused", "awaiting_snapshot", "prepared", "awaiting_confirm"}
        and not out.get("abort_lockout_active")
        and not out.get("completed_runtime")
        and out.get("connected", True)
        and (not stage_text or "mash" in stage_text or "mäsk" in stage_text)
    )


def _apply_post_mash_in_refresh_guard(hass: HomeAssistant, out: dict[str, Any]) -> dict[str, Any]:
    if not _post_mash_in_refresh_active(out):
        return out

    guarded = dict(out)
    refresh_attrs = _request_transition_rcl_refresh(
        hass,
        guarded,
        reason="mash_in_complete_mash_control_handoff",
    )
    original_reason = str(guarded.get("control_reason") or "BrewZilla mash control handoff active.")
    guarded.update(
        {
            **refresh_attrs,
            "rcl_post_mash_in_refresh_active": True,
            "rcl_post_mash_in_refresh_reason": "mash_in_complete_mash_control_handoff",
            "control_reason": (
                f"{original_reason} Post mash-in RCL refresh: Mash-In Complete is active and BA is handing BrewZilla "
                "to real mash control; a fresh RCL readback was requested for target, pump, heat and temperature echo."
            ),
        }
    )
    return guarded


def _apply_transition_guard(hass: HomeAssistant, out: dict[str, Any]) -> dict[str, Any]:
    if not _transition_brake_active(out):
        return out

    strike_target = _num(out.get("heat_strike_target"))
    if strike_target is None:
        return out

    guarded = dict(out)
    refresh_attrs = _request_transition_rcl_refresh(
        hass,
        guarded,
        reason="brewfather_left_strike_ramp",
    )

    requested_target = _num(guarded.get("requested_target"))
    control_target = min(requested_target, strike_target) if requested_target is not None else strike_target
    original_heat = _num(guarded.get("desired_heat_utilization"))
    if original_heat is None:
        original_heat = _num(guarded.get("advice_local_profile_heat_utilization"))
    if original_heat is None:
        original_heat = 0.0

    guard_temp, guard_source = _hottest_transition_temperature(guarded)
    temp_rate = _num(guarded.get("advice_temp_rate_c_per_min"))
    braked_heat, brake_phase, delta_to_strike = _braked_heat(original_heat, strike_target, guard_temp, temp_rate)
    desired_heater_on = braked_heat > 0.0

    applied_target = advice_control._num(guarded.get("applied_target"))
    target_delta = None if applied_target is None else round(control_target - applied_target, 2)
    target_sync_needed = bool(target_delta is not None and abs(target_delta) > advice_control.base.TARGET_SYNC_TOLERANCE)

    heat_util = advice_control._num(guarded.get("heat_utilization"))
    pump_util = advice_control._num(guarded.get("pump_utilization"))
    heater_on = bool(guarded.get("heater_on"))
    pump_on = bool(guarded.get("pump_on"))
    desired_pump = _num(guarded.get("desired_pump_utilization"))
    if desired_pump is None:
        desired_pump = 50.0

    heat_action_needed = advice_control.base._utilization_action_needed(heat_util, braked_heat)
    pump_action_needed = advice_control.base._utilization_action_needed(pump_util, desired_pump)
    heater_action_needed = bool(desired_heater_on and not heater_on)
    heater_stop_needed = bool(not desired_heater_on and heater_on)
    pump_start_needed = bool(guarded.get("desired_pump_on", True) and not pump_on)

    action_needed = bool(
        target_sync_needed
        or heat_action_needed
        or pump_action_needed
        or heater_action_needed
        or heater_stop_needed
        or pump_start_needed
    )
    state = str(guarded.get("brewday_state") or "idle").lower()
    can_apply = bool(
        guarded.get("connected")
        and action_needed
        and not guarded.get("abort_lockout_active")
        and state in {"live", "running", "paused", "awaiting_snapshot", "prepared", "awaiting_confirm"}
        and not guarded.get("completed_runtime")
    )

    original_reason = str(guarded.get("control_reason") or "BrewZilla transition guard active.")
    guarded.update(
        {
            **refresh_attrs,
            "rcl_transition_refresh_active": True,
            "heat_strike_transition_brake_active": brake_phase != "transition_no_brake" or control_target != requested_target,
            "heat_strike_transition_brake_phase": brake_phase,
            "heat_strike_transition_brake_temperature": guard_temp,
            "heat_strike_transition_brake_temperature_source": guard_source,
            "heat_strike_transition_brake_delta_to_strike": delta_to_strike,
            "heat_strike_transition_brake_original_target": requested_target,
            "heat_strike_transition_brake_original_heat": original_heat,
            "requested_target": round(control_target, 1),
            "requested_target_source": "pre_mash_in_paused_wait_transition_brake",
            "target_delta": target_delta,
            "target_sync_needed": target_sync_needed,
            "desired_heat_utilization": round(braked_heat, 1),
            "desired_heater_on": desired_heater_on,
            "heat_utilization_action_needed": heat_action_needed,
            "heater_action_needed": heater_action_needed,
            "heater_stop_needed": heater_stop_needed,
            "pump_utilization_action_needed": pump_action_needed,
            "pump_action_needed": pump_start_needed,
            "can_apply_target": can_apply,
            "orchestration_mode": "direct-control" if can_apply else "monitor",
            "advice_capped_heat_utilization": round(braked_heat, 1),
            "advice_heat_cap": round(braked_heat, 1),
            "advice_heat_profile_phase": brake_phase,
            "advice_local_profile_heat_utilization": round(braked_heat, 1),
            "mash_in_heat_strategy_phase": brake_phase,
            "mash_in_heat_strategy_delta_to_target": delta_to_strike,
            "heat_strike_control_target": round(control_target, 1),
            "heat_strike_phase": brake_phase,
            "heat_strike_delta_to_target": delta_to_strike,
            "heating_needed": desired_heater_on,
            "control_reason": (
                f"{original_reason} Transition guard: Brewfather is paused on the first mash hold/mash-additions step; "
                "RCL refresh requested and strike boost is capped. "
                f"Guard temp {guard_temp}°C ({guard_source}), strike target {round(strike_target, 1)}°C, "
                f"device target {round(control_target, 1)}°C, heat {round(braked_heat, 1)}% ({brake_phase})."
            ),
        }
    )
    return guarded


def _patched_apply_pre_mash_in_heat_strike_profile(hass: HomeAssistant, out: dict[str, Any]) -> dict[str, Any]:
    assert _ORIGINAL_APPLY_PRE_MASH_IN_HEAT_STRIKE_PROFILE is not None
    after_heat_strike = _ORIGINAL_APPLY_PRE_MASH_IN_HEAT_STRIKE_PROFILE(hass, out)
    after_transition_brake = _apply_transition_guard(hass, after_heat_strike)
    return _apply_post_mash_in_refresh_guard(hass, after_transition_brake)


def install_heat_strike_transition_guard() -> None:
    """Install transition refresh/overshoot brake around heat-strike handoff."""
    global _INSTALLED, _ORIGINAL_APPLY_PRE_MASH_IN_HEAT_STRIKE_PROFILE
    if _INSTALLED:
        return

    _ORIGINAL_APPLY_PRE_MASH_IN_HEAT_STRIKE_PROFILE = heat_strike._apply_pre_mash_in_heat_strike_profile
    heat_strike._apply_pre_mash_in_heat_strike_profile = _patched_apply_pre_mash_in_heat_strike_profile
    _INSTALLED = True
