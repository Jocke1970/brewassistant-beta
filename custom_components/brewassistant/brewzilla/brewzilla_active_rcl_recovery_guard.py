"""Active hot-side RCL recovery watchdog for BrewZilla.

This guard is deliberately recovery/diagnostics only.  It may request
``homeassistant.update_entity`` and throttled ``homeassistant.reload_config_entry``
when RAPT Cloud Link/BrewZilla telemetry is stale or disconnected during an active
hot-side session, but it must not change target, heat, pump, heater or pump state.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant

from . import brewzilla_orchestration as base

_INSTALLED = False
_ORIGINAL_BUILD: Callable[[HomeAssistant], dict[str, Any]] | None = None

_DATA_KEY = "brewzilla_active_hot_side_rcl_recovery"
_UPDATE_MIN_INTERVAL_SECONDS = 30
_RELOAD_MIN_INTERVAL_SECONDS = 180
_ACTIVE_STATES = {"live", "running", "paused", "prepared", "awaiting_snapshot", "awaiting_confirm"}
_HOT_SIDE_WORDS = (
    "mash",
    "mäsk",
    "ramp",
    "heat",
    "värm",
    "strike",
    "boil",
    "kok",
    "sparge",
    "lak",
    "whirlpool",
    "hop stand",
    "hopstand",
)
_BAD_STATES = {"unknown", "unavailable", "none", ""}


def _now() -> datetime:
    return datetime.now(UTC)


def _store(hass: HomeAssistant) -> dict[str, Any]:
    return hass.data.setdefault("brewassistant", {}).setdefault(
        _DATA_KEY,
        {
            "last_update_at": None,
            "last_reload_at": None,
            "last_error": None,
            "last_reason": None,
            "last_entity_ids": [],
        },
    )


def _is_recent(value: Any, *, seconds: int) -> bool:
    if not isinstance(value, datetime):
        return False
    return _now() - value < timedelta(seconds=seconds)


def _runtime_state(snapshot: dict[str, Any]) -> str:
    return str(snapshot.get("brewday_state") or snapshot.get("runtime_state") or "idle").strip().lower()


def _hot_side_context(snapshot: dict[str, Any]) -> bool:
    state = _runtime_state(snapshot)
    if state not in _ACTIVE_STATES:
        return False
    if snapshot.get("abort_lockout_active") or snapshot.get("completed_runtime"):
        return False
    if snapshot.get("boil_stage"):
        return True

    text = " ".join(
        str(snapshot.get(key) or "")
        for key in ("runtime_stage", "runtime_step", "runtime_raw_step_name")
    ).lower()
    if any(word in text for word in _HOT_SIDE_WORDS):
        return True

    # A valid target during an active Brewday runtime is still hot-side relevant.
    return snapshot.get("requested_target") is not None or snapshot.get("applied_target") is not None


def _known_entity_ids(hass: HomeAssistant) -> list[str]:
    return [entity_id for entity_id in base.RAPT_BREWZILLA_ENTITY_IDS if hass.states.get(entity_id) is not None]


def _connection_lost(snapshot: dict[str, Any]) -> bool:
    if snapshot.get("connected") is False:
        return True
    connection = str(snapshot.get("connection_state") or "").strip().lower()
    return connection in _BAD_STATES or (connection and connection != "connected")


def _stale_reason(snapshot: dict[str, Any]) -> str | None:
    if _connection_lost(snapshot):
        return "brewzilla_connection_lost_during_active_brew"

    control_age = snapshot.get("brewzilla_rapt_control_age_seconds")
    dynamic_age = snapshot.get("rapt_brewzilla_dynamic_age_seconds")
    temp_age = snapshot.get("rapt_brewzilla_temperature_age_seconds")
    target_age = snapshot.get("rapt_brewzilla_target_age_seconds")
    heat_age = snapshot.get("rapt_brewzilla_heat_util_age_seconds")
    pump_age = snapshot.get("rapt_brewzilla_pump_util_age_seconds")

    warn = base.RAPT_OBSERVATION_WARN_AGE_SECONDS
    candidates = {
        "control": control_age,
        "dynamic": dynamic_age,
        "temperature": temp_age,
        "target": target_age,
        "heat_utilization": heat_age,
        "pump_utilization": pump_age,
    }
    stale = {name: age for name, age in candidates.items() if isinstance(age, (int, float)) and age > warn}
    if stale:
        oldest_name, oldest_age = max(stale.items(), key=lambda item: float(item[1]))
        return f"brewzilla_{oldest_name}_stale_{int(float(oldest_age))}s"

    if snapshot.get("rapt_brewzilla_poll_warning") or snapshot.get("rapt_critical_refresh_recommended"):
        return "brewzilla_rapt_refresh_recommended"

    return None


def _request_recovery(hass: HomeAssistant, *, reason: str) -> dict[str, Any]:
    store = _store(hass)
    entity_ids = _known_entity_ids(hass)
    update_requested = False
    reload_requested = False
    error = None

    update_recent = _is_recent(store.get("last_update_at"), seconds=_UPDATE_MIN_INTERVAL_SECONDS)
    reload_recent = _is_recent(store.get("last_reload_at"), seconds=_RELOAD_MIN_INTERVAL_SECONDS)
    reload_available = hass.services.has_service("homeassistant", "reload_config_entry")

    if entity_ids and not update_recent:
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
            store["last_update_at"] = _now()
        except Exception as exc:  # pragma: no cover - defensive HA runtime guard
            error = f"update_entity:{type(exc).__name__}: {exc}"

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
            store["last_reload_at"] = _now()
        except Exception as exc:  # pragma: no cover - defensive HA runtime guard
            error = f"reload_config_entry:{type(exc).__name__}: {exc}"

    store["last_error"] = error
    store["last_reason"] = reason
    store["last_entity_ids"] = entity_ids

    last_update_at = store.get("last_update_at")
    last_reload_at = store.get("last_reload_at")
    return {
        "rcl_active_hot_side_recovery_active": True,
        "rcl_active_hot_side_recovery_reason": reason,
        "rcl_active_hot_side_recovery_update_requested": update_requested,
        "rcl_active_hot_side_recovery_reload_requested": reload_requested,
        "rcl_active_hot_side_recovery_update_recently_requested": update_recent,
        "rcl_active_hot_side_recovery_reload_recently_requested": reload_recent,
        "rcl_active_hot_side_recovery_reload_available": reload_available,
        "rcl_active_hot_side_recovery_update_interval_seconds": _UPDATE_MIN_INTERVAL_SECONDS,
        "rcl_active_hot_side_recovery_reload_interval_seconds": _RELOAD_MIN_INTERVAL_SECONDS,
        "rcl_active_hot_side_recovery_last_update_at": last_update_at.isoformat() if isinstance(last_update_at, datetime) else None,
        "rcl_active_hot_side_recovery_last_reload_at": last_reload_at.isoformat() if isinstance(last_reload_at, datetime) else None,
        "rcl_active_hot_side_recovery_entity_ids": entity_ids,
        "rcl_active_hot_side_recovery_error": error,
    }


def _augment_snapshot(hass: HomeAssistant, snapshot: dict[str, Any]) -> dict[str, Any]:
    if not _hot_side_context(snapshot):
        return {
            **snapshot,
            "rcl_active_hot_side_recovery_active": False,
            "rcl_active_hot_side_recovery_reason": None,
        }

    reason = _stale_reason(snapshot)
    if reason is None:
        return {
            **snapshot,
            "rcl_active_hot_side_recovery_active": False,
            "rcl_active_hot_side_recovery_reason": None,
        }

    recovery = _request_recovery(hass, reason=reason)
    local_target = snapshot.get("applied_target") or snapshot.get("requested_target")
    control_reason = str(snapshot.get("control_reason") or "").strip()
    recovery_reason = (
        f"Active hot-side RCL recovery: {reason}; update_entity requested when throttling allows, "
        "reload_config_entry attempted when available/throttled; BrewZilla local target is preserved."
    )
    return {
        **snapshot,
        **recovery,
        "rapt_critical_refresh_recommended": True,
        "rcl_active_hot_side_recovery_local_regulation_preserved": local_target is not None,
        "rcl_active_hot_side_recovery_preserved_target": local_target,
        "control_reason": f"{control_reason} {recovery_reason}".strip(),
    }


def install_active_rcl_recovery_guard() -> None:
    """Install active hot-side RCL recovery diagnostics around orchestration snapshots."""
    global _INSTALLED, _ORIGINAL_BUILD
    if _INSTALLED:
        return

    _ORIGINAL_BUILD = base.build_orchestration_snapshot

    def build_orchestration_snapshot(hass: HomeAssistant) -> dict[str, Any]:
        assert _ORIGINAL_BUILD is not None
        return _augment_snapshot(hass, _ORIGINAL_BUILD(hass))

    base.build_orchestration_snapshot = build_orchestration_snapshot
    _INSTALLED = True
