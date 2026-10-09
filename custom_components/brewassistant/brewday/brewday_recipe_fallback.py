"""Convert retained external Brewday context into a conservative ManualPlan.

This adapter is intentionally source-agnostic. It consumes the normalized
Brewday timeline already produced for Brewfather or RAPT and creates a Manual
Brewday plan without inventing recipe steps that were not present in the last
trusted external snapshot.

Fallback progression remains operator-led. Unknown timing units are omitted
rather than guessed.
"""

from __future__ import annotations

from typing import Any

from .manual_brewday_runtime import ManualPlan, ManualStage, ManualStep


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _seconds(value: Any) -> int | None:
    number = _num(value)
    if number is None or number <= 0:
        return None
    return max(1, int(round(number)))


def _rapt_duration_seconds(step: dict[str, Any]) -> int | None:
    """Convert RAPT length only when its unit is explicit."""
    length = _num(step.get("rapt_length"))
    if length is None or length <= 0:
        return None
    unit = str(step.get("rapt_duration_type") or "").strip().lower()
    if unit in {"second", "seconds", "sec", "secs", "s"}:
        return max(1, int(round(length)))
    if unit in {"minute", "minutes", "min", "mins", "m"}:
        return max(1, int(round(length * 60)))
    if unit in {"hour", "hours", "hr", "hrs", "h"}:
        return max(1, int(round(length * 3600)))
    return None


def _step_duration_seconds(step: dict[str, Any]) -> int | None:
    # Brewfather normalized timeline durations are seconds. RAPT exposes an
    # explicit duration unit separately and must never be guessed.
    if step.get("rapt_length") is not None:
        return _rapt_duration_seconds(step)
    return _seconds(step.get("duration"))


def _step_from_row(row: dict[str, Any], index: int) -> ManualStep:
    name = str(row.get("name") or row.get("raw_name") or f"Step {index + 1}")
    description = row.get("description")
    target = _num(row.get("value"))
    pause_before = row.get("pause_before")
    if pause_before is None:
        pause_before = True
    return ManualStep(
        name=name,
        step_type=str(row.get("type") or "external_recipe"),
        description=str(description) if description is not None else None,
        duration_seconds=_step_duration_seconds(row),
        target_temperature=target,
        pause_before=bool(pause_before),
        auto_advance=False,
    )


def plan_from_external_snapshot(snapshot: dict[str, Any]) -> ManualPlan | None:
    """Build a ManualPlan from the normalized external timeline."""
    raw_timeline = snapshot.get("timeline")
    stages: list[ManualStage] = []
    if isinstance(raw_timeline, list):
        for stage_index, raw_stage in enumerate(raw_timeline):
            if not isinstance(raw_stage, dict):
                continue
            rows = raw_stage.get("steps")
            steps = tuple(
                _step_from_row(row, step_index)
                for step_index, row in enumerate(rows if isinstance(rows, list) else [])
                if isinstance(row, dict)
            )
            if not steps:
                continue
            stages.append(
                ManualStage(
                    name=str(raw_stage.get("name") or f"Stage {stage_index + 1}"),
                    stage_type=str(raw_stage.get("type") or "external_recipe"),
                    steps=steps,
                )
            )

    # A trustworthy active snapshot without a full timeline is still more useful
    # than dropping to the generic default BIAB plan.
    if not stages:
        step_name = str(snapshot.get("step") or "").strip()
        if not step_name or step_name.lower() in {"idle", "unknown", "none"}:
            return None
        current = ManualStep(
            name=step_name,
            step_type="external_current_step",
            description=(
                str(snapshot.get("current_step_description"))
                if snapshot.get("current_step_description") is not None
                else None
            ),
            target_temperature=_num(snapshot.get("target_temperature")),
            pause_before=False,
            auto_advance=False,
        )
        extra: list[ManualStep] = [current]
        next_name = str(snapshot.get("next_step") or "").strip()
        if next_name and next_name.lower() not in {"none", "unknown", step_name.lower()}:
            extra.append(
                ManualStep(
                    name=next_name,
                    step_type="external_next_step",
                    description=(
                        str(snapshot.get("next_step_description"))
                        if snapshot.get("next_step_description") is not None
                        else None
                    ),
                    pause_before=True,
                    auto_advance=False,
                )
            )
        stages.append(
            ManualStage(
                name=str(snapshot.get("stage") or "Retained recipe"),
                stage_type="external_recipe",
                steps=tuple(extra),
            )
        )

    name = (
        snapshot.get("profile_name")
        or snapshot.get("recipe_name")
        or snapshot.get("batch_name")
        or "Retained external recipe"
    )
    return ManualPlan(name=str(name), stages=tuple(stages))


def active_position_from_snapshot(
    snapshot: dict[str, Any],
    plan: ManualPlan,
) -> tuple[int, int]:
    """Resolve the external active stage/step into the converted ManualPlan."""
    raw_timeline = snapshot.get("timeline")
    if isinstance(raw_timeline, list):
        converted_stage = 0
        for raw_stage in raw_timeline:
            if not isinstance(raw_stage, dict):
                continue
            rows = raw_stage.get("steps")
            valid_rows = [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []
            if not valid_rows:
                continue
            if raw_stage.get("active"):
                for step_index, row in enumerate(valid_rows):
                    if row.get("active"):
                        return converted_stage, min(step_index, len(plan.stages[converted_stage].steps) - 1)
                return converted_stage, 0
            converted_stage += 1

    stage_name = str(snapshot.get("stage") or "")
    step_name = str(snapshot.get("step") or "")
    for stage_index, stage in enumerate(plan.stages):
        if stage.name == stage_name:
            for step_index, step in enumerate(stage.steps):
                if step.name == step_name:
                    return stage_index, step_index

    for stage_index, stage in enumerate(plan.stages):
        for step_index, step in enumerate(stage.steps):
            if step.name == step_name:
                return stage_index, step_index
    return 0, 0
