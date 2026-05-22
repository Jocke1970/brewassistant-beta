"""Core Brewday Runtime resolver."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant, State
from homeassistant.util import dt as dt_util

BAD = {"unknown", "unavailable", "none", ""}
ACTIVE = {"running", "paused", "completed"}

BF_STATUS = "sensor.brewfather_brew_tracker_status"
BF_STAGE = "sensor.brewfather_brew_tracker_stage"
BF_STEP = "sensor.brewfather_brew_tracker_step"
BF_NEXT = "sensor.brewfather_brew_tracker_next_step"
BF_PROGRESS = "sensor.brewfather_brew_tracker_progress"
BF_REMAINING = "sensor.brewfather_brew_tracker_time_remaining"
BF_RAW = "sensor.brewfather_brew_tracker_raw"

MANUAL_MODE = "input_select.brewassistant_brewday_mode"
MANUAL_ACTIVE = "input_boolean.brewassistant_brewday_manual_active"
MANUAL_STATUS = "input_select.brewassistant_brewday_manual_status"
MANUAL_STAGE = "input_select.brewassistant_brewday_manual_stage"
MANUAL_STEP = "input_text.brewassistant_brewday_manual_step"
MANUAL_NEXT = "input_text.brewassistant_brewday_manual_next_step"
MANUAL_PROGRESS = "input_number.brewassistant_brewday_manual_progress"
MANUAL_REMAINING_MIN = "input_number.brewassistant_brewday_manual_time_remaining_min"
MANUAL_TARGET = "input_number.brewassistant_brewday_manual_target_temp"
MANUAL_ACTUAL = "input_number.brewassistant_brewday_manual_actual_temp"


def state(hass: HomeAssistant, entity_id: str, default: str = "") -> str:
    obj = hass.states.get(entity_id)
    if obj is None or obj.state in BAD:
        return default
    return obj.state


def state_obj(hass: HomeAssistant, entity_id: str) -> State | None:
    obj = hass.states.get(entity_id)
    if obj is None or obj.state in BAD:
        return None
    return obj


def attr(hass: HomeAssistant, entity_id: str, name: str) -> Any:
    obj = hass.states.get(entity_id)
    return None if obj is None else obj.attributes.get(name)


def as_float(value: Any) -> float | None:
    try:
        if value is None or str(value) in BAD:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def as_int(value: Any, default: int = 0) -> int:
    number = as_float(value)
    return default if number is None else int(number)


def clean(value: Any, limit: int = 96) -> str | None:
    if value is None or str(value) in BAD:
        return None
    text = str(value)
    for marker in ("</br>", "<br>", "<br/>", "<br />"):
        text = text.replace(marker, " ")
    while "<" in text and ">" in text:
        start = text.find("<")
        end = text.find(">", start)
        if end <= start:
            break
        text = text[:start] + text[end + 1:]
    text = " ".join(text.split()).strip()
    if not text:
        return None
    return text[: limit - 1].rstrip() + "…" if len(text) > limit else text


def step_name(step: dict[str, Any] | None, fallback: str = "Unknown") -> str:
    if not isinstance(step, dict):
        return fallback
    return (
        clean(step.get("name"))
        or clean(step.get("tooltip"))
        or clean(step.get("description"))
        or clean(step.get("type"))
        or fallback
    )


def step_desc(step: dict[str, Any] | None) -> str | None:
    if not isinstance(step, dict):
        return None
    return clean(step.get("description"), 180) or clean(step.get("tooltip"), 180)


def raw_data(hass: HomeAssistant) -> dict[str, Any]:
    data = attr(hass, BF_RAW, "data")
    return data if isinstance(data, dict) else {}


def stages(hass: HomeAssistant) -> list[dict[str, Any]]:
    values = raw_data(hass).get("stages")
    return [item for item in values if isinstance(item, dict)] if isinstance(values, list) else []


def indices(hass: HomeAssistant) -> tuple[int | None, int | None]:
    all_stages = stages(hass)
    stage_index = as_int(raw_data(hass).get("stage"), -1)
    if stage_index < 0 or stage_index >= len(all_stages):
        return None, None
    step_index = as_int(all_stages[stage_index].get("step"), -1)
    return stage_index, None if step_index < 0 else step_index


def current_stage(hass: HomeAssistant) -> dict[str, Any]:
    stage_index, _ = indices(hass)
    all_stages = stages(hass)
    if stage_index is not None and stage_index < len(all_stages):
        return all_stages[stage_index]
    fallback = attr(hass, BF_STATUS, "current_stage")
    return fallback if isinstance(fallback, dict) else {}


def current_step(hass: HomeAssistant) -> dict[str, Any]:
    stage = current_stage(hass)
    step_index = as_int(stage.get("step"), -1)
    step_list = stage.get("steps")
    if isinstance(step_list, list) and 0 <= step_index < len(step_list):
        step = step_list[step_index]
        return step if isinstance(step, dict) else {}
    fallback = attr(hass, BF_STATUS, "current_step")
    return fallback if isinstance(fallback, dict) else {}


def next_step(hass: HomeAssistant) -> tuple[str, str | None, dict[str, Any] | None]:
    stage_index, step_index = indices(hass)
    all_stages = stages(hass)
    if stage_index is not None and step_index is not None and stage_index < len(all_stages):
        step_list = all_stages[stage_index].get("steps")
        if isinstance(step_list, list):
            for pos in range(step_index + 1, len(step_list)):
                step = step_list[pos]
                if isinstance(step, dict):
                    return step_name(step, "Next step"), step_desc(step), step
        if stage_index + 1 < len(all_stages):
            stage = all_stages[stage_index + 1]
            first = (stage.get("steps") or [None])[0] if isinstance(stage.get("steps"), list) else None
            name = clean(stage.get("name")) or "Next stage"
            if isinstance(first, dict):
                return f"{name} · {step_name(first, 'Start')}", step_desc(first), first
            return name, None, stage
    fallback = attr(hass, BF_STATUS, "next_step")
    if isinstance(fallback, dict):
        return step_name(fallback, state(hass, BF_NEXT, "None")), step_desc(fallback), fallback
    return state(hass, BF_NEXT, "None"), None, None


def current_step_remaining(stage: dict[str, Any], step_index: int | None, stage_remaining: int) -> int:
    """Return time until the next Brew Tracker step boundary.

    Brewfather exposes stage remaining time plus each step's anchor time within
    that countdown. For example, a 90 min mash stage has a 10 min ramp from
    time=5400 to the next step at time=4800. The active step remaining is
    therefore stage_remaining - next_step.time, not the full stage remaining.
    """
    if step_index is None or step_index < 0:
        return stage_remaining

    step_list = stage.get("steps") if isinstance(stage.get("steps"), list) else []
    if step_index >= len(step_list):
        return stage_remaining

    boundary = 0.0
    for pos in range(step_index + 1, len(step_list)):
        step = step_list[pos]
        if isinstance(step, dict):
            anchor = as_float(step.get("time"))
            if anchor is not None:
                boundary = anchor
                break

    remaining = max(stage_remaining - int(boundary), 0)
    current = step_list[step_index]
    duration = as_float(current.get("duration")) if isinstance(current, dict) else None
    if duration and duration > 0:
        remaining = min(remaining, int(duration))
    return remaining


def snapshot_age(hass: HomeAssistant) -> int:
    obj = state_obj(hass, BF_REMAINING) or state_obj(hass, BF_STATUS)
    if obj is None:
        return 0
    return max(0, int((dt_util.utcnow() - dt_util.as_utc(obj.last_updated)).total_seconds()))


def fmt(seconds: int) -> str:
    minutes = round(seconds / 60)
    if minutes < 60:
        return f"{minutes} min"
    hours = minutes // 60
    rest = minutes % 60
    return f"{hours} h {rest} min" if rest else f"{hours} h"


def timeline(hass: HomeAssistant) -> list[dict[str, Any]]:
    stage_index, step_index = indices(hass)
    rows: list[dict[str, Any]] = []
    for s_pos, stage in enumerate(stages(hass)):
        active_stage = stage_index == s_pos
        completed_stage = stage_index is not None and s_pos < stage_index
        upcoming_stage = stage_index is None or s_pos > stage_index
        step_rows: list[dict[str, Any]] = []
        step_list = stage.get("steps") if isinstance(stage.get("steps"), list) else []
        for st_pos, step in enumerate(step_list):
            if not isinstance(step, dict):
                continue
            active = active_stage and step_index == st_pos
            completed = completed_stage or (active_stage and step_index is not None and st_pos < step_index)
            upcoming = upcoming_stage or (active_stage and step_index is not None and st_pos > step_index)
            step_rows.append({
                "index": st_pos,
                "name": step_name(step, f"Step {st_pos + 1}"),
                "description": step_desc(step),
                "type": step.get("type"),
                "time": step.get("time"),
                "duration": step.get("duration"),
                "value": step.get("value"),
                "completed": completed,
                "active": active,
                "upcoming": upcoming,
                "state": "active" if active else "completed" if completed else "upcoming",
            })
        rows.append({
            "index": s_pos,
            "name": clean(stage.get("name")) or f"Stage {s_pos + 1}",
            "type": stage.get("type"),
            "duration": stage.get("duration"),
            "remaining_seconds": stage.get("remainingSeconds"),
            "progress_percent": stage.get("progressPercent"),
            "completed": completed_stage,
            "active": active_stage,
            "upcoming": upcoming_stage,
            "state": "active" if active_stage else "completed" if completed_stage else "upcoming",
            "steps": step_rows,
        })
    return rows


def source(hass: HomeAssistant) -> str:
    mode = state(hass, MANUAL_MODE, "Auto")
    bf_status = state(hass, BF_STATUS)
    if mode == "Brewfather Brew Tracker" and bf_status in ACTIVE:
        return "Brewfather Brew Tracker"
    if mode == "Manual":
        return "Manual Brewday"
    if mode == "Auto" and bf_status in ACTIVE:
        return "Brewfather Brew Tracker"
    if mode == "Auto" and state(hass, MANUAL_ACTIVE) == "on":
        return "Manual Brewday"
    return "None"


def brewfather_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    status = state(hass, BF_STATUS, "inactive")
    raw_remaining = as_int(state(hass, BF_REMAINING), 0)
    age = snapshot_age(hass)
    stage_remaining = max(raw_remaining - age, 0) if status == "running" else max(raw_remaining, 0)
    live_timer = status == "running"
    stage = current_stage(hass)
    stage_index, step_index = indices(hass)
    step_remaining = current_step_remaining(stage, step_index, stage_remaining)
    duration = as_float(stage.get("duration"))
    progress = as_float(state(hass, BF_PROGRESS)) or 0.0
    if duration and duration > 0:
        progress = round(min(max(((duration - stage_remaining) / duration) * 100, 0), 100), 1)
    runtime_state = "completed" if status == "completed" else "awaiting_snapshot" if step_remaining <= 0 and status in {"running", "paused"} else "live" if status == "running" else "paused" if status == "paused" else "idle"
    refresh = status == "running" and step_remaining <= 0
    awaiting = runtime_state == "awaiting_snapshot"
    cur_step = current_step(hass)
    nxt_name, nxt_desc, nxt_step = next_step(hass)
    step = step_name(cur_step, state(hass, BF_STEP, "Unknown"))
    if awaiting and nxt_name in {step, "None", "Unknown"}:
        nxt_name = "Väntar på Brewfather snapshot"
        nxt_desc = "Runtime väntar på att Brewfather publicerar nästa checkpoint."
    snap_obj = state_obj(hass, BF_REMAINING) or state_obj(hass, BF_STATUS)
    stage_name = state(hass, BF_STAGE, "Unknown")
    elapsed = max((duration or 0) - stage_remaining, 0) if duration else as_float(stage.get("elapsedSeconds"))
    target = as_float(cur_step.get("value")) or as_float(nxt_step.get("value") if isinstance(nxt_step, dict) else None)
    return {
        "source": "Brewfather Brew Tracker",
        "status": status,
        "runtime_state": runtime_state,
        "stage": stage_name,
        "step": step,
        "next_step": nxt_name,
        "progress": round(progress, 1),
        "time_remaining_seconds": step_remaining,
        "time_remaining_minutes": round(step_remaining / 60),
        "target_temperature": target,
        "actual_temperature": None,
        "summary": f"{runtime_state} · {stage_name} · {step} · {round(progress)}% · {fmt(step_remaining)} kvar",
        "source_entity": BF_STATUS,
        "snapshot_entity": snap_obj.entity_id if snap_obj else None,
        "snapshot_updated_at": snap_obj.last_updated.isoformat() if snap_obj else None,
        "snapshot_age_seconds": age,
        "snapshot_age_minutes": round(age / 60),
        "raw_remaining_seconds": raw_remaining,
        "live_elapsed_since_snapshot_seconds": age,
        "live_timer_active": live_timer,
        "refresh_recommended": refresh,
        "awaiting_snapshot": awaiting,
        "stage_duration_seconds": duration,
        "stage_elapsed_seconds": elapsed,
        "stage_remaining_seconds": stage_remaining,
        "stage_remaining_minutes": round(stage_remaining / 60),
        "stage_progress_percent": round(progress, 1),
        "current_step_remaining_seconds": step_remaining,
        "current_step_remaining_minutes": round(step_remaining / 60),
        "current_step_description": step_desc(cur_step),
        "next_step_description": nxt_desc,
        "timeline": timeline(hass),
    }


def manual_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    status = state(hass, MANUAL_STATUS, "inactive")
    remaining = as_int(state(hass, MANUAL_REMAINING_MIN), 0) * 60
    progress = round(as_float(state(hass, MANUAL_PROGRESS)) or 0, 1)
    stage = state(hass, MANUAL_STAGE, "Setup")
    step = state(hass, MANUAL_STEP, "Manual step")
    runtime_state = "live" if status == "running" else "paused" if status == "paused" else "completed" if status == "completed" else "idle"
    return {
        "source": "Manual Brewday",
        "status": status,
        "runtime_state": runtime_state,
        "stage": stage,
        "step": step,
        "next_step": state(hass, MANUAL_NEXT, "None"),
        "progress": progress,
        "time_remaining_seconds": remaining,
        "time_remaining_minutes": round(remaining / 60),
        "target_temperature": as_float(state(hass, MANUAL_TARGET)),
        "actual_temperature": as_float(state(hass, MANUAL_ACTUAL)),
        "summary": f"{runtime_state} · {stage} · {step} · {round(progress)}% · {fmt(remaining)} kvar",
        "source_entity": MANUAL_MODE,
        "snapshot_entity": None,
        "snapshot_updated_at": None,
        "snapshot_age_seconds": 0,
        "snapshot_age_minutes": 0,
        "raw_remaining_seconds": remaining,
        "live_elapsed_since_snapshot_seconds": 0,
        "live_timer_active": False,
        "refresh_recommended": False,
        "awaiting_snapshot": False,
        "stage_duration_seconds": None,
        "stage_elapsed_seconds": None,
        "stage_remaining_seconds": remaining,
        "stage_remaining_minutes": round(remaining / 60),
        "stage_progress_percent": progress,
        "current_step_remaining_seconds": remaining,
        "current_step_remaining_minutes": round(remaining / 60),
        "current_step_description": state(hass, "input_text.brewassistant_brewday_manual_step_description", ""),
        "next_step_description": state(hass, "input_text.brewassistant_brewday_manual_next_step_description", ""),
        "timeline": [],
    }


def inactive_snapshot() -> dict[str, Any]:
    return {
        "source": "None", "status": "inactive", "runtime_state": "idle", "stage": "Idle", "step": "Idle", "next_step": "None",
        "progress": 0.0, "time_remaining_seconds": 0, "time_remaining_minutes": 0, "target_temperature": None, "actual_temperature": None,
        "summary": "idle · Idle", "source_entity": None, "snapshot_entity": None, "snapshot_updated_at": None, "snapshot_age_seconds": 0,
        "snapshot_age_minutes": 0, "raw_remaining_seconds": None, "live_elapsed_since_snapshot_seconds": 0, "live_timer_active": False,
        "refresh_recommended": False, "awaiting_snapshot": False, "stage_duration_seconds": None, "stage_elapsed_seconds": None,
        "stage_remaining_seconds": 0, "stage_remaining_minutes": 0, "stage_progress_percent": 0,
        "current_step_remaining_seconds": 0, "current_step_remaining_minutes": 0,
        "current_step_description": None, "next_step_description": None, "timeline": [],
    }


def build_core_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    selected = source(hass)
    if selected == "Brewfather Brew Tracker":
        return brewfather_snapshot(hass)
    if selected == "Manual Brewday":
        return manual_snapshot(hass)
    return inactive_snapshot()


def core_attrs(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in snapshot.items() if key != "timeline"}
