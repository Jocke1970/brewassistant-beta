"""Read HA state into the HLT simulator; this adapter never calls a service.

Power is interpreted as current consumption, not a free-capacity authorization.
The optional HLT temperature sensor is informational/calibration input, and
must be fresh before use; falling back to the thermal model is explicit.
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


def _fresh(hass, entity_id: str | None, now: datetime, age_s: float):
    if not entity_id:
        return None
    state = hass.states.get(entity_id)
    if state is None or state.state in ("unknown", "unavailable", "none", ""):
        return None
    if (now - state.last_updated).total_seconds() > age_s:
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
    """Collect fresh HA readings; unknown states remain None (never zero)."""
    now = now or datetime.now(timezone.utc)
    bz_power = _float(_fresh(hass, config.brewzilla_power, now, config.max_age_s))
    bz_util = _float(_fresh(hass, config.brewzilla_utilization, now, config.max_age_s))
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
