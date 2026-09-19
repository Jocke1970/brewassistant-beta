"""Write HLT simulator samples to JSONL, expose metrics and Audit transitions.

No physical writes. BZ is never granted/capped by the simulator.
"""
from __future__ import annotations

from typing import Any

from .metrics import update_hlt_dashboard
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
    source_context: dict[str, Any] | None = None,
) -> None:
    """Full samples in JSONL; power/timing UI updates, high-signal Audit only."""
    from ..brewday import brewday_audit as audit

    # The trace context comes from the already-selected normalized Brewday
    # snapshot. Do not read raw BT or make another source selection here.
    selected_context = dict(source_context or {})
    path = await async_record_hlt_trace(
        hass, session_id, inputs, result,
        hlt_power_w=hlt_power_w, hlt_switch=hlt_switch,
        stage=stage, step=step, usable_budget_w=usable_budget_w,
        hlt_target_c=hlt_target_c, hlt_volume_l=hlt_volume_l,
        source_context=selected_context,
    )
    state_data = hass.data.setdefault("brewassistant", {})
    if path is not None:
        state_data["hlt_trace_path"] = str(path)
    # On an unchanged tick the trace writer skips a row; its existing file is
    # still the correct upload path, not a missing/changed session.
    recorder = state_data.get("hlt_trace_recorder")
    trace_path = str(recorder.path) if recorder is not None else None
    dashboard = update_hlt_dashboard(
        hass, session_id, inputs, result,
        hlt_power_w=hlt_power_w, hlt_switch=hlt_switch,
        usable_budget_w=usable_budget_w, hlt_target_c=hlt_target_c,
        hlt_volume_l=hlt_volume_l, trace_path=trace_path,
    )

    log = audit.get_brewday_audit_log(hass)
    conflict = "simulation_budget_conflict" in result.events
    # Source/session/step transitions are high-signal and must not be collapsed
    # merely because HLT's virtual heater remains in the same state.
    source_identity = tuple(selected_context.get(field) for field in (
        "brewday_source", "brewday_runtime_state", "brewday_source_status",
        "rapt_profile_session_id", "rapt_profile_step_id",
        "rapt_profile_step_number", "rapt_profile_source_available",
        "rapt_profile_stop_guard_active", "brewday_operator_abort_active",
    ))
    state_key = (session_id, result.state, result.reason, result.virtual_heater_on,
                 result.temperature_source, result.power_budget_verified,
                 inputs.sparge_required, getattr(inputs, "brewzilla_cruising", False),
                 getattr(inputs, "brewzilla_ramp_requested", False), conflict,
                 source_identity)
    old_key = state_data.get("hlt_audit_state_key")
    if not log.active:
        state_data.pop("hlt_audit_state_key", None)
        return
    state_data["hlt_audit_state_key"] = state_key
    transitions = tuple(result.events)
    # A prolonged overload is one warning transition, not 120 copies in Audit.
    if state_key == old_key and (not transitions or transitions == ("simulation_budget_conflict",)):
        return
    event_type = (
        "hlt_sim_budget_conflict" if conflict else
        next((_EVENT_TYPES[name] for name in transitions if name in _EVENT_TYPES), "hlt_sim_state")
    )
    event = audit._event_base(hass, event_type,
                              note=f"HLT simulation: {result.state}; BZ priority, no hardware writes")
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
        "hlt_brewzilla_priority": "unthrottled",
        "hlt_brewzilla_cruising": getattr(inputs, "brewzilla_cruising", False),
        "hlt_brewzilla_ramp_requested": getattr(inputs, "brewzilla_ramp_requested", False),
        "hlt_budget_w": usable_budget_w,
        "hlt_observed_bz_plus_virtual_hlt_w": result.total_reserved_w,
        "hlt_budget_verified": False,
        "hlt_total_session_seconds": dashboard["total_session_seconds"],
        "hlt_virtual_heating_seconds": dashboard["virtual_heating_seconds"],
        "hlt_observed_heating_estimate_seconds": dashboard["observed_heating_estimate_seconds"],
        "hlt_yield_count": dashboard["yield_count"],
        "hlt_transition_events": list(transitions),
        **selected_context,
    })
    event["severity"] = "warning" if conflict else "info"
    audit._append_event(log, event)
    await audit.async_save_brewday_audit_log(hass)
