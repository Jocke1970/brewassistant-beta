"""Brewday Stage Engine.

Interprets normalized Brewday Runtime and BrewZilla telemetry into a
human-friendly hot-side process stage.

This module is read-only. It does not control BrewZilla hardware.
"""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

BAD_STATES = {"unknown", "unavailable", "none", ""}

BREWDAY_STATE = "sensor.brewassistant_brewday_runtime_state"
BREWDAY_STAGE = "sensor.brewassistant_brewday_runtime_stage"
BREWDAY_STEP = "sensor.brewassistant_brewday_runtime_step"
BREWDAY_NEXT_STEP = "sensor.brewassistant_brewday_runtime_next_step"
BREWDAY_REMAINING_MIN = "sensor.brewassistant_brewday_live_time_remaining_minutes"
BREWDAY_PROGRESS = "sensor.brewassistant_brewday_live_progress"

BREWZILLA_STATE = "sensor.brewassistant_brewzilla_runtime_state"
BREWZILLA_TEMP = "sensor.brewassistant_brewzilla_current_temperature"
BREWZILLA_TARGET = "sensor.brewassistant_brewzilla_target_temperature"
BREWZILLA_DELTA = "sensor.brewassistant_brewzilla_temperature_delta"
BREWZILLA_POWER = "sensor.brewassistant_brewzilla_power"
BREWZILLA_HEAT_UTIL = "sensor.brewassistant_brewzilla_heat_utilization"
BREWZILLA_PUMP_UTIL = "sensor.brewassistant_brewzilla_pump_utilization"

COOLING_KEYWORDS = (
    "cool",
    "cooling",
    "chill",
    "chilling",
    "counterflow",
    "counter-flow",
    "counter flow",
    "counterflow chiller",
    "motström",
    "motstrom",
    "motströmskyl",
    "motstromskyl",
    "kyl",
    "kyla",
    "kylning",
    "kyl vört",
    "kyl vort",
    "wort cooling",
    "wort chilling",
    "cool wort",
    "chill wort",
)

PITCH_READY_KEYWORDS = (
    "pitch ready",
    "ready to pitch",
    "pitch yeast",
    "pitching",
    "jäst",
    "jasta",
    "tillsätt jäst",
    "tillsatt jast",
    "pitch",
)

TRANSFER_TO_FERMENTER_KEYWORDS = (
    "transfer to fermenter",
    "transfer wort",
    "move to fermenter",
    "fermenter transfer",
    "överför till jäskärl",
    "overfor till jaskarl",
    "för över till jäskärl",
    "for over till jaskarl",
)


def _state(hass: HomeAssistant, entity_id: str, default: str | None = None) -> str | None:
    entity_state = hass.states.get(entity_id)
    if entity_state is None or entity_state.state in BAD_STATES:
        return default
    return entity_state.state


def _float(hass: HomeAssistant, entity_id: str) -> float | None:
    raw = _state(hass, entity_id)
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _contains(value: str | None, *needles: str) -> bool:
    haystack = (value or "").lower()
    return any(needle.lower() in haystack for needle in needles)


def _stage_icon(stage: str) -> str:
    return {
        "Idle": "mdi:kettle-outline",
        "Prepare": "mdi:clipboard-check-outline",
        "Strike Water": "mdi:water-thermometer",
        "Heating Strike": "mdi:fire",
        "Mash In": "mdi:grain",
        "Mash": "mdi:pot-steam",
        "Mash Out": "mdi:thermometer-chevron-up",
        "Heating To Boil": "mdi:kettle-steam",
        "Boiling": "mdi:kettle-steam",
        "Hop Addition": "mdi:hop",
        "Whirlpool": "mdi:rotate-3d-variant",
        "Wort Cooling": "mdi:snowflake-thermometer",
        "Pitch Ready": "mdi:yeast",
        "Transfer": "mdi:transfer",
        "Cleaning": "mdi:spray-bottle",
        "Completed": "mdi:check-circle",
    }.get(stage, "mdi:state-machine")


def _stage_group(stage: str) -> str:
    if stage == "Prepare":
        return "prep"
    if stage in {"Strike Water", "Heating Strike", "Mash In", "Mash", "Mash Out"}:
        return "mash"
    if stage in {"Heating To Boil", "Boiling", "Hop Addition"}:
        return "boil"
    if stage in {"Wort Cooling", "Pitch Ready"}:
        return "cooling"
    if stage in {"Whirlpool", "Transfer"}:
        return "post_boil"
    if stage in {"Cleaning", "Completed"}:
        return "wrap_up"
    return "idle"


def _stage_priority(stage: str) -> str:
    if stage in {"Hop Addition", "Pitch Ready"}:
        return "attention"
    if stage in {"Boiling", "Wort Cooling", "Transfer"}:
        return "active"
    if stage in {"Heating Strike", "Heating To Boil", "Mash Out"}:
        return "warming"
    if stage in {"Mash", "Whirlpool", "Strike Water", "Mash In", "Prepare"}:
        return "monitor"
    if stage == "Completed":
        return "done"
    return "idle"


