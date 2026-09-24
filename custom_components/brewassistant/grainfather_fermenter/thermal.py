"""Read-only GF30 thermal preflight helpers.

This module deliberately contains no Home Assistant service calls and no hardware
control.  It can be used before Grainfather Wi-Fi/controller telemetry is
available to compare an automatic beer-temperature observation (for example a
RAPT Pill) with a manually entered reference measurement.

The result is diagnostic/learning input only.  Neither observation is silently
promoted to an actuator-control source.
"""

from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite
from typing import Any

DEFAULT_FRESHNESS_SECONDS = 15 * 60
DEFAULT_AGREEMENT_TOLERANCE_C = 0.5
DEFAULT_PLAUSIBLE_MIN_C = -10.0
DEFAULT_PLAUSIBLE_MAX_C = 50.0


def _as_utc(value: datetime | None) -> datetime | None:
    """Normalize an aware/naive datetime to UTC.

    Naive values are interpreted as UTC because callers must already know the
    provenance of manually entered timestamps.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _valid_temperature(
    value: float | int | None,
    *,
    plausible_min_c: float,
    plausible_max_c: float,
) -> float | None:
    """Return a finite plausible Celsius value, otherwise None."""
    if value is None:
        return None
    try:
        candidate = float(value)
    except (TypeError, ValueError):
        return None
    if not isfinite(candidate):
        return None
    if not plausible_min_c <= candidate <= plausible_max_c:
        return None
    return candidate


def _observation_snapshot(
    *,
    source: str,
    temperature_c: float | int | None,
    observed_at: datetime | None,
    now: datetime,
    freshness_seconds: int,
    plausible_min_c: float,
    plausible_max_c: float,
) -> dict[str, Any]:
    """Normalize one diagnostic temperature observation."""
    normalized_temperature = _valid_temperature(
        temperature_c,
        plausible_min_c=plausible_min_c,
        plausible_max_c=plausible_max_c,
    )
    normalized_time = _as_utc(observed_at)

    age_seconds: float | None = None
    future_timestamp = False
    fresh = False

    if normalized_time is not None:
        age_seconds = (now - normalized_time).total_seconds()
        future_timestamp = age_seconds < -5
        if not future_timestamp:
            age_seconds = max(0.0, age_seconds)

    if normalized_temperature is not None and age_seconds is not None:
        fresh = not future_timestamp and age_seconds <= freshness_seconds

    if normalized_temperature is None:
        state = "invalid_or_missing"
    elif normalized_time is None:
        state = "timestamp_missing"
    elif future_timestamp:
        state = "timestamp_in_future"
    elif fresh:
        state = "fresh"
    else:
        state = "stale"

    return {
        "source": source,
        "temperature_c": normalized_temperature,
        "observed_at": normalized_time.isoformat() if normalized_time else None,
        "age_seconds": round(age_seconds, 1) if age_seconds is not None else None,
        "fresh": fresh,
        "state": state,
    }


def build_manual_preflight_snapshot(
    *,
    pill_temperature_c: float | int | None,
    manual_temperature_c: float | int | None,
    pill_observed_at: datetime | None,
    manual_observed_at: datetime | None,
    now: datetime | None = None,
    freshness_seconds: int = DEFAULT_FRESHNESS_SECONDS,
    agreement_tolerance_c: float = DEFAULT_AGREEMENT_TOLERANCE_C,
    plausible_min_c: float = DEFAULT_PLAUSIBLE_MIN_C,
    plausible_max_c: float = DEFAULT_PLAUSIBLE_MAX_C,
) -> dict[str, Any]:
    """Compare a RAPT Pill observation with a manual reference measurement.

    The comparison is explicitly read-only.  A pair is eligible as one learning
    sample only when both observations are valid and fresh.  A disagreement does
    not choose a winner; it is surfaced for operator review.
    """
    if freshness_seconds <= 0:
        raise ValueError("freshness_seconds must be > 0")
    if agreement_tolerance_c < 0:
        raise ValueError("agreement_tolerance_c must be >= 0")
    if plausible_min_c >= plausible_max_c:
        raise ValueError("plausible_min_c must be lower than plausible_max_c")

    current_time = _as_utc(now) or datetime.now(timezone.utc)

    pill = _observation_snapshot(
        source="rapt_pill",
        temperature_c=pill_temperature_c,
        observed_at=pill_observed_at,
        now=current_time,
        freshness_seconds=freshness_seconds,
        plausible_min_c=plausible_min_c,
        plausible_max_c=plausible_max_c,
    )
    manual = _observation_snapshot(
        source="manual_reference",
        temperature_c=manual_temperature_c,
        observed_at=manual_observed_at,
        now=current_time,
        freshness_seconds=freshness_seconds,
        plausible_min_c=plausible_min_c,
        plausible_max_c=plausible_max_c,
    )

    pair_valid_and_fresh = bool(pill["fresh"] and manual["fresh"])
    delta_c: float | None = None
    absolute_delta_c: float | None = None
    within_tolerance: bool | None = None

    if pair_valid_and_fresh:
        delta_c = float(pill["temperature_c"]) - float(manual["temperature_c"])
        absolute_delta_c = abs(delta_c)
        within_tolerance = absolute_delta_c <= agreement_tolerance_c

    if not pill["fresh"] and not manual["fresh"]:
        status = "awaiting_fresh_measurements"
        reason = "Neither Pill nor manual reference is a fresh valid observation"
    elif not pill["fresh"]:
        status = "awaiting_pill"
        reason = "Manual reference is available but Pill observation is missing, invalid or stale"
    elif not manual["fresh"]:
        status = "awaiting_manual_reference"
        reason = "Pill observation is available but manual reference is missing, invalid or stale"
    elif within_tolerance:
        status = "pair_agrees"
        reason = "Pill and manual reference agree within the configured diagnostic tolerance"
    else:
        status = "pair_disagrees"
        reason = "Pill and manual reference differ beyond the configured diagnostic tolerance"

    return {
        "mode": "gf30_preflight_manual_reference",
        "control_mode": "read_only",
        "control_allowed": False,
        "status": status,
        "reason": reason,
        "freshness_seconds": freshness_seconds,
        "agreement_tolerance_c": agreement_tolerance_c,
        "pill": pill,
        "manual_reference": manual,
        "dual_measurement_available": pair_valid_and_fresh,
        "temperature_delta_c": round(delta_c, 3) if delta_c is not None else None,
        "absolute_temperature_delta_c": (
            round(absolute_delta_c, 3) if absolute_delta_c is not None else None
        ),
        "within_tolerance": within_tolerance,
        "learning_sample_eligible": pair_valid_and_fresh,
        "learning_sample_reason": (
            "fresh_dual_measurement"
            if pair_valid_and_fresh
            else "requires_fresh_pill_and_manual_reference"
        ),
        "source_selection": "no_automatic_winner",
    }
