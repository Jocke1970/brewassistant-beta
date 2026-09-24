"""Passive GF30 thermal-learning calculations.

These helpers summarize already-recorded observations.  They do not write any
Home Assistant state, choose a control sensor, calculate actuator commands or
change temperature targets.
"""

from __future__ import annotations

from datetime import datetime, timezone
from statistics import mean
from typing import Any

MIN_RATE_INTERVAL_SECONDS = 60
MAX_RATE_INTERVAL_SECONDS = 6 * 60 * 60


def _parse_datetime(value: Any) -> datetime | None:
    """Parse an ISO/datetime value without Home Assistant dependencies."""
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _as_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed != parsed or parsed in {float("inf"), float("-inf")}:
        return None
    return parsed


def _confidence(sample_count: int, span_hours: float | None) -> str:
    """Return deliberately conservative observational confidence."""
    if sample_count <= 0:
        return "none"
    if sample_count < 3:
        return "insufficient"
    if sample_count < 6 or span_hours is None or span_hours < 1:
        return "early"
    return "observational"


def summarize_preflight_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize manual/Pill preflight records for read-only learning."""
    pair_deltas: list[float] = []
    pair_abs_deltas: list[float] = []
    pair_times: list[datetime] = []
    phase_counts: dict[str, int] = {}

    pill_points: list[tuple[datetime, float, str]] = []
    for record in records:
        phase = str(record.get("phase") or "unspecified").strip().lower()
        phase_counts[phase] = phase_counts.get(phase, 0) + 1

        if bool(record.get("learning_sample_eligible")):
            delta = _as_float(record.get("temperature_delta_c"))
            abs_delta = _as_float(record.get("absolute_temperature_delta_c"))
            observed_at = _parse_datetime(record.get("manual_observed_at"))
            if delta is not None and abs_delta is not None:
                pair_deltas.append(delta)
                pair_abs_deltas.append(abs_delta)
                if observed_at is not None:
                    pair_times.append(observed_at)

        pill_temp = _as_float(record.get("pill_temperature_c"))
        pill_at = _parse_datetime(record.get("pill_observed_at"))
        if pill_temp is not None and pill_at is not None:
            pill_points.append((pill_at, pill_temp, phase))

    pill_points.sort(key=lambda item: item[0])

    rates: list[dict[str, Any]] = []
    for previous, current in zip(pill_points, pill_points[1:]):
        previous_at, previous_temp, previous_phase = previous
        current_at, current_temp, current_phase = current
        seconds = (current_at - previous_at).total_seconds()
        if seconds < MIN_RATE_INTERVAL_SECONDS or seconds > MAX_RATE_INTERVAL_SECONDS:
            continue
        rate = (current_temp - previous_temp) / (seconds / 3600)
        rates.append(
            {
                "from": previous_at.isoformat(),
                "to": current_at.isoformat(),
                "rate_c_per_hour": round(rate, 3),
                "phase": (
                    current_phase
                    if current_phase == previous_phase
                    else f"{previous_phase}->{current_phase}"
                ),
            }
        )

    cooling_rates = [
        float(item["rate_c_per_hour"])
        for item in rates
        if float(item["rate_c_per_hour"]) < 0
    ]
    warming_rates = [
        float(item["rate_c_per_hour"])
        for item in rates
        if float(item["rate_c_per_hour"]) > 0
    ]

    span_hours: float | None = None
    if len(pair_times) >= 2:
        span_hours = round(
            (max(pair_times) - min(pair_times)).total_seconds() / 3600,
            2,
        )

    mean_delta = round(mean(pair_deltas), 3) if pair_deltas else None
    mean_abs_delta = round(mean(pair_abs_deltas), 3) if pair_abs_deltas else None
    max_abs_delta = round(max(pair_abs_deltas), 3) if pair_abs_deltas else None

    if mean_delta is None:
        observed_bias = "unknown"
    elif abs(mean_delta) < 0.1:
        observed_bias = "balanced"
    elif mean_delta > 0:
        observed_bias = "pill_warmer"
    else:
        observed_bias = "manual_reference_warmer"

    return {
        "mode": "read_only_learning",
        "sample_count": len(records),
        "eligible_pair_count": len(pair_deltas),
        "pair_span_hours": span_hours,
        "mean_delta_c": mean_delta,
        "mean_absolute_delta_c": mean_abs_delta,
        "max_absolute_delta_c": max_abs_delta,
        "observed_bias": observed_bias,
        "confidence": _confidence(len(pair_deltas), span_hours),
        "phase_counts": phase_counts,
        "rate_sample_count": len(rates),
        "latest_pill_rate_c_per_hour": (
            rates[-1]["rate_c_per_hour"] if rates else None
        ),
        "mean_cooling_rate_c_per_hour": (
            round(mean(cooling_rates), 3) if cooling_rates else None
        ),
        "mean_warming_rate_c_per_hour": (
            round(mean(warming_rates), 3) if warming_rates else None
        ),
        "recent_rates": rates[-10:],
        "automatic_sensor_correction": False,
        "automatic_control": False,
        "control_recommendation": None,
    }
