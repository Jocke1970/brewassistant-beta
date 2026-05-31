"""Brewday addition alert runtime."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .brewday_runtime_core import as_float, build_core_snapshot, clean, indices, stages, step_desc, step_display_name

DUE_SOON_SECONDS = 300
DUE_NOW_SECONDS = 30
COUNTERFLOW_CHILLER_ENABLED = "input_boolean.brewassistant_counterflow_chiller_enabled"
COUNTERFLOW_CHILLER_SANITIZE_MINUTES = "input_number.brewassistant_counterflow_chiller_sanitize_minutes"
COUNTERFLOW_CHILLER_DEFAULT_SANITIZE_SECONDS = 15 * 60
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
BOIL_WORDS = ("boil", "kok", "boiling", "heating to boil", "värm till kok", "kokning")


def _text(value: Any) -> str:
    return clean(value, 240) or ""


def _bool_state(hass: HomeAssistant, entity_id: str, default: bool = False) -> bool:
    fallback = "on" if default else "off"
    state = hass.states.get(entity_id)
    raw = state.state if state is not None else fallback
    return str(raw).lower() in {"on", "true", "yes", "enabled"}


def _number_state(hass: HomeAssistant, entity_id: str, default: float) -> float:
    state = hass.states.get(entity_id)
    if state is None or state.state in {"unknown", "unavailable", "none", ""}:
        return default
    try:
        return float(state.state)
    except (TypeError, ValueError):
        return default


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


def _stage_is_boil(stage: dict[str, Any], runtime: dict[str, Any]) -> bool:
    text = " ".join(
        part
        for part in (
            _text(stage.get("name")),
            _text(stage.get("type")),
            _text(runtime.get("stage")),
            _text(runtime.get("step")),
            _text(runtime.get("raw_step_name")),
        )
        if part
    ).lower()
    return any(word in text for word in BOIL_WORDS)


def _due_seconds(stage_remaining: int, step: dict[str, Any]) -> int | None:
    anchor = as_float(step.get("time"))
    if anchor is None:
        return None
    return max(0, int(stage_remaining - anchor))


def _counterflow_sanitize_candidate(
    hass: HomeAssistant,
    runtime: dict[str, Any],
    stage: dict[str, Any],
    stage_index: int,
    stage_remaining: int,
) -> dict[str, Any] | None:
    """Return counterflow chiller sanitation reminder candidate during boil."""
    if not _bool_state(hass, COUNTERFLOW_CHILLER_ENABLED, False):
        return None
    if not _stage_is_boil(stage, runtime):
        return None

    sanitize_minutes = _number_state(
        hass,
        COUNTERFLOW_CHILLER_SANITIZE_MINUTES,
        COUNTERFLOW_CHILLER_DEFAULT_SANITIZE_SECONDS / 60,
    )
    sanitize_seconds = max(60, int(sanitize_minutes * 60))
    due = max(0, int(stage_remaining - sanitize_seconds))
    due_minutes = round(due / 60)
    return {
        "index": -1000,
        "name": "Counter Flow Chiller",
        "description": f"Koppla in counter flow chiller och kör vörten genom den sista {round(sanitize_seconds / 60)} min av koket för sterilisering.",
        "type": "counterflow_chiller_sanitize",
        "time": sanitize_seconds,
        "due_seconds": due,
        "due_minutes": due_minutes,
        "stage": _text(stage.get("name")) or f"Stage {stage_index + 1}",
        "sanitize_seconds_before_end": sanitize_seconds,
        "sanitize_minutes_before_end": round(sanitize_seconds / 60),
    }


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
    counterflow_candidate = _counterflow_sanitize_candidate(hass, runtime, stage, stage_index, stage_remaining)
    if counterflow_candidate is not None:
        out.append(counterflow_candidate)

    if not _stage_relevant(stage):
        out.sort(key=lambda item: (999999 if item.get("due_seconds") is None else int(item["due_seconds"]), item.get("index") or 0))
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
    counterflow_enabled = _bool_state(hass, COUNTERFLOW_CHILLER_ENABLED, False)
    counterflow_sanitize_minutes = _number_state(
        hass,
        COUNTERFLOW_CHILLER_SANITIZE_MINUTES,
        COUNTERFLOW_CHILLER_DEFAULT_SANITIZE_SECONDS / 60,
    )
    candidates = _candidates(hass, runtime) if runtime_state in {"live", "running", "paused", "awaiting_snapshot"} else []
    item = candidates[0] if candidates else None
    due_seconds = item.get("due_seconds") if item else None
    item_type = item.get("type") if item else None

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
    if item_type == "counterflow_chiller_sanitize" and state == "due_now":
        message = f"Koppla in {name} nu för sterilisering under sista {item.get('sanitize_minutes_before_end')} min av koket"
    elif item_type == "counterflow_chiller_sanitize" and state == "due_soon":
        message = f"Förbered {name}: koppla in om ca {due_minutes} min för sterilisering"
    elif item_type == "counterflow_chiller_sanitize" and state == "upcoming":
        message = f"{name}: sterilisering startar om ca {due_minutes} min"
    elif state == "due_now" and name:
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
        "next_addition_type": item_type,
        "next_addition_in_seconds": due_seconds,
        "next_addition_in_minutes": due_minutes,
        "runtime_state": runtime_state,
        "runtime_stage": runtime.get("stage"),
        "runtime_step": runtime.get("step"),
        "candidate_count": len(candidates),
        "candidates": candidates[:8],
        "counterflow_chiller_enabled": counterflow_enabled,
        "counterflow_chiller_enabled_entity": COUNTERFLOW_CHILLER_ENABLED,
        "counterflow_chiller_sanitize_minutes": counterflow_sanitize_minutes,
        "counterflow_chiller_sanitize_minutes_entity": COUNTERFLOW_CHILLER_SANITIZE_MINUTES,
        "due_soon_threshold_seconds": DUE_SOON_SECONDS,
        "due_now_threshold_seconds": DUE_NOW_SECONDS,
    }
