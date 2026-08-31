"""Pure decision model for the BrewAssistant kegerator circulation fan."""

from __future__ import annotations

from dataclasses import dataclass

MODE_OFF = "Off"
MODE_COOLING_ONLY = "Cooling only"
MODE_AFTERRUN = "Afterrun"
MODE_SMART_AUTO = "Smart auto"
MODE_ALWAYS_ON = "Always on"

FAN_MODE_OPTIONS = [
    MODE_OFF,
    MODE_COOLING_ONLY,
    MODE_AFTERRUN,
    MODE_SMART_AUTO,
    MODE_ALWAYS_ON,
]
DEFAULT_FAN_MODE = MODE_SMART_AUTO
AFTERRUN_MODES = {MODE_AFTERRUN, MODE_SMART_AUTO}

TOO_WARM_C = 0.8
TOO_COLD_C = -0.8
WARMING_C_H = 0.20
SMART_STOP_DELTA_C = 0.25
SMART_STOP_TREND_C_H = 0.05
MAX_REASONABLE_WARMING_C_H = 5.0


@dataclass(slots=True)
class FanInputs:
    compressor_active: bool
    fan_running: bool
    fan_switch_ok: bool
    power_sensor_ok: bool
    temperature_sensor_ok: bool
    temperature_context_available: bool
    climate_conflict: bool
    hvac_action: str | None
    temperature_delta: float | None
    trend_c_per_hour: float | None


@dataclass(slots=True)
class FanDemand:
    too_warm: bool
    too_cold: bool
    cooling_requested: bool
    warming_fast: bool
    hysteresis_run: bool
    diagnostic_reason: str


@dataclass(slots=True)
class FanDecision:
    enabled: bool
    state: str
    reason: str
    desired_switch_state: str
    should_run: bool
    action: str
    command: str | None
    action_needed: bool
    warning_level: str
    demand: FanDemand


def build_demand(inputs: FanInputs) -> FanDemand:
    """Build temperature/trend circulation demand."""
    too_warm = inputs.temperature_delta is not None and inputs.temperature_delta >= TOO_WARM_C
    too_cold = inputs.temperature_delta is not None and inputs.temperature_delta <= TOO_COLD_C
    cooling_requested = inputs.hvac_action == "cooling"
    warming_fast = (
        inputs.trend_c_per_hour is not None
        and WARMING_C_H <= inputs.trend_c_per_hour <= MAX_REASONABLE_WARMING_C_H
    )
    hysteresis_run = inputs.fan_running and (
        (inputs.temperature_delta is not None and inputs.temperature_delta > SMART_STOP_DELTA_C)
        or (
            inputs.trend_c_per_hour is not None
            and SMART_STOP_TREND_C_H < inputs.trend_c_per_hour <= MAX_REASONABLE_WARMING_C_H
        )
    )

    if inputs.climate_conflict:
        reason = "climate_conflict"
    elif too_cold:
        reason = "too_cold"
    elif cooling_requested:
        reason = "cooling_requested"
    elif too_warm:
        reason = "too_warm"
    elif warming_fast:
        reason = "warming_fast"
    elif hysteresis_run:
        reason = "hysteresis_run"
    elif not inputs.temperature_context_available:
        reason = "temperature_context_unavailable"
    else:
        reason = "stable"

    return FanDemand(
        too_warm=too_warm,
        too_cold=too_cold,
        cooling_requested=cooling_requested,
        warming_fast=warming_fast,
        hysteresis_run=hysteresis_run,
        diagnostic_reason=reason,
    )


def warning_level(inputs: FanInputs, *, enabled: bool, mode: str) -> str:
    """Return mode-aware backend warning severity."""
    if not enabled:
        return "ok"
    if not inputs.fan_switch_ok:
        return "sensor_issue"
    if mode in {MODE_COOLING_ONLY, MODE_AFTERRUN, MODE_SMART_AUTO} and not inputs.power_sensor_ok:
        return "sensor_issue"
    if mode == MODE_SMART_AUTO and not inputs.temperature_sensor_ok:
        return "sensor_issue"
    if inputs.climate_conflict:
        return "warning"
    if inputs.temperature_delta is not None and abs(inputs.temperature_delta) >= 2.0:
        return "warning"
    if (
        inputs.trend_c_per_hour is not None
        and 1.5 <= inputs.trend_c_per_hour <= MAX_REASONABLE_WARMING_C_H
    ):
        return "warning"
    return "ok"


def _smart_state(inputs: FanInputs, demand: FanDemand, afterrun_active: bool) -> tuple[str, str, bool]:
    if inputs.compressor_active:
        return "compressor_follow", "compressor_active", True
    if afterrun_active:
        return "afterrun", "afterrun", True
    if demand.cooling_requested:
        return "circulating", "smart_cooling_requested", True
    if not inputs.temperature_context_available:
        reason = "smart_climate_conflict" if inputs.climate_conflict else "smart_temperature_context_unavailable"
        return "standby", reason, False
    if demand.too_cold:
        return "standby", "smart_too_cold", False
    if demand.too_warm:
        return "circulating", "smart_too_warm", True
    if demand.warming_fast:
        return "circulating", "smart_warming_fast", True
    if demand.hysteresis_run:
        return "circulating", "smart_hysteresis", True
    return "standby", "smart_stable", False


def decide(*, enabled: bool, mode: str, inputs: FanInputs, afterrun_active: bool) -> FanDecision:
    """Return one deterministic fan decision without touching Home Assistant."""
    demand = build_demand(inputs)

    if not enabled:
        state, reason, should_run, desired = "disabled", "fan_auto_disabled", False, "unmanaged"
    elif not inputs.fan_switch_ok:
        state, reason, should_run, desired = "blocked", "missing_fan_switch", False, "unmanaged"
    elif mode == MODE_OFF:
        state, reason, should_run, desired = "standby", "mode_off", False, "off"
    elif mode == MODE_ALWAYS_ON:
        state, reason, should_run, desired = "always_on", "mode_always_on", True, "on"
    elif mode == MODE_COOLING_ONLY:
        should_run = inputs.compressor_active
        state = "compressor_follow" if should_run else "standby"
        reason = "compressor_active" if should_run else "compressor_idle"
        desired = "on" if should_run else "off"
    elif mode == MODE_AFTERRUN:
        if inputs.compressor_active:
            state, reason, should_run = "compressor_follow", "compressor_active", True
        elif afterrun_active:
            state, reason, should_run = "afterrun", "afterrun", True
        else:
            state, reason, should_run = "standby", "compressor_idle_afterrun_expired", False
        desired = "on" if should_run else "off"
    else:
        state, reason, should_run = _smart_state(inputs, demand, afterrun_active)
        desired = "on" if should_run else "off"

    action = "none"
    command = None
    if enabled and inputs.fan_switch_ok and desired in {"on", "off"}:
        if should_run and not inputs.fan_running:
            action, command = "turn_on_fan", "kegerator_fan_on"
        elif not should_run and inputs.fan_running:
            action, command = "turn_off_fan", "kegerator_fan_off"

    return FanDecision(
        enabled=enabled,
        state=state,
        reason=reason,
        desired_switch_state=desired,
        should_run=should_run,
        action=action,
        command=command,
        action_needed=action != "none",
        warning_level=warning_level(inputs, enabled=enabled, mode=mode),
        demand=demand,
    )
