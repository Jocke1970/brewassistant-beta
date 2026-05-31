"""Brewday addition alert runtime."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .brewday_runtime_core import as_float, build_core_snapshot, clean, indices, stages, step_desc, step_display_name

DUE_SOON_SECONDS = 300
DUE_NOW_SECONDS = 30
ADDITION_WORDS = (
    "hop",
    "hops",
    "humle",
    "humling",
    "humlegiva",
    "addition",
    "aroma",
    "whirlpool",
)
STAGE_WORDS = ("boil", "kok", "whirlpool", "hop stand", "hopstand")


def _text(value: Any) -> str:
    return clean(value, 240) or ""


def _contains_addition_word(step: dict[str, Any]) -> bool:
    text = " ".join(
        part
        for part in (
            _text(step.get("name")),
            _text(step.get("type")),
            _text(step.get("description")),
            _text(step.get("tooltip")),
        )
        if part
    ).lower()
    return any(word in text for word in ADDITION_WORDS)


def _stage_relevant(stage: dict[str, Any]) -> bool:
    text = f"{_text(stage.get('name'))} {_text(stage.get('type'))}".lower()
    return any(word in text for word in STAGE_WORDS)


def _due_seconds(stage_remaining: int, step: dict[str, Any]) -> int | None:
    anchor = as_float(step.get("time"))
    if anchor is None:
        return None
    return max(0, int(stage_remaining - anchor))


def _candidates(hass: HomeAssistant, runtime: dict[str, Any]) -> list[dict[str, Any]]:
    all_stages = stages(hass)
    stage_index, resolved_step_index = indices(hass)
    runtime_step_index = runtime.get("runtime_resolved_step_index") or runtime.get("resolved_step_index")
    if isinstance(runtime_step_index, int):
        resolved_step_index = runtime_step_index

    stage_remaining = int(runtime.get("stage_remaining_seconds") or runtime.get("time_remaining_seconds") or 0)
    out: list[dict[str, Any]] = []
    if stage_index is None or stage_index >= len(all_stages):
        return out

    stage = all_stages[stage_index]
    if not _stage_relevant(stage):
        return out

    step_list = stage.get("steps") if isinstance(stage.get("steps"), list) else []
    for index, step in enumerate(step_list):
        if not isinstance(step, dict) or not _contains_addition_word(step):
            continue
        due = _due_seconds(stage_remaining, step)
        active_or_future = resolved_step_index is None or index >= resolved_step_index
        if due is not None and not active_or_future and due > DUE_NOW_SECONDS:
            continue
        out.append({
            "index": index,
            "name": step_display_name(step, f"Addition {index + 1}"),
            "description": step_desc(step),
            "type": step.get("type"),
            "time": step.get("time"),
            "due_seconds": due,
            "due_minutes": round(due / 60) if due is not None else None,
            "stage": _text(stage.get("name")) or f"Stage {stage_index + 1}",
        })
    out.sort(key=lambda item: (999999 if item.get("due_seconds") is None else int(item["due_seconds"]), item.get("index") or 0))
    return out


def build_addition_alert_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    runtime = build_core_snapshot(hass)
    runtime_state = str(runtime.get("runtime_state") or "idle")
    candidates = _candidates(hass, runtime) if runtime_state in {"live", "running", "paused", "awaiting_snapshot"} else []
    item = candidates[0] if candidates else None
    due_seconds = item.get("due_seconds") if item else None

    if not item:
        state = "off" if runtime_state in {"idle", "completed"} else "none"
    elif due_seconds is not None and due_seconds <= DUE_NOW_SECONDS:
        state = "due_now"
    elif due_seconds is not None and due_seconds <= DUE_SOON_SECONDS:
        state = "due_soon"
    else:
        state = "upcoming"

    name = item.get("name") if item else None
    due_minutes = item.get("due_minutes") if item else None
    if state == "due_now" and name:
        message = f"Bryggtillsats nu: {name}"
    elif state == "due_soon" and name:
        message = f"Bryggtillsats om ca {due_minutes} min: {name}"
    elif state == "upcoming" and name:
        message = f"Nästa bryggtillsats: {name} om ca {due_minutes} min"
    elif runtime_state == "completed":
        message = "Brewday completed"
    else:
        message = "Ingen kommande bryggtillsats hittad"

    return {
        "source": "brewday_addition_alerts",
        "state": state,
        "due": state in {"due_now", "due_soon"},
        "due_now": state == "due_now",
        "due_soon": state == "due_soon",
        "message": message,
        "next_addition_name": name,
        "next_addition_description": item.get("description") if item else None,
        "next_addition_stage": item.get("stage") if item else None,
        "next_addition_in_seconds": due_seconds,
        "next_addition_in_minutes": due_minutes,
        "runtime_state": runtime_state,
        "runtime_stage": runtime.get("stage"),
        "runtime_step": runtime.get("step"),
        "candidate_count": len(candidates),
        "candidates": candidates[:8],
        "due_soon_threshold_seconds": DUE_SOON_SECONDS,
        "due_now_threshold_seconds": DUE_NOW_SECONDS,
    }
