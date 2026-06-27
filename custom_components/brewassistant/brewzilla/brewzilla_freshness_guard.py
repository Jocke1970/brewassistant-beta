"""BrewZilla RCL freshness guard."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from . import brewzilla_batch_context_guard as _batch_context_guard
from . import brewzilla_orchestration as _base

RAPT_ACTIVE_CONTROL_WARN_AGE_SECONDS = 60
RAPT_ACTIVE_CONTROL_BLOCK_AGE_SECONDS = 90
RCL_REFRESH_THROTTLE_SECONDS = 60
BREWZILLA_SAFE_MODE_ENTITY = "switch.brewassistant_brewzilla_safe_mode"

RCL_REFRESH_ENTITY_IDS = [
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

_BASE_BUILD_ORCHESTRATION_SNAPSHOT = None
_INSTALLED = False
_REFETCH_LAST_REQUESTED_AT: datetime | None = None
_REFRESH_LAST_REQUESTED_AT: datetime | None = None
_REFRESH_LAST_AGE_SECONDS: int | None = None
_REFRESH_LAST_SOURCE: str | None = None
_REFRESH_LAST_ENTITY_IDS: list[str] = []
_REFRESH_LAST_ERROR: str | None = None


def _runtime_active(state: Any) -> bool:
    return _base._runtime_active(str(state or "idle"))


def _as_number(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _utilization_action_needed(current: Any, desired: float | None) -> bool:
    if desired is None:
        return False
    current_value = _as_number(current)
    if current_value is None:
        return True
    return abs(float(desired) - current_value) > _base.UTILIZATION_TOLERANCE


def _safe_mode_enabled(hass) -> bool:
    state = hass.states.get(BREWZILLA_SAFE_MODE_ENTITY)
    if state is None:
        return True
    return str(state.state).lower() != "off"


def _active_control_context(snapshot: dict[str, Any]) -> bool:
    # ABORT/desync are higher-level safety states. RCL freshness must not
    # overwrite their mode/reason, otherwise the UI says abort_lockout while the
    # reason says stale RCL. Keep RCL age visible, but do not let this guard own
    # control while those gates are active.
    if snapshot.get("abort_lockout_active"):
        return False
    if snapshot.get("execution_desync") or snapshot.get("execution_desync_active"):
        return False
    if not _runtime_active(snapshot.get("brewday_state")):
        return False
    if bool(snapshot.get("completed_runtime")):
        return False
    return bool(
        snapshot.get("mash_in_heat_strategy_active")
        or snapshot.get("mash_hold_strategy_active")
        or snapshot.get("boil_stage")
        or snapshot.get("target_sync_needed")
        or snapshot.get("heater_action_needed")
        or snapshot.get("pump_action_needed")
        or snapshot.get("heat_utilization_action_needed")
        or snapshot.get("pump_utilization_action_needed")
    )


def _known_refresh_entity_ids(hass) -> list[str]:
    return [entity_id for entity_id in RCL_REFRESH_ENTITY_IDS if hass.states.get(entity_id) is not None]


def _refresh_state_attrs(requested: bool) -> dict[str, Any]:
    return {
        "rcl_refresh_requested": requested,
        "rcl_refresh_last_requested_at": _REFRESH_LAST_REQUESTED_AT.isoformat() if _REFRESH_LAST_REQUESTED_AT else None,
        "rcl_refresh_last_age_seconds": _REFRESH_LAST_AGE_SECONDS,
        "rcl_refresh_last_source": _REFRESH_LAST_SOURCE,
        "rcl_refresh_last_entity_ids": list(_REFRESH_LAST_ENTITY_IDS),
        "rcl_refresh_last_error": _REFRESH_LAST_ERROR,
        "rcl_refresh_throttle_seconds": RCL_REFRESH_THROTTLE_SECONDS,
    }


def _request_rcl_refresh(hass, age: int | None, source: str | None) -> dict[str, Any]:
    global _REFRESH_LAST_REQUESTED_AT, _REFRESH_LAST_AGE_SECONDS, _REFRESH_LAST_SOURCE, _REFRESH_LAST_ENTITY_IDS, _REFRESH_LAST_ERROR

    now = datetime.now(UTC)
    if _REFRESH_LAST_REQUESTED_AT is not None and now - _REFRESH_LAST_REQUESTED_AT < timedelta(seconds=RCL_REFRESH_THROTTLE_SECONDS):
        return _refresh_state_attrs(False)

    entity_ids = _known_refresh_entity_ids(hass)
    _REFRESH_LAST_REQUESTED_AT = now
    _REFRESH_LAST_AGE_SECONDS = int(age) if age is not None else None
    _REFRESH_LAST_SOURCE = source
    _REFRESH_LAST_ENTITY_IDS = entity_ids

    if not entity_ids:
        _REFRESH_LAST_ERROR = "no_known_rcl_entities"
        return _refresh_state_attrs(False)

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
        _REFRESH_LAST_ERROR = f"{type(exc).__name__}: {exc}"
        return _refresh_state_attrs(False)

    _REFRESH_LAST_ERROR = None
    return _refresh_state_attrs(True)


def _staleness_source(snapshot: dict[str, Any]) -> tuple[str | None, int | None]:
    candidates = [
        ("rapt_brewzilla_temperature_age_seconds", snapshot.get("rapt_brewzilla_temperature_age_seconds")),
        ("brewzilla_rapt_control_age_seconds", snapshot.get("brewzilla_rapt_control_age_seconds")),
        ("rapt_brewzilla_poll_age_seconds", snapshot.get("rapt_brewzilla_poll_age_seconds")),
    ]
    for source, age in candidates:
        num = _as_number(age)
        if num is not None:
            return source, int(num)
    return None, None


def _apply_freshness_guard(hass, snapshot: dict[str, Any]) -> dict[str, Any]:
    guarded = dict(snapshot)
    source, age = _staleness_source(guarded)
    active_context = _active_control_context(guarded)
    safe_mode_enabled = _safe_mode_enabled(hass)
    warning = bool(active_context and age is not None and age > RAPT_ACTIVE_CONTROL_WARN_AGE_SECONDS)
    blocking = bool(active_context and safe_mode_enabled and age is not None and age > RAPT_ACTIVE_CONTROL_BLOCK_AGE_SECONDS)
    diagnostic_bypass = bool(warning and not safe_mode_enabled)
    reason = None
    if blocking:
        reason = f"BrewZilla/RCL temperature data stale ({int(age)}s); refresh requested and control blocked."
    elif warning and diagnostic_bypass:
        reason = f"BrewZilla/RCL temperature data stale ({int(age)}s); refresh requested, Safe Mode off so diagnostic Direct action may continue."
    elif warning:
        reason = f"BrewZilla/RCL temperature data getting stale ({int(age)}s); refresh requested."

    refresh_attrs = _request_rcl_refresh(hass, age, source) if warning or blocking else _refresh_state_attrs(False)

    guarded.update(
        {
            "rcl_freshness_guard_active": warning,
            "rcl_freshness_guard_blocking": blocking,
            "rcl_freshness_guard_reason": reason,
            "rcl_freshness_age_seconds": int(age) if age is not None else None,
            "rcl_freshness_source": source,
            "rcl_freshness_warn_age_seconds": RAPT_ACTIVE_CONTROL_WARN_AGE_SECONDS,
            "rcl_freshness_block_age_seconds": RAPT_ACTIVE_CONTROL_BLOCK_AGE_SECONDS,
            "rcl_freshness_safe_mode_enabled": safe_mode_enabled,
            "rcl_freshness_diagnostic_bypass_active": diagnostic_bypass,
            **refresh_attrs,
        }
    )

    if not blocking:
        if warning:
            guarded["rapt_critical_refresh_recommended"] = True
        return guarded

    heater_on = bool(guarded.get("heater_on"))
    pump_on = bool(guarded.get("pump_on"))
    desired_heat = 0.0
    desired_pump = 0.0
    heat_utilization_action_needed = _utilization_action_needed(guarded.get("heat_utilization"), desired_heat)
    pump_utilization_action_needed = _utilization_action_needed(guarded.get("pump_utilization"), desired_pump)
    safe_action_needed = bool(heater_on or pump_on or heat_utilization_action_needed or pump_utilization_action_needed)
    connected = bool(guarded.get("connected"))

    guarded.update(
        {
            "target_sync_needed": False,
            "heating_needed": False,
            "pump_recommended": False,
            "desired_heat_utilization": desired_heat,
            "desired_pump_utilization": desired_pump,
            "desired_heater_on": False,
            "desired_pump_on": False,
            "heater_action_needed": False,
            "pump_action_needed": False,
            "heater_stop_needed": heater_on,
            "pump_stop_needed": pump_on,
            "heat_utilization_action_needed": heat_utilization_action_needed,
            "pump_utilization_action_needed": pump_utilization_action_needed,
            "ba_owned_reassert_action_needed": False,
            "rapt_critical_refresh_recommended": True,
            "can_apply_target": connected and safe_action_needed,
            "orchestration_mode": "direct-control" if connected and safe_action_needed else "blocked",
            "control_reason": reason,
        }
    )
    return guarded


def build_orchestration_snapshot(hass) -> dict[str, Any]:
    assert _BASE_BUILD_ORCHESTRATION_SNAPSHOT is not None
    return _apply_freshness_guard(hass, _BASE_BUILD_ORCHESTRATION_SNAPSHOT(hass))


def install_freshness_guard() -> None:
    global _BASE_BUILD_ORCHESTRATION_SNAPSHOT, _INSTALLED
    if _INSTALLED:
        return
    _BASE_BUILD_ORCHESTRATION_SNAPSHOT = _base.build_orchestration_snapshot
    _base.build_orchestration_snapshot = build_orchestration_snapshot
    _INSTALLED = True
