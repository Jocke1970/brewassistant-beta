"""Uploadable JSONL trace for the virtual HLT, independent of HA state attributes.

Only called by simulation runtime; never switches physical hardware. One file
per Brewday session, in the Home Assistant configuration directory.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 2
SAMPLE_INTERVAL_S = 30.0
_DATA_KEY = "hlt_trace_recorder"


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return round(result, 4) if isfinite(result) else None


def _session_path(config_root: str | Path, session_id: str) -> Path:
    if not session_id:
        raise ValueError("A nonempty brewday session ID is required")
    digest = sha256(session_id.encode("utf-8")).hexdigest()[:16]
    return Path(config_root) / "brewassistant" / "logs" / f"hlt-sim-{digest}.jsonl"


def _append_line(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(line + "\n")


def _ha_diagnostics(hass: Any, sample_s: float) -> dict[str, Any]:
    """Read published HA states for diagnosis only, NEVER for power permission.

    Values are labelled HA-published because coordinator sensors can lag the
    simulator's direct runtime snapshot. An old or unavailable measurement is
    preserved as evidence with its age, not treated as zero or as fresh.
    """
    states = getattr(hass, "states", None)

    def read(entity_id: str) -> tuple[str | None, float | None]:
        state = states.get(entity_id) if states is not None else None
        if state is None:
            return None, None
        value = str(state.state)
        updated = getattr(state, "last_updated", None)
        age_s = None
        if isinstance(updated, datetime):
            if updated.tzinfo is not None:
                age_s = _number(sample_s - updated.timestamp())
            if age_s is not None and age_s < 0:
                age_s = None
        return value, age_s

    temperature, temperature_age = read("sensor.brewzilla_temperature")
    device_target, device_target_age = read("number.brewzilla_target_temperature")
    brewday_target, brewday_target_age = read("sensor.brewassistant_brewday_target_temperature")
    virtual_recipient, virtual_recipient_age = read("sensor.brewassistant_hlt_virtual_energy_recipient")
    return {
        "bz_temperature_ha_c": _number(temperature),
        "bz_temperature_ha_age_s": temperature_age,
        "bz_device_target_ha_c": _number(device_target),
        "bz_device_target_ha_age_s": device_target_age,
        "bz_brewday_target_ha_c": _number(brewday_target),
        "bz_brewday_target_ha_age_s": brewday_target_age,
        "hlt_virtual_recipient_ha_state": virtual_recipient,
        "hlt_virtual_recipient_ha_age_s": virtual_recipient_age,
    }


class HLTTraceRecorder:
    """Rate-limited samples, immediate transitions; BZ grants do not exist."""

    def __init__(self, config_root: str | Path, session_id: str,
                 *, sample_interval_s: float = SAMPLE_INTERVAL_S) -> None:
        if not isfinite(sample_interval_s) or sample_interval_s <= 0:
            raise ValueError("Sample interval must be positive and finite")
        self.path = _session_path(config_root, session_id)
        self.session_key = sha256(session_id.encode("utf-8")).hexdigest()[:16]
        self.sample_interval_s = sample_interval_s
        self._last_sample_s: float | None = None
        self._last_fingerprint: tuple[Any, ...] | None = None
        self._lock = asyncio.Lock()

    def make_record(self, inputs: Any, result: Any, *,
                    hlt_power_w: float | None = None,
                    hlt_switch: str | None = None,
                    stage: str | None = None,
                    step: str | None = None,
                    usable_budget_w: float | None = None,
                    hlt_target_c: float | None = None,
                    hlt_volume_l: float | None = None) -> dict[str, Any] | None:
        now_s = _number(inputs.timestamp_s)
        if now_s is None or now_s < 0:
            raise ValueError("Invalid HLT sample timestamp")
        transitions = list(result.events)
        cruising = bool(getattr(inputs, "brewzilla_cruising", False))
        ramp = bool(getattr(inputs, "brewzilla_ramp_requested", False))
        fingerprint = (result.state, result.reason, result.virtual_heater_on,
                       result.temperature_source, result.power_budget_verified,
                       inputs.sparge_required, inputs.enable_hlt, cruising, ramp)
        state_changed = fingerprint != self._last_fingerprint
        due = (self._last_sample_s is None or now_s < self._last_sample_s
               or now_s - self._last_sample_s >= self.sample_interval_s)
        if not transitions and not state_changed and not due:
            return None
        self._last_sample_s = now_s
        self._last_fingerprint = fingerprint
        return {
            "schema_version": SCHEMA_VERSION,
            "record_type": "transition" if transitions or state_changed else "sample",
            "timestamp_utc": datetime.fromtimestamp(now_s, tz=timezone.utc).isoformat(),
            "session_key": self.session_key,
            "simulation": True,
            "physical_writes": False,
            "brewzilla_priority": "absolute_unthrottled",
            "stage": stage,
            "step": step,
            "events": transitions,
            "hlt_state": result.state,
            "hlt_reason": result.reason,
            "hlt_sparge_required": inputs.sparge_required,
            "hlt_enabled": inputs.enable_hlt,
            "hlt_virtual_heater_on": result.virtual_heater_on,
            "hlt_switch_observed": hlt_switch,
            "hlt_power_observed_w": _number(hlt_power_w),
            "hlt_temp_measured_c": _number(inputs.measured_hlt_temperature_c),
            "hlt_temp_model_c": _number(result.temperature_c),
            "hlt_temp_source": result.temperature_source,
            "hlt_temp_uncertainty": result.temperature_uncertainty,
            "hlt_target_c": _number(hlt_target_c),
            "hlt_volume_l": _number(hlt_volume_l),
            "hlt_thermostat_heating": inputs.thermostat_heating,
            "hlt_thermostat_calibrated": result.thermostat_calibrated,
            "bz_power_observed_w": _number(inputs.brewzilla_measured_w),
            "bz_utilization_observed_pct": _number(inputs.brewzilla_requested_utilization),
            "bz_cruising_observed": cruising,
            "bz_ramp_requested": ramp,
            "bz_request_calculated_w": _number(result.brewzilla_request_w),
            "bz_power_cap_w": None,
            "bz_power_cap_pct": None,
            "hlt_reserved_w": _number(result.hlt_reservation_w),
            "total_observed_bz_plus_virtual_hlt_w": _number(result.total_reserved_w),
            "available_observed_w": _number(result.available_w),
            "usable_budget_w": _number(usable_budget_w),
            "power_budget_verified": False,
        }

    async def async_record(self, hass: Any, inputs: Any, result: Any, **context: Any) -> Path | None:
        async with self._lock:
            record = self.make_record(inputs, result, **context)
            if record is None:
                return None
            record.update(_ha_diagnostics(hass, inputs.timestamp_s))
            line = json.dumps(record, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
            await hass.async_add_executor_job(_append_line, self.path, line)
            return self.path


async def async_record_hlt_trace(hass: Any, session_id: str, inputs: Any,
                                 result: Any, **context: Any) -> Path | None:
    """HA entry point. Session rotation follows the Brewday recorder session."""
    data = hass.data.setdefault("brewassistant", {})
    recorder = data.get(_DATA_KEY)
    target_path = _session_path(hass.config.path(), session_id)
    if not isinstance(recorder, HLTTraceRecorder) or recorder.path != target_path:
        recorder = HLTTraceRecorder(hass.config.path(), session_id)
        data[_DATA_KEY] = recorder
    return await recorder.async_record(hass, inputs, result, **context)
