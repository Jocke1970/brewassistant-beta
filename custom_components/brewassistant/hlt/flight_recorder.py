"""Bridge simulated HLT transitions to Brewday Audit and uploadable JSONL.

The runtime calls this once after each simulator tick. No physical writes.
"""
from __future__ import annotations

from typing import Any

from .trace import async_record_hlt_trace

_EVENT_TYPES = {
    "virtual_hlt_on": "hlt_sim_heater_on",
    "virtual_hlt_off_requested": "hlt_sim_yield",
    "virtual_hlt_off_confirmed": "hlt_sim_release",
    "thermostat_cutoff_calibration": "hlt_sim_thermostat_cutoff",
    "simulation_budget_conflict": "hlt_sim_budget_conflict",
}


async def async_record_hlt_tick(
    hass: Any,
    *,
    session_id: str,
    inputs: Any,
    result: Any,
    hlt_power_w: float | None = None,
    hlt_switch: str | None = None,
    stage: str | None = None,
    step: str | None = None,
    usable_budget_w: float | None = None,
    hlt_target_c: float | None = None,
    hlt_volume_l: float | None = None,
) -> None:
    """Keep useful trace points in the file, only transitions in HA Audit."""
    from ..brewday import brewday_audit as audit

    path = await async_record_hlt_trace(
        hass, session_id, inputs, result,
        hlt_power_w=hlt_power_w, hlt_switch=hlt_switch,
        stage=stage, step=step, usable_budget_w=usable_budget_w,
        hlt_target_c=hlt_target_c, hlt_volume_l=hlt_volume_l,
    )
    if path is not None:
        hass.data.setdefault("brewassistant", {})["hlt_trace_path"] = str(path)

    log = audit.get_brewday_audit_log(hass)
    state_data = hass.data.setdefault("brewassistant", {})
    state_key = (session_id, result.state, result.reason, result.virtual_heater_on,
                 result.temperature_source, result.power_budget_verified,
                 inputs.sparge_required)
    old_key = state_data.get("hlt_audit_state_key")
    state_data["hlt_audit_state_key"] = state_key
    if not log.active:
        return
    transitions = tuple(result.events)
    if not transitions and state_key == old_key:
        return
    event_type = next(
        (_EVENT_TYPES[name] for name in transitions if name == "simulation_budget_conflict"),
        None,
    ) or next((_EVENT_TYPES[name] for name in transitions if name in _EVENT_TYPES), None)
    if event_type is None:
        event_type = "hlt_sim_state"

    event = audit._event_base(hass, event_type, note=f"HLT simulation: {result.state}; no hardware writes")
    event.update({
        "hlt_simulation": True,
        "hlt_state": result.state,
        "hlt_reason": result.reason,
        "hlt_virtual_heater_on": result.virtual_heater_on,
        "hlt_temperature_c": round(result.temperature_c, 2),
        "hlt_temperature_source": result.temperature_source,
        "hlt_measured_temperature_c": inputs.measured_hlt_temperature_c,
        "hlt_target_c": hlt_target_c,
        "hlt_measured_power_w": hlt_power_w,
        "hlt_reserved_w": result.hlt_reservation_w,
        "hlt_brewzilla_power_w": inputs.brewzilla_measured_w,
        "hlt_brewzilla_would_grant_w": result.brewzilla_would_grant_w,
        "hlt_budget_w": usable_budget_w,
        "hlt_total_reserved_w": result.total_reserved_w,
        "hlt_budget_verified": result.power_budget_verified,
        "hlt_transition_events": list(transitions),
    })
    event["severity"] = "warning" if event_type == "hlt_sim_budget_conflict" else "info"
    audit._append_event(log, event)
    await audit.async_save_brewday_audit_log(hass)
