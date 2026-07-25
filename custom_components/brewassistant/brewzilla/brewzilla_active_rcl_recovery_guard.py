"""Active hot-side RCL recovery watchdog for BrewZilla.

This guard is deliberately recovery/diagnostics only. It may request
``homeassistant.update_entity`` when RAPT Cloud Link/BrewZilla telemetry looks
stale during an active hot-side session.  A heavier
``homeassistant.reload_config_entry`` is only attempted for a hard disconnect or
when live telemetry is no longer flowing; reloading RCL while it is still
publishing temperatures can itself create the disconnect we are trying to avoid.

The guard must not change target, heat, pump, heater or pump state.
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
_RELOAD_MIN_INTERVAL_SECONDS = 600
_LIVE_TELEMETRY_HARD_STALE_MULTIPLIER = 2
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


def _age(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


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


def _live_telemetry_ages(snapshot: dict[str, Any]) -> dict[str, float | None]:
    return {
        "temperature": _age(snapshot.get("rapt_brewzilla_temperature_age_seconds")),
        "power": _age(snapshot.get("rapt_brewzilla_power_age_seconds")),
    }


def _live_telemetry_fresh(snapshot: dict[str, Any]) -> bool:
    if _connection_lost(snapshot):
        return False
    warn = float(base.RAPT_OBSERVATION_WARN_AGE_SECONDS)
    ages = _live_telemetry_ages(snapshot)
    return any(age is not None and age <= warn for age in ages.values())


def _live_telemetry_stale(snapshot: dict[str, Any], *, hard: bool = False) -> tuple[bool, float | None]:
    """Return true when live BrewZilla telemetry itself is stale.

    Target/heat/pump number entities may legitimately have old ``last_updated``
    values because their values do not change while BrewZilla is regulating
    locally.  Do not treat those unchanged config values as proof that RCL is
    dead if temperature or power telemetry is still fresh.
    """

    threshold = float(base.RAPT_OBSERVATION_WARN_AGE_SECONDS)
    if hard:
        threshold *= _LIVE_TELEMETRY_HARD_STALE_MULTIPLIER

    ages = {name: age for name, age in _live_telemetry_ages(snapshot).items() if age is not None}
    if not ages:
        return False, None
    if any(age <= threshold for age in ages.values()):
        return False, max(ages.values())
    return True, max(ages.values())


def _stale_reason(snapshot: dict[str, Any]) -> str | None:
    if _connection_lost(snapshot):
        return "brewzilla_connection_lost_during_active_brew"

    # If live temperature/power telemetry is flowing, RCL is not considered dead.
    # Old target/heat/pump last_updated values alone are expected during a stable
    # hold and must not trigger reload churn.
    if _live_telemetry_fresh(snapshot):
        return None

    live_stale, live_age = _live_telemetry_stale(snapshot)
    if live_stale and live_age is not None:
        return f"brewzilla_live_telemetry_stale_{int(live_age)}s"

    if snapshot.get("rapt_brewzilla_poll_warning") or snapshot.get("rapt_critical_refresh_recommended"):
        return "brewzilla_rapt_refresh_recommended"

    return None


def _reload_allowed(reason: str, snapshot: dict[str, Any]) -> tuple[bool, str | None]:
    if _connection_lost(snapshot):
        return True, None

    hard_stale, hard_age = _live_telemetry_stale(snapshot, hard=True)
    if hard_stale:
        return True, f"live_telemetry_hard_stale_{int(hard_age or 0)}s"

    if _live_telemetry_fresh(snapshot):
        return False, "live_telemetry_fresh"

    return False, "refresh_only_until_disconnect_or_hard_stale"


def _request_recovery(
    hass: HomeAssistant,
    *,
    reason: str,
    allow_reload: bool,
    reload_suppressed_reason: str | None,
) -> dict[str, Any]:
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

    if entity_ids and reload_available and allow_reload and not reload_recent:
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
        "rcl_active_hot_side_recovery_reload_allowed": allow_reload,
        "rcl_active_hot_side_recovery_reload_suppressed_reason": reload_suppressed_reason,
        "rcl_active_hot_side_recovery_live_telemetry_fresh": False,
        "rcl_active_hot_side_recovery_live_telemetry_ages": {},
        "rcl_active_hot_side_recovery_update_interval_seconds": _UPDATE_MIN_INTERVAL_SECONDS,
        "rcl_active_hot_side_recovery_reload_interval_seconds": _RELOAD_MIN_INTERVAL_SECONDS,
        "rcl_active_hot_side_recovery_last_update_at": last_update_at.isoformat() if isinstance(last_update_at, datetime) else None,
        "rcl_active_hot_side_recovery_last_reload_at": last_reload_at.isoformat() if isinstance(last_reload_at, datetime) else None,
        "rcl_active_hot_side_recovery_entity_ids": entity_ids,
        "rcl_active_hot_side_recovery_error": error,
    }


def _augment_snapshot(hass: HomeAssistant, snapshot: dict[str, Any]) -> dict[str, Any]:
    live_ages = _live_telemetry_ages(snapshot)
    live_fresh = _live_telemetry_fresh(snapshot)

    inactive_fields = {
        "rcl_active_hot_side_recovery_active": False,
        "rcl_active_hot_side_recovery_reason": None,
        "rcl_active_hot_side_recovery_reload_allowed": False,
        "rcl_active_hot_side_recovery_reload_suppressed_reason": None,
        "rcl_active_hot_side_recovery_live_telemetry_fresh": live_fresh,
        "rcl_active_hot_side_recovery_live_telemetry_ages": live_ages,
    }

    if not _hot_side_context(snapshot):
        return {**snapshot, **inactive_fields}

    reason = _stale_reason(snapshot)
    if reason is None:
        return {**snapshot, **inactive_fields}

    allow_reload, reload_suppressed_reason = _reload_allowed(reason, snapshot)
    recovery = _request_recovery(
        hass,
        reason=reason,
        allow_reload=allow_reload,
        reload_suppressed_reason=reload_suppressed_reason,
    )
    local_target = snapshot.get("applied_target") or snapshot.get("requested_target")
    control_reason = str(snapshot.get("control_reason") or "").strip()
    reload_text = (
        "reload_config_entry allowed because RCL is disconnected or live telemetry is hard stale"
        if allow_reload
        else f"reload_config_entry suppressed ({reload_suppressed_reason})"
    )
    recovery_reason = (
        f"Active hot-side RCL recovery: {reason}; update_entity requested when throttling allows; "
        f"{reload_text}; BrewZilla local target is preserved."
    )
    return {
        **snapshot,
        **recovery,
        "rapt_critical_refresh_recommended": True,
        "rcl_active_hot_side_recovery_live_telemetry_fresh": live_fresh,
        "rcl_active_hot_side_recovery_live_telemetry_ages": live_ages,
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
