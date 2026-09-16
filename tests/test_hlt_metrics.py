"""Hardware-free contract tests for UI-ready HLT telemetry."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

PATH = Path(__file__).resolve().parents[1] / "custom_components/brewassistant/hlt/metrics.py"
SPEC = spec_from_file_location("hlt_metrics_contract", PATH)
MODULE = module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
Metrics = MODULE.HLTMetrics


def sample(t, *, bz=400, virtual=True, state="HEATING", events=(), temp=41,
           measured_temp=None, switch="on", hlt_w=1000, active=True,
           reason="cruise_power_opportunity_simulated"):
    inputs = SimpleNamespace(timestamp_s=t, brewzilla_measured_w=bz,
                             sparge_required=active, enable_hlt=active,
                             measured_hlt_temperature_c=measured_temp,
                             brewzilla_cruising=True, brewzilla_ramp_requested=False)
    result = SimpleNamespace(state=state, reason=reason, virtual_heater_on=virtual,
                             hlt_reservation_w=1500 if virtual else 0,
                             events=events, temperature_c=temp,
                             temperature_source="measured" if measured_temp is not None else "estimated",
                             temperature_uncertainty="model or sensor")
    return inputs, result, dict(hlt_power_w=hlt_w, hlt_switch=switch,
                                usable_budget_w=2750, hlt_target_c=78, hlt_volume_l=10,
                                trace_path="/config/brewassistant/logs/test.jsonl")


def test_sampled_time_energy_and_brewzilla_priority():
    m = Metrics("brewday-A")
    i, r, context = sample(0)
    first = m.update(i, r, **context)
    assert first["total_session_seconds"] == 0
    assert first["power_priority"] == "brewzilla"
    assert first["actual_energy_recipient"] == "brewzilla_and_hlt"
    assert first["hlt_power_virtual_w"] == 1500
    assert first["virtual_total_scenario_w"] == 1900
    assert first["actual_total_observed_w"] == 1400
    assert first["hlt_temperature_estimated_c"] == 41
    assert first["hlt_temperature_measured_c"] is None
    assert first["trace_path"].endswith("test.jsonl")
    i, r, context = sample(30, temp=43)
    second = m.update(i, r, **context)
    assert second["total_session_seconds"] == 30
    assert second["virtual_heating_seconds"] == 30
    assert second["observed_heating_estimate_seconds"] == 30
    assert second["bz_energy_estimate_wh"] == pytest.approx(400 * 30 / 3600, abs=0.01)
    assert second["hlt_energy_estimate_wh"] == pytest.approx(1000 * 30 / 3600, abs=0.01)


def test_reclaim_does_not_forge_actual_heating_or_virtual_reservation():
    m = Metrics("brewday-B")
    i, r, context = sample(0)
    m.update(i, r, **context)
    i, r, context = sample(30, bz=2200, virtual=False, state="YIELDING",
                           events=("virtual_hlt_off_requested",), hlt_w=0,
                           switch="off", reason="brewzilla_ramp_priority")
    out = m.update(i, r, **context)
    assert out["virtual_heating_seconds"] == 30  # previous sampled virtual state
    assert out["observed_heating_estimate_seconds"] == 0  # transition not continuously observed
    assert out["hlt_power_virtual_w"] == 0
    assert out["actual_energy_recipient"] == "brewzilla"
    assert out["reclaim_count"] == 1
    assert out["yield_count"] == 1
    assert out["physical_control_enabled"] is False
    assert out["power_budget_verified"] is False
    i, r, context = sample(60, bz=2200, virtual=False, state="WAITING_FOR_POWER", hlt_w=0,
                           switch="off")
    out = m.update(i, r, **context)
    assert out["yielding_seconds"] == 30
    assert out["total_session_seconds"] == 60


def test_missing_real_power_is_unknown_not_zero_and_long_gap_is_excluded():
    m = Metrics("brewday-C")
    i, r, context = sample(0, hlt_w=None, switch=None)
    out = m.update(i, r, **context)
    assert out["actual_energy_recipient"] == "unknown"
    assert out["actual_total_observed_w"] is None
    assert out["actual_headroom_observed_w"] is None
    i, r, context = sample(180, hlt_w=None, switch=None)
    out = m.update(i, r, **context)
    assert out["unknown_sample_seconds"] == 180
    assert out["virtual_heating_seconds"] == 0
    assert out["observed_heating_estimate_seconds"] == 0
    assert out["total_session_seconds"] == 180


def test_measured_temp_and_session_reset_and_inactive_snapshot():
    hass = SimpleNamespace(data={})
    i, r, context = sample(10, measured_temp=45)
    out = MODULE.update_hlt_dashboard(hass, "session-1", i, r, **context)
    assert out["hlt_temperature_measured_c"] == 45
    assert out["hlt_temperature_estimated_c"] is None
    i, r, context = sample(40, measured_temp=46)
    MODULE.update_hlt_dashboard(hass, "session-1", i, r, **context)
    i, r, context = sample(100, measured_temp=47)
    out = MODULE.update_hlt_dashboard(hass, "session-2", i, r, **context)
    assert out["total_session_seconds"] == 0
    assert out["session_id"] == "session-2"
    hass.data["brewassistant"]["hlt_simulation_runtime"] = {"status": "waiting_for_brewday_recorder"}
    ended = MODULE.build_hlt_dashboard_snapshot(hass)
    assert ended["status"] == "waiting_for_brewday_recorder"
    assert ended["hlt_power_observed_w"] is None
    assert ended["actual_energy_recipient"] == "unknown"
    assert ended["total_session_seconds"] == 0


def test_monotonic_timestamp_enforced():
    m = Metrics("brewday-D")
    i, r, context = sample(30)
    m.update(i, r, **context)
    i, r, context = sample(29)
    with pytest.raises(ValueError):
        m.update(i, r, **context)