def _suggested_action(stage: str, remaining_min: float | None, delta: float | None) -> str:
    remaining = remaining_min if remaining_min is not None else 0
    abs_delta = abs(delta) if delta is not None else None

    if stage == "Idle":
        return "Prepare brewday or connect Brew Tracker"
    if stage == "Prepare":
        return "Prepare equipment and verify brewday setup"
    if stage == "Strike Water":
        return "Verify strike temperature before mash in"
    if stage == "Heating Strike":
        return "Heat toward strike target"
    if stage == "Mash In":
        return "Add grain and stabilize mash temperature"
    if stage == "Mash":
        if remaining > 0:
            return f"Maintain mash · {remaining:.0f} min remaining"
        return "Maintain mash temperature"
    if stage == "Mash Out":
        return "Ramp to mash-out target"
    if stage == "Heating To Boil":
        return "Heat to boil and watch for hot break"
    if stage == "Boiling":
        if remaining > 0:
            return f"Maintain boil · {remaining:.0f} min remaining"
        return "Maintain stable boil"
    if stage == "Hop Addition":
        return "Add scheduled hops now"
    if stage == "Whirlpool":
        return "Run whirlpool or hop stand schedule"
    if stage == "Wort Cooling":
        return "Start/monitor counterflow cooling"
    if stage == "Pitch Ready":
        return "Transfer and pitch when sanitation is ready"
    if stage == "Transfer":
        return "Transfer wort to fermenter"
    if stage == "Cleaning":
        return "Clean and rinse BrewZilla and chiller"
    if stage == "Completed":
        return "Brewday completed"
    if abs_delta is not None and abs_delta > 2:
        return "Monitor temperature delta"
    return "Monitor brewday"


def _control_hint(stage: str, bz_state: str | None, power: float | None, pump_util: float | None) -> str:
    power_value = power if power is not None else 0
    pump_value = pump_util if pump_util is not None else 0
    bz = bz_state or "unknown"

    if stage in {"Idle", "Prepare", "Completed"}:
        return "observe_only"
    if stage in {"Heating Strike", "Mash Out", "Heating To Boil"}:
        return "target_sync_candidate"
    if stage in {"Mash", "Whirlpool"} and pump_value > 0:
        return "circulation_active"
    if stage == "Boiling" and power_value > 0:
        return "boil_monitor"
    if stage == "Wort Cooling":
        return "cooling_monitor"
    if stage in {"Hop Addition", "Pitch Ready", "Transfer"}:
        return "manual_attention"
    return f"observe_{bz}"


