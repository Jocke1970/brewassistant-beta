"""Active hot-side RCL recovery watchdog for BrewZilla.

This guard is deliberately recovery/diagnostics only. It may request
``homeassistant.update_entity`` for soft telemetry staleness and a much more
conservative throttled ``homeassistant.reload_config_entry`` only when RAPT Cloud
Link/BrewZilla looks hard-disconnected or extremely stale during an active
hot-side session.

It must not change target, heat, pump, heater or pump state.
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
_UPDATE_MIN_INTERVAL_SECONDS = 60
_RELOAD_MIN_INTERVAL_SECONDS = 900
_HARD_RELOAD_STALE_MULTIPLIER = 3
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


def _telemetry_age_candidates(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "control": snapshot.get("brewzilla_rapt_control_age_seconds"),
        "dynamic": snapshot.get("rapt_brewzilla_dynamic_age_seconds"),
        "temperature": snapshot.get("rapt_brewzilla_temperature_age_seconds"),
        "target": snapshot.get("rapt_brewzilla_target_age_seconds"),
        "heat_utilization": snapshot.get("rapt_brewzilla_heat_util_age_seconds"),
        "pump_utilization": snapshot.get("rapt_brewzilla_pump_util_age_seconds"),
    }


def _aged_entries(candidates: dict[str, Any], *, older_than_seconds: int) -> dict[str, float]:
    return {
        name: float(age)
        for name, age in candidates.items()
        if isinstance(age, (int, float)) and float(age) > older_than_seconds
    }


def _recovery_need(snapshot: dict[str, Any]) -> tuple[str | None, bool]:
    """Return (reason, allow_reload).

    Soft stale telemetry should only request ``update_entity``.  Reloading the
    RCL config entry is disruptive because entities briefly disconnect, so it is
    reserved for hard connection loss or very stale telemetry.
    """

    if _connection_lost(snapshot):
        return "brewzilla_connection_lost_during_active_brew", True

    warn = base.RAPT_OBSERVATION_WARN_AGE_SECONDS
    hard = warn * _HARD_RELOAD_STALE_MULTIPLIER
    candidates = _telemetry_age_candidates(snapshot)

    hard_stale = _aged_entries(candidates, older_than_seconds=hard)
    if hard_stale:
        oldest_name, oldest_age = max(hard_stale.items(), key=lambda item: item[1])
        return f"brewzilla_{oldest_name}_hard_stale_{int(oldest_age)}s", True

    soft_stale = _aged_entries(candidates, older_than_seconds=warn)
    if soft_stale:
        oldest_name, oldest_age = max(soft_stale.items(), key=lambda item: item[1])
        return f"brewzilla_{oldest_name}_soft_stale_{int(oldest_age)}s", False

    # Intentionally do not use rapt_critical_refresh_recommended as a recovery
    # trigger.  That flag can be true for normal hot-side control reasons such as
    # an action being needed, target sync, or a step ending soon.  Treating it as
    # an RCL failure caused needless reloads while telemetry was still flowing.
    return None, False


def _request_recovery(hass: HomeAssistant, *, reason: str, allow_reload: bool) -> dict[str, Any]:
    store = _store(hass)
    entity_ids = _known_entity_ids(hass)
    update_requested = False
    reload_requested = False
    error = None

    update_recent = _is_recent(store.get("last_update_at"), seconds=_UPDATE_MIN_INTERVAL_SECONDS)
    reload_recent = _is_recent(store.get("last_reload_at"), seconds=_RELOAD_MIN_INTERVAL_SECONDS)
    reload_available = hass.services.has_service("homeassistant", "reload_config_entry")
    reload_suppressed_reason = None

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

    if not allow_reload:
        reload_suppressed_reason = "soft_stale_update_only"
    elif not reload_available:
        reload_suppressed_reason = "reload_config_entry_unavailable"
    elif reload_recent:
        reload_suppressed_reason = "reload_recently_requested"
    elif entity_ids:
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
        "rcl_active_hot_side_recovery_reload_allowed": allow_reload,
        "rcl_active_hot_side_recovery_reload_suppressed_reason": reload_suppressed_reason,
        "rcl_active_hot_side_recovery_update_recently_requested": update_recent,
        "rcl_active_hot_side_recovery_reload_recently_requested": reload_recent,
        "rcl_active_hot_side_recovery_reload_available": reload_available,
        "rcl_active_hot_side_recovery_update_interval_seconds": _UPDATE_MIN_INTERVAL_SECONDS,
        "rcl_active_hot_side_recovery_reload_interval_seconds": _RELOAD_MIN_INTERVAL_SECONDS,
        "rcl_active_hot_side_recovery_hard_stale_seconds": base.RAPT_OBSERVATION_WARN_AGE_SECONDS * _HARD_RELOAD_STALE_MULTIPLIER,
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

    reason, allow_reload = _recovery_need(snapshot)
    if reason is None:
        return {
            **snapshot,
            "rcl_active_hot_side_recovery_active": False,
            "rcl_active_hot_side_recovery_reason": None,
        }

    recovery = _request_recovery(hass, reason=reason, allow_reload=allow_reload)
    local_target = snapshot.get("applied_target") or snapshot.get("requested_target")
    control_reason = str(snapshot.get("control_reason") or "").strip()
    reload_note = (
        "reload_config_entry allowed for hard RCL failure"
        if allow_reload
        else "reload_config_entry suppressed because telemetry is only soft-stale"
    )
    recovery_reason = (
        f"Active hot-side RCL recovery: {reason}; update_entity requested when throttling allows; "
        f"{reload_note}; BrewZilla local target is preserved."
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
