"""RCL value-stale recovery for BrewZilla heat-strike control.

RAPT Cloud Link / Home Assistant may sometimes report fresh entity timestamps
without the underlying temperature value actually changing.  During heat-strike
that is dangerous in two directions: BA may coast too early from one stale hot
value, or it may keep waiting on a stale external mash/BLE value while the kettle
has already moved on.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import brewzilla_advice_control as advice_control
from . import brewzilla_heat_strike_profile as heat_strike
from . import brewzilla_temperature

_INSTALLED = False
_ORIGINAL_APPLY_PRE_MASH_IN_HEAT_STRIKE_PROFILE = None
_ORIGINAL_TEMPERATURE_AGE_SECONDS = None

_DATA_KEY = "brewzilla_rcl_value_recovery_guard"
_RCL_VALUE_STALE_WARN_SECONDS = 120
_RCL_RELOAD_MIN_INTERVAL_SECONDS = 180
_TEMPERATURE_CHANGE_EPSILON_C = 0.05
_GATE_COLD_DELTA_C = 5.0
_INTERNAL_NEAR_STRIKE_COAST_C = 1.0
_LOW_HOLD_HEAT_FAR_FROM_STRIKE = 20.0
_LOW_HOLD_HEAT_NEAR_STRIKE = 10.0

_RCL_RECOVERY_ENTITY_IDS = [
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


_ACTIVE_STATES = {"live", "running", "paused", "awaiting_snapshot", "prepared", "awaiting_confirm"}
_OFF_BRAKE_PHASES = {"transition_fast_rise_coast", "transition_final_coast"}


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _state_value_age_seconds(hass: HomeAssistant, entity_id: str | None) -> int | None:
    """Return age since the actual state value/attributes changed, not last report.

    Home Assistant's last_reported can be refreshed even when RCL repeats an old
    value.  For mash-probe eligibility and RCL safety we need value freshness.
    """
    if not entity_id:
        return None
    state = hass.states.get(entity_id)
    if state is None:
        return None
    updated = state.last_updated
    if updated is None:
        return None
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=UTC)
    return max(0, int(round((datetime.now(UTC) - updated).total_seconds())))


def _store(hass: HomeAssistant) -> dict[str, Any]:
    return hass.data.setdefault("brewassistant", {}).setdefault(
        _DATA_KEY,
        {
            "last_temp": None,
            "last_temp_source": None,
            "last_changed_at": None,
            "last_reload_at": None,
            "last_reload_error": None,
            "last_reload_entity_ids": [],
        },
    )


def _known_entity_ids(hass: HomeAssistant) -> list[str]:
    return [entity_id for entity_id in _RCL_RECOVERY_ENTITY_IDS if hass.states.get(entity_id) is not None]


def _active_heatstrike_context(out: dict[str, Any]) -> bool:
    state = str(out.get("brewday_state") or "idle").strip().lower()
    return bool(
        state in _ACTIVE_STATES
        and not out.get("abort_lockout_active")
        and not out.get("completed_runtime")
        and (
            out.get("advice_physical_phase") == "pre_mash_in_paused_wait"
            or out.get("mash_in_heat_strategy_active")
            or out.get("heat_strike_latch_active")
        )
    )


def _transition_guard_temperature(out: dict[str, Any]) -> tuple[float | None, str | None]:
    for key in (
        "heat_strike_transition_brake_temperature",
        "current_temperature",
        "brewzilla_current_temp",
        "wort_temperature",
        "advice_learning_temperature",
    ):
        value = _num(out.get(key))
        if value is not None:
            return value, key
    return None, None


def _refresh_and_maybe_reload_rcl(hass: HomeAssistant, *, stale_seconds: int, reason: str) -> dict[str, Any]:
    store = _store(hass)
    now = datetime.now(UTC)
    entity_ids = _known_entity_ids(hass)
    update_requested = False
    reload_requested = False
    reload_available = hass.services.has_service("homeassistant", "reload_config_entry")
    error = None

    if entity_ids:
        try:
            hass.async_create_task(
                hass.services.async_call(
                    "homeassistant",
                    "update_entity",
                    {"entity_id": entity_ids},
                    blocking=False,
                )
            )
            update_requested = True
        except Exception as exc:  # pragma: no cover - defensive HA runtime guard
            error = f"update_entity:{type(exc).__name__}: {exc}"

    last_reload = store.get("last_reload_at")
    reload_recent = bool(
        isinstance(last_reload, datetime)
        and now - last_reload < timedelta(seconds=_RCL_RELOAD_MIN_INTERVAL_SECONDS)
    )

    if entity_ids and reload_available and not reload_recent:
        try:
            hass.async_create_task(
                hass.services.async_call(
                    "homeassistant",
                    "reload_config_entry",
                    {"entity_id": entity_ids},
                    blocking=False,
                )
            )
            reload_requested = True
            store["last_reload_at"] = now
            store["last_reload_entity_ids"] = entity_ids
            store["last_reload_error"] = None
        except Exception as exc:  # pragma: no cover - defensive HA runtime guard
            error = f"reload_config_entry:{type(exc).__name__}: {exc}"
            store["last_reload_error"] = error

    if error:
        store["last_reload_error"] = error

    return {
        "rcl_value_stale_guard_refresh_requested": update_requested,
        "rcl_value_stale_guard_reload_requested": reload_requested,
        "rcl_value_stale_guard_reload_available": reload_available,
        "rcl_value_stale_guard_reload_recently_requested": reload_recent,
        "rcl_value_stale_guard_reload_interval_seconds": _RCL_RELOAD_MIN_INTERVAL_SECONDS,
        "rcl_value_stale_guard_last_reload_at": store.get("last_reload_at").isoformat()
        if isinstance(store.get("last_reload_at"), datetime)
        else None,
        "rcl_value_stale_guard_entity_ids": entity_ids,
        "rcl_value_stale_guard_error": error or store.get("last_reload_error"),
        "rcl_value_stale_guard_reason": reason,
        "rcl_value_stale_guard_stale_seconds": stale_seconds,
    }


def _track_rcl_value_staleness(hass: HomeAssistant, out: dict[str, Any]) -> dict[str, Any]:
    if not _active_heatstrike_context(out):
        return out

    temp, source = _transition_guard_temperature(out)
    if temp is None:
        return out

    guarded = dict(out)
    store = _store(hass)
    now = datetime.now(UTC)
    previous = _num(store.get("last_temp"))
    previous_source = store.get("last_temp_source")
    changed_at = store.get("last_changed_at")

    if (
        previous is None
        or previous_source != source
        or abs(float(temp) - float(previous)) >= _TEMPERATURE_CHANGE_EPSILON_C
        or not isinstance(changed_at, datetime)
    ):
        store["last_temp"] = float(temp)
        store["last_temp_source"] = source
        store["last_changed_at"] = now
        guarded.update(
            {
                "rcl_value_stale_guard_active": False,
                "rcl_value_stale_guard_temperature": float(temp),
                "rcl_value_stale_guard_temperature_source": source,
                "rcl_value_stale_guard_stale_seconds": 0,
                "rcl_value_stale_guard_warn_seconds": _RCL_VALUE_STALE_WARN_SECONDS,
            }
        )
        return guarded

    stale_seconds = max(0, int((now - changed_at).total_seconds()))
    guarded.update(
        {
            "rcl_value_stale_guard_active": stale_seconds >= _RCL_VALUE_STALE_WARN_SECONDS,
            "rcl_value_stale_guard_temperature": float(temp),
            "rcl_value_stale_guard_temperature_source": source,
            "rcl_value_stale_guard_stale_seconds": stale_seconds,
            "rcl_value_stale_guard_warn_seconds": _RCL_VALUE_STALE_WARN_SECONDS,
        }
    )

    if stale_seconds < _RCL_VALUE_STALE_WARN_SECONDS:
        return guarded

    recovery_attrs = _refresh_and_maybe_reload_rcl(
        hass,
        stale_seconds=stale_seconds,
        reason="heatstrike_temperature_value_not_changing",
    )
    guarded.update({**recovery_attrs, "rapt_critical_refresh_recommended": True})
    guarded["control_reason"] = (
        str(guarded.get("control_reason") or "")
        + f" RCL value-stale guard: {source} has stayed at {round(float(temp), 2)}°C for {stale_seconds}s; "
        "update_entity was requested and reload_config_entry is attempted when available/throttled."
    ).strip()
    return guarded


def _gate_temperature(out: dict[str, Any]) -> float | None:
    for key in (
        "heat_strike_control_temperature",
        "mash_temperature",
        "advice_learning_temperature",
        "mash_in_gate_current_temperature",
    ):
        value = _num(out.get(key))
        if value is not None:
            return value
    return None


def _apply_low_hold_floor_while_gate_cold(out: dict[str, Any]) -> dict[str, Any]:
    phase = str(out.get("heat_strike_transition_brake_phase") or "")
    if phase not in _OFF_BRAKE_PHASES:
        return out
    if out.get("advice_physical_phase") != "pre_mash_in_paused_wait":
        return out

    strike_target = _num(out.get("heat_strike_target"))
    guard_temp = _num(out.get("heat_strike_transition_brake_temperature"))
    gate_temp = _gate_temperature(out)
    if strike_target is None or guard_temp is None or gate_temp is None:
        return out

    gate_delta = round(strike_target - gate_temp, 2)
    guard_delta = round(strike_target - guard_temp, 2)

    # Coasting is fine once the hottest sensor is basically at strike, or the
    # operator-facing mash/BLE gate is close.  Before that, do not let one stale
    # fast-rise sample park heat-strike indefinitely.
    if gate_delta <= _GATE_COLD_DELTA_C or guard_delta <= _INTERNAL_NEAR_STRIKE_COAST_C:
        return out

    desired_heat = _LOW_HOLD_HEAT_NEAR_STRIKE if guard_delta <= 3.0 else _LOW_HOLD_HEAT_FAR_FROM_STRIKE
    guarded = dict(out)
    heat_util = advice_control._num(guarded.get("heat_utilization"))
    pump_util = advice_control._num(guarded.get("pump_utilization"))
    desired_pump = advice_control._num(guarded.get("desired_pump_utilization"))
    if desired_pump is None:
        desired_pump = 50.0

    heater_on = bool(guarded.get("heater_on"))
    pump_on = bool(guarded.get("pump_on"))
    heat_needed = advice_control.base._utilization_action_needed(heat_util, desired_heat)
    pump_needed = advice_control.base._utilization_action_needed(pump_util, desired_pump)
    heater_action_needed = bool(not heater_on)
    pump_action_needed = bool(not pump_on)
    target_sync_needed = bool(guarded.get("target_sync_needed"))
    action_needed = bool(target_sync_needed or heat_needed or pump_needed or heater_action_needed or pump_action_needed)
    state = str(guarded.get("brewday_state") or "idle").lower()

    guarded.update(
        {
            "heat_strike_transition_low_hold_floor_active": True,
            "heat_strike_transition_low_hold_floor_reason": "mash_gate_still_far_below_strike",
            "heat_strike_transition_low_hold_floor_gate_temperature": gate_temp,
            "heat_strike_transition_low_hold_floor_gate_delta_to_strike": gate_delta,
            "heat_strike_transition_low_hold_floor_guard_delta_to_strike": guard_delta,
            "desired_heat_utilization": desired_heat,
            "desired_heater_on": True,
            "heating_needed": True,
            "heat_utilization_action_needed": heat_needed,
            "heater_action_needed": heater_action_needed,
            "heater_stop_needed": False,
            "pump_utilization_action_needed": pump_needed,
            "pump_action_needed": pump_action_needed,
            "pump_stop_needed": False,
            "can_apply_target": bool(
                guarded.get("connected")
                and action_needed
                and not guarded.get("abort_lockout_active")
                and state in _ACTIVE_STATES
                and not guarded.get("completed_runtime")
            ),
            "orchestration_mode": "direct-control" if action_needed else "monitor",
            "advice_capped_heat_utilization": desired_heat,
            "advice_heat_cap": desired_heat,
            "advice_heat_profile_phase": "transition_low_hold_floor",
            "advice_local_profile_heat_utilization": desired_heat,
            "mash_in_heat_strategy_phase": "transition_low_hold_floor",
            "heat_strike_phase": "transition_low_hold_floor",
            "heat_strike_transition_brake_phase": "transition_low_hold_floor",
            "control_reason": (
                str(guarded.get("control_reason") or "")
                + f" Low-hold floor: mash gate is still {gate_delta}°C below strike while guard temp is {guard_delta}°C below strike; "
                f"holding {desired_heat}% instead of coasting to 0%."
            ).strip(),
        }
    )
    return guarded


def _patched_apply_pre_mash_in_heat_strike_profile(hass: HomeAssistant, out: dict[str, Any]) -> dict[str, Any]:
    assert _ORIGINAL_APPLY_PRE_MASH_IN_HEAT_STRIKE_PROFILE is not None
    guarded = _ORIGINAL_APPLY_PRE_MASH_IN_HEAT_STRIKE_PROFILE(hass, out)
    guarded = _apply_low_hold_floor_while_gate_cold(guarded)
    guarded = _track_rcl_value_staleness(hass, guarded)
    return guarded


def install_rcl_value_recovery_guard() -> None:
    """Install RCL value-freshness and heat-strike recovery patches."""
    global _INSTALLED, _ORIGINAL_APPLY_PRE_MASH_IN_HEAT_STRIKE_PROFILE, _ORIGINAL_TEMPERATURE_AGE_SECONDS
    if _INSTALLED:
        return

    _ORIGINAL_TEMPERATURE_AGE_SECONDS = brewzilla_temperature._state_age_seconds
    brewzilla_temperature._state_age_seconds = _state_value_age_seconds

    _ORIGINAL_APPLY_PRE_MASH_IN_HEAT_STRIKE_PROFILE = heat_strike._apply_pre_mash_in_heat_strike_profile
    heat_strike._apply_pre_mash_in_heat_strike_profile = _patched_apply_pre_mash_in_heat_strike_profile

    _INSTALLED = True
