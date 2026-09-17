"""Pure, read-only SG control decisions for fermentation tracking.

No Home Assistant imports, actuator calls, or Brewfather-side interpretation.
The caller must persist stage/pending state and explicitly opt in per batch.
Cold-crash readiness is advice ONLY, never a command to start cooling.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import isfinite
from typing import Any, Iterable

STAGE_TEMPERATURES_C = (18.0, 19.0, 20.5)
STAGE_THRESHOLDS_SG = (1.035, 1.020)
MAX_SAMPLE_AGE = timedelta(minutes=20)
CONFIRM_INTERVAL = timedelta(minutes=5)
MAX_CONFIRM_WINDOW = timedelta(hours=2)
DEFAULT_STABLE_HOURS = 72.0
DEFAULT_FG = 1.014
DEFAULT_FG_TOLERANCE = 0.002
DEFAULT_STABILITY_TOLERANCE = 0.001
MAX_STABILITY_GAP = timedelta(hours=12)


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _valid_sample(
    sg: float | None,
    observed_at: datetime | None,
    now: datetime,
    *,
    original_gravity: float | None = None,
) -> str | None:
    if sg is None or not isfinite(sg) or not 0.980 <= sg <= 1.150:
        return "implausible_gravity"
    if original_gravity is not None and isfinite(original_gravity) and sg > original_gravity + 0.005:
        return "above_original_gravity"
    if observed_at is None:
        return "missing_sample_time"
    age = now - _utc(observed_at)
    if age < -timedelta(minutes=1):
        return "future_sample"
    if age > MAX_SAMPLE_AGE:
        return "stale_gravity"
    return None


def evaluate_stage(
    *,
    stage: int,
    pending_stage: int | None,
    pending_since: datetime | None,
    last_observed_at: datetime | None,
    sg: float | None,
    observed_at: datetime | None,
    now: datetime,
    original_gravity: float | None = None,
) -> dict[str, Any]:
    """Evaluate one new Pill observation; never lower or skip the latched stage.

    A threshold requires two *distinct* observations at least five minutes apart.
    Duplicate coordinator polls must not count as a second reading. Bad or stale
    observations leave the last confirmed temperature unchanged.
    """
    now = _utc(now)
    stage = max(0, min(int(stage), len(STAGE_TEMPERATURES_C) - 1))
    result: dict[str, Any] = {
        "stage": stage,
        "temperature_c": STAGE_TEMPERATURES_C[stage],
        "pending_stage": pending_stage,
        "pending_since": pending_since,
        "last_observed_at": last_observed_at,
        "accepted": False,
        "advanced": False,
        "reason": "awaiting_pill",
    }
    invalid = _valid_sample(sg, observed_at, now, original_gravity=original_gravity)
    if invalid is not None:
        result["reason"] = invalid
        return result
    assert observed_at is not None and sg is not None
    observed_at = _utc(observed_at)
    if last_observed_at is not None and observed_at <= _utc(last_observed_at):
        result["reason"] = "duplicate_observation"
        return result
    result["accepted"] = True
    result["last_observed_at"] = observed_at
    if stage >= len(STAGE_THRESHOLDS_SG):
        result.update(pending_stage=None, pending_since=None, reason="final_temperature_held")
        return result

    next_stage = stage + 1
    if sg > STAGE_THRESHOLDS_SG[stage]:
        result.update(pending_stage=None, pending_since=None, reason="threshold_not_reached")
        return result
    if pending_stage != next_stage or pending_since is None:
        result.update(pending_stage=next_stage, pending_since=observed_at, reason="awaiting_confirmation")
        return result
    elapsed = observed_at - _utc(pending_since)
    if elapsed > MAX_CONFIRM_WINDOW:
        result.update(pending_stage=next_stage, pending_since=observed_at, reason="confirmation_window_restarted")
    elif elapsed >= CONFIRM_INTERVAL:
        result.update(
            stage=next_stage,
            temperature_c=STAGE_TEMPERATURES_C[next_stage],
            pending_stage=None,
            pending_since=None,
            advanced=True,
            reason="threshold_confirmed",
        )
    else:
        result["reason"] = "awaiting_confirmation"
    return result


def evaluate_cold_crash_readiness(
    observations: Iterable[tuple[datetime, float]],
    *,
    now: datetime,
    target_fg: float | None,
    stable_hours: float = DEFAULT_STABLE_HOURS,
    fg_tolerance: float = DEFAULT_FG_TOLERANCE,
    stability_tolerance: float = DEFAULT_STABILITY_TOLERANCE,
) -> dict[str, Any]:
    """Require a continuous, fresh Pill series near FG before recommending crash.

    A few distant points or a single current reading cannot prove stable FG.
    This function never authorizes cooling; physical suck-back protection and
    operator confirmation remain separate requirements.
    """
    now = _utc(now)
    result: dict[str, Any] = {
        "ready": False,
        "reason": "insufficient_history",
        "sample_count": 0,
        "span_hours": 0.0,
        "range_sg": None,
    }
    if target_fg is None or not isfinite(target_fg) or not 0.980 <= target_fg <= 1.150:
        result["reason"] = "missing_expected_fg"
        return result
    if not 48.0 <= stable_hours <= 72.0:
        result["reason"] = "invalid_stability_window"
        return result

    valid = sorted(
        (
            (_utc(at), sg)
            for at, sg in observations
            if isinstance(at, datetime) and isfinite(sg) and 0.980 <= sg <= 1.150
            and _utc(at) <= now + timedelta(minutes=1)
        ),
        key=lambda item: item[0],
    )
    if not valid:
        return result
    if now - valid[-1][0] > MAX_SAMPLE_AGE:
        result["reason"] = "stale_gravity"
        return result

    cutoff = now - timedelta(hours=stable_hours)
    window = [item for item in valid if item[0] >= cutoff]
    before = [item for item in valid if item[0] < cutoff]
    if before:
        window.insert(0, before[-1])
    result["sample_count"] = len(window)
    if len(window) < 6:
        return result
    span_hours = (window[-1][0] - window[0][0]).total_seconds() / 3600.0
    result["span_hours"] = round(span_hours, 2)
    if span_hours < stable_hours:
        result["reason"] = "insufficient_time_span"
        return result
    if any(b[0] - a[0] > MAX_STABILITY_GAP for a, b in zip(window, window[1:])):
        result["reason"] = "gaps_in_pill_history"
        return result

    values = [sg for _, sg in window]
    sg_range = max(values) - min(values)
    result["range_sg"] = round(sg_range, 4)
    if sg_range > stability_tolerance:
        result["reason"] = "gravity_still_changing"
    elif values[-1] > target_fg + fg_tolerance:
        result["reason"] = "not_near_expected_fg"
    else:
        result.update(ready=True, reason="stable_near_fg_waiting_for_operator")
    return result
