"""Simulation-only HLT load shedding with UNRESTRICTED BrewZilla priority.

Never writes Home Assistant or caps the BrewZilla heater. Current draw is useful
for replay, but not advance assurance: a thermostat can energize BZ between HA
polls. An actual shared-circuit installation needs independent load-shed/interlock
and verified HLT OFF feedback before physical HLT control is enabled.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

WATER_J_PER_L_K = 4186.0


@dataclass(frozen=True)
class SimulationConfig:
    usable_budget_w: float = 2500.0  # scenario only; never a certified circuit limit
    hlt_heater_w: float = 1800.0
    brewzilla_heater_w: float = 2200.0
    brewzilla_idle_w: float = 0.0
    hlt_volume_l: float = 12.0
    hlt_start_c: float = 18.0
    hlt_target_c: float = 78.0
    thermostat_cutoff_c: float | None = None
    efficiency: float = 0.9
    loss_w_per_k: float = 0.0
    ambient_c: float = 20.0
    off_confirmation_s: float = 3.0
    max_step_s: float = 60.0
    power_tolerance_w: float = 100.0

    def __post_init__(self) -> None:
        numeric = (self.usable_budget_w, self.hlt_heater_w, self.brewzilla_heater_w,
                   self.brewzilla_idle_w, self.hlt_volume_l, self.hlt_start_c,
                   self.hlt_target_c, self.efficiency, self.loss_w_per_k,
                   self.ambient_c, self.off_confirmation_s, self.max_step_s,
                   self.power_tolerance_w)
        if any(not isfinite(x) for x in numeric):
            raise ValueError("All HLT simulation inputs must be finite")
        if not (0 < self.hlt_volume_l and 0 < self.hlt_heater_w and 0 < self.brewzilla_heater_w
                and 0 < self.usable_budget_w and 0 < self.efficiency <= 1
                and self.brewzilla_idle_w >= 0 and self.loss_w_per_k >= 0
                and self.off_confirmation_s >= 0 and self.max_step_s > 0
                and self.power_tolerance_w >= 0):
            raise ValueError("Invalid HLT power, water volume, or model constants")
        if self.thermostat_cutoff_c is not None and not isfinite(self.thermostat_cutoff_c):
            raise ValueError("Thermostat cutoff must be finite")


@dataclass(frozen=True)
class Inputs:
    """Fresh sample; missing measurements are None, never assumed to be zero."""
    timestamp_s: float
    brewzilla_requested_utilization: float | None
    brewzilla_measured_w: float | None
    sparge_required: bool = True
    enable_hlt: bool = True
    measured_hlt_temperature_c: float | None = None
    thermostat_heating: bool | None = None
    # Explicit higher-level runtime observation, NOT inferred from one low W sample.
    brewzilla_cruising: bool = False
    brewzilla_ramp_requested: bool = False
    # Legacy compatibility only; never authorizes a BZ cap or physical power grant.
    brewzilla_unconstrained: bool = True


@dataclass(frozen=True)
class Result:
    state: str
    reason: str
    temperature_c: float
    temperature_source: str
    temperature_uncertainty: str
    virtual_heater_on: bool
    hlt_reservation_w: float
    brewzilla_request_w: float | None
    brewzilla_would_grant_w: float | None  # always None: BZ is never allocated/capped
    brewzilla_would_cap_utilization: float | None  # always None
    total_reserved_w: float  # observed BZ + virtual HLT; not a safe power reservation
    available_w: float
    thermostat_calibrated: bool
    power_budget_verified: bool  # always False until independent protection exists
    events: tuple[str, ...]


class HLTSimulator:
    """Replay HLT opportunistic heating. BZ ALWAYS keeps its full physical power."""

    def __init__(self, config: SimulationConfig) -> None:
        self.config = config
        self.temperature_c = config.hlt_start_c
        self.last_timestamp_s: float | None = None
        self.virtual_heater_on = False
        self.release_until_s: float | None = None
        self.calibrated = False
        self.last_thermostat_heating: bool | None = None
        self.state = "IDLE"

    def tick(self, sample: Inputs) -> Result:
        c = self.config
        t = sample.timestamp_s
        if not isfinite(t) or (self.last_timestamp_s is not None and t < self.last_timestamp_s):
            raise ValueError("Simulation timestamps must increase monotonically")
        elapsed = 0.0 if self.last_timestamp_s is None else t - self.last_timestamp_s
        if elapsed > 86400:
            raise ValueError("Unexpected sample gap; restart simulation rather than replay stale grants")
        events: list[str] = []
        remaining = elapsed
        while remaining > 0:
            dt = min(c.max_step_s, remaining)
            heat_w = c.hlt_heater_w * c.efficiency if self.virtual_heater_on else 0.0
            loss_w = c.loss_w_per_k * (self.temperature_c - c.ambient_c)
            self.temperature_c += (heat_w - loss_w) * dt / (c.hlt_volume_l * WATER_J_PER_L_K)
            remaining -= dt
        self.last_timestamp_s = t
        if sample.measured_hlt_temperature_c is not None:
            if not isfinite(sample.measured_hlt_temperature_c):
                raise ValueError("Invalid HLT temperature")
            self.temperature_c = sample.measured_hlt_temperature_c
            temp_source = "measured"
            uncertainty = "sensor accuracy / freshness checked by adapter"
        else:
            temp_source = "estimated"
            uncertainty = "model-dependent; assumed starting temperature and losses"
        if (sample.measured_hlt_temperature_c is None and
                self.last_thermostat_heating is True and sample.thermostat_heating is False and
                c.thermostat_cutoff_c is not None):
            self.temperature_c = c.thermostat_cutoff_c
            self.calibrated = True
            temp_source = "thermostat_calibrated_estimate"
            uncertainty = "cutoff calibration only; hysteresis/stratification unknown"
            events.append("thermostat_cutoff_calibration")
        self.last_thermostat_heating = sample.thermostat_heating

        utilization = sample.brewzilla_requested_utilization
        measured = sample.brewzilla_measured_w
        valid_request = utilization is not None and isfinite(utilization) and 0 <= utilization <= 100
        valid_measurement = measured is not None and isfinite(measured) and measured >= 0
        requested_w = c.brewzilla_idle_w + c.brewzilla_heater_w * utilization / 100 if valid_request else None
        wants_heat = sample.sparge_required and sample.enable_hlt and self.temperature_c < c.hlt_target_c
        # Snapshot-based OPPORTUNITY only. Neither this calculation nor cruise
        # detection prevents BZ autonomously energizing before the next sample.
        opportunity = (valid_request and valid_measurement and sample.brewzilla_cruising
                       and not sample.brewzilla_ramp_requested
                       and measured + c.hlt_heater_w <= c.usable_budget_w)

        pending_release = self.release_until_s is not None and t < self.release_until_s
        if self.release_until_s is not None and t >= self.release_until_s:
            self.release_until_s = None
            events.append("virtual_hlt_off_confirmed")
            pending_release = False
        if pending_release:
            self.virtual_heater_on = False
            self.state, reason = "YIELDING", "awaiting_virtual_off_confirmation"
        elif self.virtual_heater_on and (not wants_heat or not opportunity):
            self.virtual_heater_on = False
            self.release_until_s = t + c.off_confirmation_s
            self.state = "YIELDING" if c.off_confirmation_s > 0 else "WAITING_FOR_POWER"
            reason = ("brewzilla_ramp_priority" if sample.brewzilla_ramp_requested or not sample.brewzilla_cruising
                      else "brewzilla_power_priority" if wants_heat else "heater_stop")
            events.append("virtual_hlt_off_requested")
            if not c.off_confirmation_s:
                self.release_until_s = None
                events.append("virtual_hlt_off_confirmed")
        elif not sample.enable_hlt or not sample.sparge_required:
            self.state, reason = "IDLE", "disabled_or_no_sparge"
        elif not valid_request or not valid_measurement:
            self.state, reason = "WAITING_FOR_POWER", "brewzilla_power_or_request_unknown"
        elif not wants_heat:
            self.state, reason = "READY", "target_reached_measured" if temp_source == "measured" else "target_reached_estimated"
        elif sample.brewzilla_ramp_requested or not sample.brewzilla_cruising:
            self.state, reason = "WAITING_FOR_POWER", "brewzilla_ramp_or_not_cruising"
        elif opportunity:
            if not self.virtual_heater_on:
                events.append("virtual_hlt_on")
            self.virtual_heater_on = True
            self.state, reason = "HEATING", "cruise_power_opportunity_simulated"
        else:
            self.state, reason = "WAITING_FOR_POWER", "not_enough_observed_capacity"

        hlt_reserved = c.hlt_heater_w if self.virtual_heater_on or self.release_until_s is not None else 0.0
        # IMPORTANT: never clamp BZ load to budget-minus-HLT. Detect the real
        # observed overlap as a conflict instead. Unknown BZ load is not safe.
        bz_observed = measured if valid_measurement else c.usable_budget_w
        total = bz_observed + hlt_reserved
        if total > c.usable_budget_w + 1e-6:
            events.append("simulation_budget_conflict")
        return Result(self.state, reason, self.temperature_c, temp_source, uncertainty,
                      self.virtual_heater_on, hlt_reserved, requested_w, None, None,
                      total, max(0.0, c.usable_budget_w - total), self.calibrated,
                      False, tuple(events))
