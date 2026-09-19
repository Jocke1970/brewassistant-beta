"""Read HA state into the HLT simulator; this adapter never calls a service.

Power is current consumption, not free-capacity authorization. A continuously
held BZ utilization setting does not get a fresh last_updated timestamp: do not
mistake an unchanged number for a lost signal. Physical measurements and HLT
switch readback still require fresh data. This is simulation ONLY.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite

from .simulation import Inputs


@dataclass(frozen=True)
class EntityConfig:
    brewzilla_power: str = "sensor.brewzilla_power"
    brewzilla_utilization: str = "number.brewzilla_heat_utilization"
    hlt_switch: str = "switch.sparge_heater"
    hlt_power: str = "sensor.sparge_heater_power"
    hlt_temperature: str | None = None
    max_age_s: float = 180.0
    heater_active_threshold_w: float = 20.0


def _fresh(hass, entity_id: str | None, now: datetime, age_s: float,
           *, allow_unchanged: bool = False):
    """Read a valid HA state; require recent updates only for observations.

    An unchanged setpoint/utilization may be older than age_s while remaining
    valid in HA. Unknown/unavailable/missing is rejected in either mode.
    `allow_unchanged` MUST NOT be used for wattmeters, probes or OFF readback.
    """
    if not entity_id:
        return None
    state = hass.states.get(entity_id)
    if state is None or str(state.state).lower() in {"unknown", "unavailable", "none", ""}:
        return None
    if not allow_unchanged:
        age = (now - state.last_updated).total_seconds()
        if not 0 <= age <= age_s:
            return None
    return state


def _float(state):
    if state is None:
        return None
    try:
        value = float(state.state)
        return value if isfinite(value) else None
    except (ValueError, TypeError):
        return None


def collect_inputs(hass, config: EntityConfig, *, sparge_required: bool,
                   enabled: bool, brewzilla_unconstrained: bool = True,
                   now: datetime | None = None) -> Inputs:
    """Collect read-only HA inputs; missing data stays None, never zero."""
    now = now or datetime.now(timezone.utc)
    bz_power = _float(_fresh(hass, config.brewzilla_power, now, config.max_age_s))
    # Utilization is a held setting, not a periodically sampled measurement.
    # The simulator still requires fresh BZ watts and fresh temperature evidence
    # before declaring a virtual cruise opportunity.
    bz_util = _float(_fresh(hass, config.brewzilla_utilization, now,
                            config.max_age_s, allow_unchanged=True))
    hlt_temp = _float(_fresh(hass, config.hlt_temperature, now, config.max_age_s))
    switch = _fresh(hass, config.hlt_switch, now, config.max_age_s)
    hlt_power = _float(_fresh(hass, config.hlt_power, now, config.max_age_s))
    # ON switch plus low watts indicates thermostat has opened; OFF switch
    # is *not* thermostat cutoff and must never calibrate the temperature.
    thermostat_heating = None
    if switch is not None and switch.state == "on" and hlt_power is not None:
        thermostat_heating = hlt_power >= config.heater_active_threshold_w
    return Inputs(timestamp_s=now.timestamp(),
                  brewzilla_requested_utilization=bz_util,
                  brewzilla_measured_w=bz_power,
                  sparge_required=sparge_required, enable_hlt=enabled,
                  measured_hlt_temperature_c=hlt_temp,
                  thermostat_heating=thermostat_heating,
                  brewzilla_unconstrained=brewzilla_unconstrained)
