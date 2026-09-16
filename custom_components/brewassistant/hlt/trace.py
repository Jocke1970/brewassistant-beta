"""Uploadable JSONL trace for the virtual HLT, independent of HA state attributes.

Only called by an HLT runtime; this module never switches physical hardware.
One file per brewday session, in the Home Assistant configuration directory.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
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
    """Hash the caller's session ID: stable across restarts; no path traversal."""
    if not session_id:
        raise ValueError("A nonempty brewday session ID is required")
    digest = sha256(session_id.encode("utf-8")).hexdigest()[:16]
    return Path(config_root) / "brewassistant" / "logs" / f"hlt-sim-{digest}.jsonl"


def _append_line(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(line + "\n")


class HLTTraceRecorder:
    """Keep a bounded-rate measurement stream and immediate transition records.

    Caller must supply a real brewday session ID and only invoke this from a
    simulation runtime. Logging cannot infer safe electrical authorization.
    """

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
        """Build a JSON-safe sample. Never mislabel model values as measured."""
        now_s = _number(inputs.timestamp_s)
        if now_s is None or now_s < 0:
            raise ValueError("Invalid HLT sample timestamp")
        transitions = list(result.events)
        fingerprint = (result.state, result.reason, result.virtual_heater_on,
                       result.temperature_source, result.power_budget_verified,
                       inputs.sparge_required, inputs.enable_hlt)
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
            "hlt_temp_resolved_c": _number(result.temperature_c),
            "hlt_temp_estimated_c": (_number(result.temperature_c)
                                     if result.temperature_source != "measured" else None),
            "hlt_temp_source": result.temperature_source,
            "hlt_temp_uncertainty": result.temperature_uncertainty,
            "hlt_target_c": _number(hlt_target_c),
            "hlt_volume_l": _number(hlt_volume_l),
            "hlt_thermostat_heating": inputs.thermostat_heating,
            "hlt_thermostat_calibrated": result.thermostat_calibrated,
            "bz_power_observed_w": _number(inputs.brewzilla_measured_w),
            "bz_utilization_observed_pct": _number(inputs.brewzilla_requested_utilization),
            "bz_unconstrained": inputs.brewzilla_unconstrained,
            "bz_request_calculated_w": _number(result.brewzilla_request_w),
            "bz_would_grant_w": _number(result.brewzilla_would_grant_w),
            "bz_would_cap_pct": _number(result.brewzilla_would_cap_utilization),
            "hlt_reserved_w": _number(result.hlt_reservation_w),
            "total_reserved_w": _number(result.total_reserved_w),
            "available_w": _number(result.available_w),
            "usable_budget_w": _number(usable_budget_w),
            "power_budget_verified": result.power_budget_verified,
        }

    async def async_record(self, hass: Any, inputs: Any, result: Any, **context: Any) -> Path | None:
        """Serialize concurrent calls; offload file I/O from HA's event loop."""
        async with self._lock:
            record = self.make_record(inputs, result, **context)
            if record is None:
                return None
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
