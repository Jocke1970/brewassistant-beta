"""Pure recipe-schedule helpers for fermentation tracking.

This module deliberately contains no Home Assistant or Brewfather integration code.
BrewAssistant consumes a read-only recipe payload from an adapter and owns the
interpretation of fermentation temperature steps and ramps.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping


def _epoch_ms_to_utc(value: Any) -> datetime | None:
    try:
        milliseconds = float(value)
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(milliseconds / 1000.0, timezone.utc)


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build_recipe_temperature_schedule(
    recipe: Mapping[str, Any] | None,
    *,
    fermentation_started_at: datetime | None,
    now: datetime,
) -> dict[str, Any] | None:
    """Return BrewAssistant's current target and ramp metadata for a recipe.

    Brewfather's recipe payload uses ``actualTime`` as the scheduled step anchor,
    ``stepTemp`` as the target and ``ramp`` as ramp duration in days.  The recipe
    timestamps are shifted so the first fermentation step aligns with the actual
    fermentation start when that timestamp is available.
    """
    if not isinstance(recipe, Mapping):
        return None

    fermentation = recipe.get("fermentation")
    if not isinstance(fermentation, Mapping):
        return None

    raw_steps = fermentation.get("steps")
    if not isinstance(raw_steps, list) or not raw_steps:
        return None

    steps: list[dict[str, Any]] = []
    for raw in raw_steps:
        if not isinstance(raw, Mapping):
            continue
        actual_at = _epoch_ms_to_utc(raw.get("actualTime"))
        target = _number(raw.get("stepTemp"))
        if actual_at is None or target is None:
            continue
        ramp_days = _number(raw.get("ramp"))
        steps.append(
            {
                "actual_at": actual_at,
                "target": target,
                "ramp_days": ramp_days if ramp_days is not None and ramp_days > 0 else None,
            }
        )

    if not steps:
        return None

    steps.sort(key=lambda item: item["actual_at"])

    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    else:
        now = now.astimezone(timezone.utc)

    first_actual = steps[0]["actual_at"]
    shift = timedelta(0)
    if fermentation_started_at is not None:
        started = fermentation_started_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        else:
            started = started.astimezone(timezone.utc)
        shift = started - first_actual

    for step in steps:
        step["scheduled_at"] = step["actual_at"] + shift

    # Ramp ownership belongs here, in BrewAssistant.  A ramp is the interval
    # immediately preceding the target step's scheduled time.
    for index, step in enumerate(steps):
        if index == 0 or step["ramp_days"] is None:
            continue
        previous = steps[index - 1]
        ramp_ends_at = step["scheduled_at"]
        ramp_started_at = ramp_ends_at - timedelta(days=step["ramp_days"])
        if not ramp_started_at <= now < ramp_ends_at:
            continue

        duration = max((ramp_ends_at - ramp_started_at).total_seconds(), 1.0)
        progress = min(max((now - ramp_started_at).total_seconds() / duration, 0.0), 1.0)
        target = previous["target"] + (step["target"] - previous["target"]) * progress
        return {
            "target_temperature_c": round(target, 2),
            "ramp_active": True,
            "ramp_start_temperature_c": float(previous["target"]),
            "ramp_target_temperature_c": float(step["target"]),
            "ramp_days": float(step["ramp_days"]),
            "ramp_started_at": ramp_started_at.isoformat(),
            "ramp_ends_at": ramp_ends_at.isoformat(),
            "ramp_progress_percent": round(progress * 100.0, 1),
        }

    # Outside a ramp, use the latest step whose scheduled target time has passed.
    current = steps[0]
    for step in steps:
        if step["scheduled_at"] <= now:
            current = step
        else:
            break

    return {
        "target_temperature_c": round(float(current["target"]), 2),
        "ramp_active": False,
        "ramp_start_temperature_c": None,
        "ramp_target_temperature_c": None,
        "ramp_days": None,
        "ramp_started_at": None,
        "ramp_ends_at": None,
        "ramp_progress_percent": None,
    }
