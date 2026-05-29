"""Brewfather Brew Tracker refresh policy for BrewAssistant.

This module keeps Brew Tracker polling gentle during real brew days while still
being responsive around step changes and short low-temperature test batches.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .brewday_runtime_core import build_core_snapshot

SOURCE_NAME = "Brewfather Brew Tracker"
STORE_KEY = "brewassistant_brewday_refresh"

NORMAL_DEFAULT_INTERVAL = 5 * 60
NORMAL_CHILLING_INTERVAL = 2 * 60
NORMAL_IDLE_INTERVAL = 10 * 60
TEST_DEFAULT_INTERVAL = 30
ENDING_SOON_INTERVAL = 15
AWAITING_SNAPSHOT_INTERVAL = 15
MIN_REFRESH_INTERVAL = 10
ENDING_SOON_SECONDS = 60
AWAITING_BURST_MAX = 5
AWAITING_BURST_WINDOW_SECONDS = 5 * 60
TEST_STEP_DURATION_LIMIT_SECONDS = 5 * 60

STAGE_GROUP_MASH = "mash"
STAGE_GROUP_BOIL = "boil"
STAGE_GROUP_CHILL = "chilling"
STAGE_GROUP_IDLE = "idle"
STAGE_GROUP_OTHER = "other"

MASH_WORDS = ("mash", "mäsk", "rest", "saccharification", "beta", "alpha", "protein")
BOIL_WORDS = ("boil", "kok")
CHILL_WORDS = ("chill", "cool", "kyl", "cooling", "nedkyl")
SETUP_WORDS = ("setup", "prepare", "förbered")
TRANSFER_WORDS = ("transfer", "tapp", "rack")
CLEAN_WORDS = ("clean", "cleanup", "rengör")


def _store(hass: HomeAssistant) -> dict[str, Any]:
    """Return integration-local refresh state storage."""
    return hass.data.setdefault(STORE_KEY, {})


def _now() -> float:
    return dt_util.utcnow().timestamp()


def _stage_group(stage: str | None, step: str | None) -> str:
    text = f"{stage or ''} {step or ''}".lower()
    if any(word in text for word in MASH_WORDS):
        return STAGE_GROUP_MASH
    if any(word in text for word in BOIL_WORDS):
        return STAGE_GROUP_BOIL
    if any(word in text for word in CHILL_WORDS):
        return STAGE_GROUP_CHILL
    if any(word in text for word in SETUP_WORDS + TRANSFER_WORDS + CLEAN_WORDS):
        return STAGE_GROUP_IDLE
    return STAGE_GROUP_OTHER


def _is_test_profile(snapshot: dict[str, Any]) -> bool:
    """Detect short-step dry-run/test recipes without requiring extra helpers."""
    duration = snapshot.get("stage_duration_seconds")
    try:
        duration_f = float(duration) if duration is not None else 0.0
    except (TypeError, ValueError):
        duration_f = 0.0

    summary = str(snapshot.get("summary") or "").lower()
    stage = str(snapshot.get("stage") or "").lower()
    step = str(snapshot.get("step") or "").lower()
    text = f"{summary} {stage} {step}"

    return (
        0 < duration_f <= TEST_STEP_DURATION_LIMIT_SECONDS
        or "test" in text
        or "policy" in text
        or "tracker sync" in text
    )


def _base_interval(snapshot: dict[str, Any], group: str, test_profile: bool) -> int:
    if test_profile:
        return TEST_DEFAULT_INTERVAL
    if group == STAGE_GROUP_CHILL:
        return NORMAL_CHILLING_INTERVAL
    if group in {STAGE_GROUP_MASH, STAGE_GROUP_BOIL, STAGE_GROUP_OTHER}:
        return NORMAL_DEFAULT_INTERVAL
    return NORMAL_IDLE_INTERVAL


def build_refresh_policy_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    """Build refresh decision diagnostics without performing a refresh."""
    snapshot = build_core_snapshot(hass)
    store = _store(hass)
    now = _now()

    source = snapshot.get("source")
    status = str(snapshot.get("status") or "")
    runtime_state = str(snapshot.get("runtime_state") or "")
    active = source == SOURCE_NAME and status in {"running", "paused"} and runtime_state in {
        "live",
        "running",
        "paused",
        "awaiting_snapshot",
    }

    group = _stage_group(str(snapshot.get("stage") or ""), str(snapshot.get("step") or ""))
    test_profile = _is_test_profile(snapshot)
    remaining = int(snapshot.get("time_remaining_seconds") or 0)
    awaiting = bool(snapshot.get("awaiting_snapshot")) or runtime_state == "awaiting_snapshot"
    ending_soon = active and 0 <= remaining <= ENDING_SOON_SECONDS

    interval = _base_interval(snapshot, group, test_profile)
    reason = "inactive"
    if active:
        reason = "normal"
        if ending_soon:
            interval = ENDING_SOON_INTERVAL
            reason = "ending_soon"
        if awaiting:
            interval = AWAITING_SNAPSHOT_INTERVAL
            reason = "awaiting_snapshot"

    last_refresh_ts = store.get("last_refresh_ts")
    elapsed = None if last_refresh_ts is None else now - float(last_refresh_ts)
    due = active and (elapsed is None or elapsed >= interval)

    burst_count = int(store.get("awaiting_burst_count") or 0)
    burst_window_start = store.get("awaiting_burst_window_start")
    if not awaiting:
        burst_count = 0
    elif burst_window_start is not None and now - float(burst_window_start) > AWAITING_BURST_WINDOW_SECONDS:
        burst_count = 0

    if awaiting and burst_count >= AWAITING_BURST_MAX:
        due = False
        reason = "awaiting_snapshot_burst_limit"

    if elapsed is not None and elapsed < MIN_REFRESH_INTERVAL:
        due = False
        reason = "min_cooldown"

    return {
        "source": "brewday_refresh_policy",
        "active": active,
        "brewtracker_source": source,
        "status": status,
        "runtime_state": runtime_state,
        "stage": snapshot.get("stage"),
        "step": snapshot.get("step"),
        "stage_group": group,
        "test_profile": test_profile,
        "remaining_seconds": remaining,
        "awaiting_snapshot": awaiting,
        "ending_soon": ending_soon,
        "interval_seconds": interval,
        "due": due,
        "reason": reason,
        "last_refresh_ts": last_refresh_ts,
        "seconds_since_last_refresh": round(elapsed, 1) if elapsed is not None else None,
        "awaiting_burst_count": burst_count,
        "awaiting_burst_max": AWAITING_BURST_MAX,
    }


def mark_refresh_performed(hass: HomeAssistant, *, reason: str) -> None:
    """Record that BrewAssistant requested a Brewfather refresh."""
    store = _store(hass)
    now = _now()
    store["last_refresh_ts"] = now
    store["last_refresh_reason"] = reason

    if reason.startswith("awaiting_snapshot"):
        window_start = store.get("awaiting_burst_window_start")
        if window_start is None or now - float(window_start) > AWAITING_BURST_WINDOW_SECONDS:
            store["awaiting_burst_window_start"] = now
            store["awaiting_burst_count"] = 0
        store["awaiting_burst_count"] = int(store.get("awaiting_burst_count") or 0) + 1
    else:
        store["awaiting_burst_count"] = 0
        store["awaiting_burst_window_start"] = None


def mark_refresh_skipped(hass: HomeAssistant, *, reason: str) -> None:
    """Record the most recent skipped refresh reason for diagnostics."""
    store = _store(hass)
    store["last_skip_reason"] = reason
    store["last_skip_ts"] = _now()
