"""UI-ready HLT telemetry. Measurements and counterfactual values NEVER mix.

These counters are sample-derived estimates, not energy-meter readings. No
physical switching, HA imports or safety decisions are implemented here.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any

MAX_SAMPLE_GAP_S = 90.0
HEATING_THRESHOLD_W = 20.0


def _w(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (ValueError, TypeError):
        return None
    return number if isfinite(number) and number >= 0 else None


def _rounded(value: float | None, digits: int = 2) -> float | None:
    return round(value, digits) if value is not None else None


@dataclass
class HLTMetrics:
    """One instance per Audit session; caller replaces it on session rollover.

    Timestamps use UTC epoch seconds. Gaps >90 s are unknown for accumulation;
    elapsed wall-clock time still includes them, and unknown time is exposed.
    Observed heating needs BOTH valid wattmeter and switch=on at both ends.
    Energy in Wh is an approximation from consecutive instantaneous samples.
    """

    session_id: str
    started_s: float | None = None
    last_s: float | None = None
    last_virtual_on: bool = False
    last_real_heating: bool | None = None
    last_bz_power_w: float | None = None
    last_hlt_power_w: float | None = None
    last_state: str | None = None
    virtual_heating_s: float = 0.0
    observed_heating_estimate_s: float = 0.0
    waiting_s: float = 0.0
    yielding_s: float = 0.0
    unknown_sample_s: float = 0.0
    bz_energy_estimate_wh: float = 0.0
    hlt_energy_estimate_wh: float = 0.0
    yield_count: int = 0
    reclaim_count: int = 0

    def update(self, inputs: Any, result: Any, *, hlt_power_w: Any = None,
               hlt_switch: str | None = None, usable_budget_w: Any = None,
               hlt_target_c: Any = None, hlt_volume_l: Any = None,
               trace_path: str | None = None) -> dict[str, Any]:
        now_s = float(inputs.timestamp_s)
        if not isfinite(now_s) or now_s < 0 or (self.last_s is not None and now_s < self.last_s):
            raise ValueError("HLT metrics require monotonic finite timestamps")
        active = bool(inputs.sparge_required and inputs.enable_hlt)
        if self.started_s is None and active:
            self.started_s = now_s
        bz_w = _w(inputs.brewzilla_measured_w)
        hlt_w = _w(hlt_power_w)
        switch = str(hlt_switch).lower() if hlt_switch is not None else None
        # Watts alone describe observed draw; the switch readback must be ON
        # before we count observed *heating* time.
        real_heating = (hlt_w >= HEATING_THRESHOLD_W and switch == "on") if hlt_w is not None and switch in {"on", "off"} else None
        dt = 0 if self.last_s is None else now_s - self.last_s
        if dt > MAX_SAMPLE_GAP_S:
            self.unknown_sample_s += dt
        elif dt > 0:
            if self.last_virtual_on:
                self.virtual_heating_s += dt  # prior virtual state held over sample interval
            if self.last_state == "WAITING_FOR_POWER":
                self.waiting_s += dt
            if self.last_state == "YIELDING":
                self.yielding_s += dt
            if self.last_real_heating is True and real_heating is True:
                self.observed_heating_estimate_s += dt
            if bz_w is not None and self.last_bz_power_w is not None:
                self.bz_energy_estimate_wh += (self.last_bz_power_w + bz_w) / 2 * dt / 3600
            if hlt_w is not None and self.last_hlt_power_w is not None:
                self.hlt_energy_estimate_wh += (self.last_hlt_power_w + hlt_w) / 2 * dt / 3600
        transitions = tuple(result.events)
        if "virtual_hlt_off_requested" in transitions:
            self.yield_count += 1
            if str(result.reason).startswith("brewzilla_"):
                self.reclaim_count += 1
        self.last_s = now_s
        self.last_virtual_on = bool(result.virtual_heater_on)
        self.last_real_heating = real_heating
        self.last_bz_power_w = bz_w
        self.last_hlt_power_w = hlt_w
        self.last_state = str(result.state)

        virtual_w = _w(getattr(result, "hlt_reservation_w", None)) if result.virtual_heater_on else 0.0
        # Release reservations are NOT real or simulated active watt draw.
        virtual_w = virtual_w or 0.0
        actual_total = bz_w + hlt_w if bz_w is not None and hlt_w is not None else None
        scenario_total = bz_w + virtual_w if bz_w is not None else None
        budget = _w(usable_budget_w)
        actual_headroom = budget - actual_total if budget is not None and actual_total is not None else None
        if bz_w is None or hlt_w is None:
            recipient = "unknown"
        elif bz_w >= HEATING_THRESHOLD_W and hlt_w >= HEATING_THRESHOLD_W:
            recipient = "brewzilla_and_hlt"
        elif bz_w >= HEATING_THRESHOLD_W:
            recipient = "brewzilla"
        elif hlt_w >= HEATING_THRESHOLD_W:
            recipient = "hlt"
        else:
            recipient = "neither"
        temp_source = str(result.temperature_source)
        measured_temp = inputs.measured_hlt_temperature_c if temp_source == "measured" else None
        model_temp = None if temp_source == "measured" else result.temperature_c
        total_s = now_s - self.started_s if self.started_s is not None else 0.0
        return {
            "status": str(result.state), "reason": str(result.reason),
            "session_id": self.session_id, "session_started_at_epoch": self.started_s,
            "updated_at_epoch": now_s, "simulation_only": True,
            "physical_control_enabled": False, "power_budget_verified": False,
            "power_priority": "brewzilla", "power_owner": "brewzilla_priority",
            "actual_energy_recipient": recipient,
            "virtual_energy_recipient": "hlt" if result.virtual_heater_on else "none",
            "bz_power_observed_w": _rounded(bz_w),
            "hlt_power_observed_w": _rounded(hlt_w),
            "hlt_power_virtual_w": _rounded(virtual_w),
            "actual_total_observed_w": _rounded(actual_total),
            "virtual_total_scenario_w": _rounded(scenario_total),
            "budget_scenario_w": _rounded(budget),
            "actual_headroom_observed_w": _rounded(actual_headroom),
            "hlt_virtual_heater_on": bool(result.virtual_heater_on),
            "hlt_switch_observed": switch,
            "hlt_temperature_c": _rounded(result.temperature_c),
            "hlt_temperature_measured_c": _rounded(_w(measured_temp)),
            "hlt_temperature_estimated_c": _rounded(_w(model_temp)),
            "hlt_temperature_source": temp_source,
            "hlt_temperature_uncertainty": str(result.temperature_uncertainty),
            "hlt_target_c": _rounded(_w(hlt_target_c)),
            "hlt_volume_l": _rounded(_w(hlt_volume_l)),
            "bz_cruising_observed": bool(getattr(inputs, "brewzilla_cruising", False)),
            "bz_ramp_requested": bool(getattr(inputs, "brewzilla_ramp_requested", False)),
            "total_session_seconds": round(total_s),
            "virtual_heating_seconds": round(self.virtual_heating_s),
            "observed_heating_estimate_seconds": round(self.observed_heating_estimate_s),
            "waiting_seconds": round(self.waiting_s),
            "yielding_seconds": round(self.yielding_s),
            "unknown_sample_seconds": round(self.unknown_sample_s),
            "bz_energy_estimate_wh": _rounded(self.bz_energy_estimate_wh),
            "hlt_energy_estimate_wh": _rounded(self.hlt_energy_estimate_wh),
            "yield_count": self.yield_count,
            "reclaim_count": self.reclaim_count,
            "trace_path": trace_path,
            "timing_quality": "sample_estimate_not_metered",
        }


def update_hlt_dashboard(hass: Any, session_id: str, inputs: Any, result: Any, **context: Any) -> dict[str, Any]:
    """Store an atomic UI snapshot without publishing live HA state ourselves."""
    data = hass.data.setdefault("brewassistant", {})
    metrics = data.get("hlt_metrics")
    if not isinstance(metrics, HLTMetrics) or metrics.session_id != session_id:
        metrics = HLTMetrics(session_id)
        data["hlt_metrics"] = metrics
    snapshot = metrics.update(inputs, result, **context)
    data["hlt_dashboard_snapshot"] = snapshot
    return snapshot


def build_hlt_dashboard_snapshot(hass: Any) -> dict[str, Any]:
    """Inactive status must not expose stale watts or a stale active state."""
    data = hass.data.get("brewassistant", {})
    saved = data.get("hlt_dashboard_snapshot")
    runtime = data.get("hlt_simulation_runtime", {})
    if not isinstance(saved, dict):
        return {"status": runtime.get("status", "waiting_for_data"), "power_priority": "brewzilla",
                "simulation_only": True, "physical_control_enabled": False, "power_budget_verified": False}
    snapshot = dict(saved)
    runtime_status = runtime.get("status")
    if runtime_status in {"waiting_for_brewday_recorder", "brewday_inactive_or_aborted", "waiting_for_sparge_volume", "error"}:
        snapshot["status"] = runtime_status
        snapshot["bz_power_observed_w"] = None
        snapshot["hlt_power_observed_w"] = None
        snapshot["hlt_power_virtual_w"] = None
        snapshot["actual_total_observed_w"] = None
        snapshot["virtual_total_scenario_w"] = None
        snapshot["actual_energy_recipient"] = "unknown"
        snapshot["virtual_energy_recipient"] = "none"
        snapshot["actual_headroom_observed_w"] = None
    return snapshot
