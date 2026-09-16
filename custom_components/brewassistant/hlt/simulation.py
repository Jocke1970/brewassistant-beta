"""Pure HLT / BrewZilla power-sharing simulator. NEVER writes Home Assistant entities.

All values are explicit inputs so a recorded Brewday can be replayed deterministically.
A real controller must additionally enforce grants in BrewZilla's physical write chain;
this simulator only reports what it *would* do.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

WATER_J_PER_L_K = 4186.0


@dataclass(frozen=True)
class SimulationConfig:
    usable_budget_w: float = 2500.0
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
    """A single sample; None signifies missing/stale data, not zero demand."""
    timestamp_s: float
    brewzilla_requested_utilization: float | None
    brewzilla_measured_w: float | None
    sparge_required: bool = True
    enable_hlt: bool = True
    measured_hlt_temperature_c: float | None = None
    thermostat_heating: bool | None = None
    # True means the actual BZ heat channel may be changed externally without an
    # arbiter-enforced cap. Simulation cannot promise physical budget enforcement.
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
    brewzilla_would_grant_w: float | None
    brewzilla_would_cap_utilization: float | None
    total_reserved_w: float
    available_w: float
    thermostat_calibrated: bool
    power_budget_verified: bool
    events: tuple[str, ...]


class HLTSimulator:
    """Stateful, replayable simulation of a BZ-priority, binary-heater HLT.

    Release uses a virtual off-confirmation interval. A future hardware adapter
    must replace this with trusted readback and never treat the simulation timer
    as proof that a real heater is off.
    """

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
        # Model energy consumed during the *previous* interval, not the newly
        # requested heater state; integrate with bounded steps for cooling losses.
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
            uncertainty = "sensor accuracy / freshness must be checked by adapter"
        else:
            temp_source = "estimated"
            uncertainty = "model-dependent; starting temperature must be configured"
        # Thermostat edge is useful only if cutoff temperature is independently
        # configured AND an actual heating->off transition has been observed.
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
        measured_w = sample.brewzilla_measured_w
        valid_request = utilization is not None and isfinite(utilization) and 0 <= utilization <= 100
        valid_measurement = measured_w is not None and isfinite(measured_w) and measured_w >= 0
        requested_w = c.brewzilla_idle_w + c.brewzilla_heater_w * utilization / 100 if valid_request else None
        # Never use low instantaneous consumption as permission to start HLT.
        # High measurement, however, raises reservation to avoid optimistic grants.
        conservative_w = max(requested_w, measured_w) if valid_request and valid_measurement else None
        budget_verified = not sample.brewzilla_unconstrained
        if sample.brewzilla_unconstrained and valid_request and valid_measurement:
            # A non-arbitrated BZ can jump to full rated power: reserve full load.
            conservative_w = max(conservative_w, c.brewzilla_idle_w + c.brewzilla_heater_w)
        if not valid_request or not valid_measurement:
            conservative_w = None

        pending_release = self.release_until_s is not None and t < self.release_until_s
        if self.release_until_s is not None and t >= self.release_until_s:
            self.release_until_s = None
            events.append("virtual_hlt_off_confirmed")
            pending_release = False
        wants_heat = sample.sparge_required and sample.enable_hlt and self.temperature_c < c.hlt_target_c
        can_grant = (conservative_w is not None and
                     conservative_w + c.hlt_heater_w <= c.usable_budget_w)
        if pending_release:
            self.virtual_heater_on = False
            self.state, reason = "YIELDING", "awaiting_virtual_off_confirmation"
        elif self.virtual_heater_on and (not wants_heat or not can_grant):
            self.virtual_heater_on = False
            self.release_until_s = t + c.off_confirmation_s
            self.state = "YIELDING" if c.off_confirmation_s > 0 else "WAITING_FOR_POWER"
            reason = "brewzilla_reclaim" if wants_heat else "heater_stop"
            events.append("virtual_hlt_off_requested")
            if not c.off_confirmation_s:
                self.release_until_s = None
                events.append("virtual_hlt_off_confirmed")
        elif not sample.enable_hlt or not sample.sparge_required:
            self.state, reason = "IDLE", "disabled_or_no_sparge"
        elif not valid_request or not valid_measurement:
            self.state, reason = "WAITING_FOR_POWER", "brewzilla_power_or_request_unknown"
        elif not wants_heat:
            self.state, reason = "READY", "target_reached_estimated" if temp_source != "measured" else "target_reached_measured"
        elif can_grant:
            if not self.virtual_heater_on:
                events.append("virtual_hlt_on")
            self.virtual_heater_on = True
            self.state, reason = "HEATING", "shared_budget_granted"
        else:
            self.state, reason = "WAITING_FOR_POWER", "not_enough_reserved_capacity"
        hlt_reservation = c.hlt_heater_w if self.virtual_heater_on or self.release_until_s is not None else 0.0
        if conservative_w is None:
            bz_grant = None
            bz_cap = None
            bz_reservation = c.usable_budget_w  # unknown BZ demand blocks all new HLT grants
        else:
            bz_grant = min(conservative_w, max(0.0, c.usable_budget_w - hlt_reservation))
            bz_cap = min(100.0, max(0.0, (bz_grant - c.brewzilla_idle_w) / c.brewzilla_heater_w * 100))
            bz_reservation = bz_grant
        total = bz_reservation + hlt_reservation
        if total > c.usable_budget_w + 1e-6:
            # Unknown demand while a previous HLT reservation is releasing:
            # preserve the reservation and flag unavailable rather than lying.
            events.append("simulation_budget_conflict")
            budget_verified = False
        return Result(self.state, reason, self.temperature_c, temp_source, uncertainty,
                      self.virtual_heater_on, hlt_reservation, requested_w, bz_grant,
                      bz_cap, total, max(0.0, c.usable_budget_w - total), self.calibrated,
                      budget_verified, tuple(events))