def _resolve_stage(
    *,
    runtime_state: str | None,
    runtime_stage: str | None,
    runtime_step: str | None,
    next_step: str | None,
    remaining_min: float | None,
    progress: float | None,
    bz_state: str | None,
    temp: float | None,
    target: float | None,
    delta: float | None,
    power: float | None,
    pump_util: float | None,
) -> tuple[str, str]:
    """Resolve interpreted brewday process stage and reason."""
    if runtime_state in {None, "idle", "inactive"}:
        return "Idle", "Brewday runtime is idle"

    if runtime_state == "completed":
        return "Completed", "Brewday runtime completed"

    # Only the active stage/step should determine the current interpreted stage.
    # next_step is intentionally kept out of this blob so an upcoming "Chill wort"
    # step does not wake the cooling cockpit while Whirlpool is still active.
    current_blob = f"{runtime_stage or ''} {runtime_step or ''}".lower()
    next_blob = f"{next_step or ''}".lower()
    temp_value = temp if temp is not None else -999
    target_value = target if target is not None else None
    power_value = power if power is not None else 0
    pump_value = pump_util if pump_util is not None else 0
    delta_value = delta if delta is not None else None

    if runtime_state == "prepared":
        return "Prepare", "Manual brewday prepared; waiting to start"
    if _contains(current_blob, "setup", "prepare equipment", "prepare brewday"):
        return "Prepare", "Runtime text indicates brewday preparation"

    if _contains(current_blob, "clean"):
        return "Cleaning", "Runtime text indicates cleaning"
    if _contains(current_blob, *COOLING_KEYWORDS):
        return "Wort Cooling", "Runtime text indicates wort cooling/chilling"
    if _contains(current_blob, *PITCH_READY_KEYWORDS) and temp_value <= 25:
        return "Pitch Ready", "Runtime text and temperature indicate pitch readiness"
    if _contains(current_blob, *TRANSFER_TO_FERMENTER_KEYWORDS) and temp_value <= 25:
        return "Pitch Ready", "Runtime text indicates transfer-to-fermenter and temperature is pitch-safe"
    if _contains(current_blob, "transfer"):
        return "Transfer", "Runtime text indicates transfer"
    if _contains(current_blob, "whirlpool", "hop stand", "hopstand"):
        return "Whirlpool", "Runtime text indicates whirlpool/hop stand"
    if temp_value >= 95 and power_value >= 1000:
        return "Boiling", "BrewZilla temperature and power indicate boil"
    if _contains(current_blob, "boil"):
        if temp_value < 92 and power_value >= 500:
            return "Heating To Boil", "Boil stage active and temperature below boil range"
        return "Boiling", "Runtime stage indicates boil"
    if _contains(current_blob, "hop") and _contains(current_blob, "addition", "giva"):
        return "Hop Addition", "Runtime text indicates hop addition"
    if _contains(current_blob, "mash out"):
        return "Mash Out", "Runtime text indicates mash out"
    if _contains(current_blob, "mash", "mäsk"):
        if _contains(current_blob, "start", "inmäsk"):
            if target_value is not None and temp_value < target_value - 2:
                return "Heating Strike", "Mash start active and temperature below target"
            return "Mash In", "Mash start/inmash step active"
        if delta_value is not None and abs(delta_value) <= 1.0:
            return "Mash", "Mash stage active and BrewZilla is near target"
        if target_value is not None and temp_value < target_value - 1:
            return "Heating Strike", "Mash stage active and BrewZilla below target"
        return "Mash", "Runtime stage indicates mash"

    # If the active text is generic but the upcoming step is a cooling/pitch action,
    # keep the current stage post-boil instead of prematurely entering cooling.
    if _contains(next_blob, *COOLING_KEYWORDS, *PITCH_READY_KEYWORDS):
        if _contains(current_blob, "whirlpool", "hop stand", "hopstand"):
            return "Whirlpool", "Runtime current stage is whirlpool; cooling is upcoming"

    if target_value is not None and temp_value < target_value - 3 and power_value >= 500:
        return "Heating Strike", "BrewZilla heating toward target"
    if target_value is not None and abs(temp_value - target_value) <= 1.0 and pump_value > 0:
        return "Strike Water", "BrewZilla near target with circulation"
    if remaining_min is not None and progress is not None:
        return "Strike Water", "Runtime active with countdown/progress"
    if bz_state in {"heating", "heating_pumping", "heating_needed"}:
        return "Heating Strike", "BrewZilla hardware state indicates heating"
    return "Idle", "No specific hot-side stage detected"


def build_brewday_stage_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    """Build interpreted Brewday Stage Engine snapshot."""
    runtime_state = _state(hass, BREWDAY_STATE, "idle")
    runtime_stage = _state(hass, BREWDAY_STAGE, "Idle")
    runtime_step = _state(hass, BREWDAY_STEP, "Idle")
    next_step = _state(hass, BREWDAY_NEXT_STEP, "None")
    remaining_min = _float(hass, BREWDAY_REMAINING_MIN)
    progress = _float(hass, BREWDAY_PROGRESS)
    bz_state = _state(hass, BREWZILLA_STATE, "unknown")
    temp = _float(hass, BREWZILLA_TEMP)
    target = _float(hass, BREWZILLA_TARGET)
    delta = _float(hass, BREWZILLA_DELTA)
    power = _float(hass, BREWZILLA_POWER)
    heat_util = _float(hass, BREWZILLA_HEAT_UTIL)
    pump_util = _float(hass, BREWZILLA_PUMP_UTIL)

    stage, reason = _resolve_stage(
        runtime_state=runtime_state,
        runtime_stage=runtime_stage,
        runtime_step=runtime_step,
        next_step=next_step,
        remaining_min=remaining_min,
        progress=progress,
        bz_state=bz_state,
        temp=temp,
        target=target,
        delta=delta,
        power=power,
        pump_util=pump_util,
    )

    status_line = stage
    if temp is not None and target is not None:
        status_line = f"{stage} · {temp:.1f} → {target:.1f} °C"
    if remaining_min is not None and remaining_min > 0:
        status_line = f"{status_line} · {remaining_min:.0f} min left"

    return {
        "stage": stage,
        "stage_reason": reason,
        "stage_icon": _stage_icon(stage),
        "stage_group": _stage_group(stage),
        "stage_priority": _stage_priority(stage),
        "suggested_action": _suggested_action(stage, remaining_min, delta),
        "control_hint": _control_hint(stage, bz_state, power, pump_util),
        "status_line": status_line,
        "runtime_state": runtime_state,
        "runtime_stage": runtime_stage,
        "runtime_step": runtime_step,
        "next_step": next_step,
        "remaining_minutes": remaining_min,
        "progress_percent": progress,
        "brewzilla_state": bz_state,
        "brewzilla_temperature": temp,
        "brewzilla_target": target,
        "brewzilla_delta": delta,
        "brewzilla_power": power,
        "brewzilla_heat_utilization": heat_util,
        "brewzilla_pump_utilization": pump_util,
    }


def brewday_stage_attrs(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Return common Brewday Stage Engine attributes."""
    return dict(snapshot)
