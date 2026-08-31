"""Cooling Advice v2 calculations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .cooling_runtime import METHOD_COUNTERFLOW, READY_TOLERANCE_C, build_cooling_runtime_snapshot

DOMAIN_DATA_KEY = "cooling_advice_v2"
MIN_SAMPLE_SECONDS = 60
MAX_SAMPLE_SECONDS = 7200
MIN_MEANINGFUL_RATE_C_PER_H = 0.2


@dataclass(slots=True)
class CoolingSample:
    timestamp: datetime
    temperature: float
    source_entity: str


def _store(hass: HomeAssistant) -> dict[str, CoolingSample | None]:
    return hass.data.setdefault("brewassistant", {}).setdefault(
        DOMAIN_DATA_KEY,
        {"previous": None, "latest": None},
    )


def _update_trend(
    hass: HomeAssistant,
    temperature: float | None,
    source_entity: str | None,
) -> tuple[CoolingSample | None, CoolingSample | None]:
    store = _store(hass)
    previous = store.get("previous")
    latest = store.get("latest")
    if temperature is None or source_entity is None:
        return previous, latest

    now = dt_util.utcnow()
    sample = CoolingSample(now, round(float(temperature), 3), source_entity)
    if latest is None:
        store["latest"] = sample
        return None, sample

    elapsed = (now - latest.timestamp).total_seconds()
    same_source = sample.source_entity == latest.source_entity
    same_value = abs(sample.temperature - latest.temperature) < 0.01
    if elapsed < MIN_SAMPLE_SECONDS and same_source:
        return previous, latest
    if same_value and same_source and elapsed < MAX_SAMPLE_SECONDS:
        return previous, latest

    store["previous"] = latest
    store["latest"] = sample
    return latest, sample


def _cooling_rate(previous: CoolingSample | None, latest: CoolingSample | None) -> float | None:
    if previous is None or latest is None:
        return None
    elapsed_seconds = (latest.timestamp - previous.timestamp).total_seconds()
    if elapsed_seconds < MIN_SAMPLE_SECONDS or elapsed_seconds > MAX_SAMPLE_SECONDS:
        return None
    rate = (previous.temperature - latest.temperature) / (elapsed_seconds / 3600)
    return round(max(0.0, rate), 2)


def build_cooling_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    runtime = build_cooling_runtime_snapshot(hass)
    process_temp = runtime.get("process_temperature")
    target = runtime.get("target_temperature")
    source = runtime.get("process_temperature_source")
    state = str(runtime.get("state") or "IDLE")
    method = str(runtime.get("method") or "")
    pump_state = str(runtime.get("wort_pump_state") or "unknown")

    previous, latest = _update_trend(hass, process_temp, source)
    rate = _cooling_rate(previous, latest)

    delta = None
    eta_minutes = None
    target_ready = False
    if process_temp is not None and target is not None:
        delta = round(float(process_temp) - float(target), 2)
        target_ready = abs(delta) <= READY_TOLERANCE_C
        if delta > READY_TOLERANCE_C and rate is not None and rate > MIN_MEANINGFUL_RATE_C_PER_H:
            eta_minutes = round((delta / rate) * 60, 1)

    if state == "IDLE":
        status = "standby"
        advice = "Cooling standby."
    elif state == "PREPARE":
        status = "prepare"
        advice = "Prepare cooling equipment for sanitation."
    elif state == "SANITIZE":
        if method == METHOD_COUNTERFLOW and pump_state != "on":
            status = "wort_pump_required"
            advice = "Start wort circulation through the CFC. Cooling water must remain off."
        else:
            status = "sanitizing"
            advice = "Sanitation active. Keep cooling water off."
    elif process_temp is None:
        status = "no_outlet_temperature" if method == METHOD_COUNTERFLOW else "no_process_temperature"
        advice = "Required cooling temperature is unavailable."
    elif target is None:
        status = "no_target"
        advice = "Set a cooling target temperature."
    elif state in {"CHILLING", "TRANSFER"}:
        if method == METHOD_COUNTERFLOW and pump_state != "on":
            status = "wort_pump_required"
            advice = "Start wort circulation through the CFC."
        elif target_ready:
            status = "transfer_ready" if state == "TRANSFER" else "on_target"
            advice = "Wort temperature is within the target range."
        elif delta is not None and delta < -READY_TOLERANCE_C:
            status = "below_target"
            advice = "Wort is below target temperature. Reduce or stop cooling."
        elif delta is not None and delta <= 2.0:
            status = "approaching_target"
            advice = "Approaching target. Monitor cooling to avoid overshoot."
        elif rate is not None and rate > MIN_MEANINGFUL_RATE_C_PER_H:
            status = "cooling"
            advice = "Cooling is active."
        else:
            status = "cooling_needed"
            advice = "Cooling is required; waiting for a meaningful temperature trend."
    else:
        status = "ready" if state == "READY" else state.lower()
        advice = "Cooling equipment ready." if state == "READY" else "Monitor cooling state."

    summary_parts = [status.replace("_", " ").title()]
    if process_temp is not None:
        summary_parts.append(f"{float(process_temp):.1f} °C")
    if target is not None:
        summary_parts.append(f"target {float(target):.0f} °C")
    if rate is not None:
        summary_parts.append(f"{rate:.1f} °C/h")
    if eta_minutes is not None:
        summary_parts.append(f"ETA {eta_minutes:.0f} min")

    return {
        **runtime,
        "status": status,
        "advice": advice,
        "summary": " · ".join(summary_parts),
        "delta": delta,
        "cooling_rate_c_per_h": rate,
        "eta_minutes": eta_minutes,
        "target_ready": target_ready,
        "pitch_ready": target_ready,
        "previous_sample_temperature": previous.temperature if previous is not None else None,
        "previous_sample_timestamp": previous.timestamp.isoformat() if previous is not None else None,
        "latest_sample_temperature": latest.temperature if latest is not None else None,
        "latest_sample_timestamp": latest.timestamp.isoformat() if latest is not None else None,
    }


def cooling_attrs(snapshot: dict[str, Any]) -> dict[str, Any]:
    return dict(snapshot)
