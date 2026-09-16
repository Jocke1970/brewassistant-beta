"""Hardware-free contracts: BrewZilla is never throttled for HLT."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys

PATH = Path(__file__).resolve().parents[1] / "custom_components/brewassistant/hlt/simulation.py"
SPEC = spec_from_file_location("hlt_simulation_test_module", PATH)
MODULE = module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
Config, Inputs, Simulator = MODULE.SimulationConfig, MODULE.Inputs, MODULE.HLTSimulator


def sample(t, bz=20, watts=450, **kwargs):
    return Inputs(timestamp_s=t, brewzilla_requested_utilization=bz,
                  brewzilla_measured_w=watts, brewzilla_cruising=True, **kwargs)


def test_cruise_grant_then_ramp_reclaims_hlt_without_capping_bz():
    sim = Simulator(Config(usable_budget_w=2750, hlt_heater_w=1500, brewzilla_heater_w=2200))
    first = sim.tick(sample(0))
    assert first.virtual_heater_on
    assert first.brewzilla_would_grant_w is None
    assert first.brewzilla_would_cap_utilization is None
    assert not first.power_budget_verified
    reclaim = sim.tick(sample(10, bz=100, watts=2200,
                              brewzilla_cruising=False, brewzilla_ramp_requested=True))
    assert reclaim.state == "YIELDING"
    assert reclaim.reason == "brewzilla_ramp_priority"
    assert not reclaim.virtual_heater_on
    assert reclaim.hlt_reservation_w == 1500
    assert reclaim.total_reserved_w == 3700  # DO NOT conceal observed overlap by clipping BZ
    assert "simulation_budget_conflict" in reclaim.events
    assert sim.tick(sample(12, bz=100, watts=2200,
                           brewzilla_cruising=False, brewzilla_ramp_requested=True)).state == "YIELDING"
    released = sim.tick(sample(14, bz=100, watts=2200,
                               brewzilla_cruising=False, brewzilla_ramp_requested=True))
    assert released.hlt_reservation_w == 0
    assert released.total_reserved_w == 2200
    assert released.brewzilla_would_grant_w is None
    assert "virtual_hlt_off_confirmed" in released.events


def test_low_watts_alone_do_not_start_hlt_without_cruise():
    sim = Simulator(Config(usable_budget_w=2750, hlt_heater_w=1500))
    result = sim.tick(sample(0, watts=50, brewzilla_cruising=False))
    assert not result.virtual_heater_on
    assert result.reason == "brewzilla_ramp_or_not_cruising"


def test_ramp_request_preempts_even_when_watts_still_low():
    sim = Simulator(Config(usable_budget_w=2750, hlt_heater_w=1500))
    sim.tick(sample(0, watts=200))
    out = sim.tick(sample(2, watts=200, brewzilla_ramp_requested=True))
    assert out.state == "YIELDING"
    assert out.reason == "brewzilla_ramp_priority"
    assert not out.virtual_heater_on


def test_temperature_increases_from_integrated_energy():
    sim = Simulator(Config(usable_budget_w=2750, hlt_heater_w=1000, hlt_volume_l=10,
                           efficiency=1, loss_w_per_k=0))
    sim.tick(sample(0, bz=0, watts=0))
    result = sim.tick(sample(41.86, bz=0, watts=0))
    assert abs(result.temperature_c - 19) < 0.001  # 41.86 kJ raises 10 L by 1 K


def test_unknown_brewzilla_demand_denies_new_opportunity():
    sim = Simulator(Config())
    r = sim.tick(sample(0, bz=None))
    assert not r.virtual_heater_on
    assert r.state == "WAITING_FOR_POWER"


def test_bz_full_power_never_gets_capped():
    sim = Simulator(Config(usable_budget_w=2500, hlt_heater_w=1800))
    r = sim.tick(sample(0, bz=100, watts=2200))
    assert not r.virtual_heater_on
    assert r.brewzilla_would_grant_w is None
    assert r.brewzilla_would_cap_utilization is None
    assert r.total_reserved_w == 2200
    assert not r.power_budget_verified


def test_thermostat_cutoff_calibrates_only_on_edge():
    sim = Simulator(Config(usable_budget_w=2750, hlt_heater_w=1000,
                           thermostat_cutoff_c=78))
    sim.tick(sample(0, bz=0, watts=0, thermostat_heating=True))
    r = sim.tick(sample(10, bz=0, watts=0, thermostat_heating=False))
    assert r.thermostat_calibrated
    assert r.temperature_c == 78
    assert r.temperature_source == "thermostat_calibrated_estimate"


def test_no_sparge_never_requests_heater():
    sim = Simulator(Config())
    r = sim.tick(sample(0, bz=0, watts=0, sparge_required=False))
    assert r.state == "IDLE"
    assert not r.virtual_heater_on


def test_invalid_config_rejected():
    import pytest
    with pytest.raises(ValueError):
        Config(usable_budget_w=0)
