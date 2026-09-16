"""Hardware-free contract tests for the HLT simulator."""
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
                  brewzilla_measured_w=watts, brewzilla_unconstrained=False, **kwargs)


def test_grant_then_reclaim_waits_for_virtual_release():
    sim = Simulator(Config(usable_budget_w=2750, hlt_heater_w=1500, brewzilla_heater_w=2200))
    assert sim.tick(sample(0)).virtual_heater_on
    reclaim = sim.tick(sample(10, bz=100, watts=2200))
    assert reclaim.state == "YIELDING"
    assert not reclaim.virtual_heater_on
    assert reclaim.hlt_reservation_w == 1500
    assert reclaim.brewzilla_would_grant_w == 1250
    assert sim.tick(sample(12, bz=100, watts=2200)).state == "YIELDING"
    released = sim.tick(sample(14, bz=100, watts=2200))
    assert released.hlt_reservation_w == 0
    assert released.brewzilla_would_grant_w == 2200
    assert "virtual_hlt_off_confirmed" in released.events


def test_temperature_increases_from_integrated_energy():
    sim = Simulator(Config(usable_budget_w=2750, hlt_heater_w=1000, hlt_volume_l=10,
                           efficiency=1, loss_w_per_k=0))
    sim.tick(sample(0, bz=0, watts=0))
    result = sim.tick(sample(4186, bz=0, watts=0))
    assert abs(result.temperature_c - 118) < 0.001  # 100 K from 4186 kJ / 41.86 kJ/K


def test_unknown_brewzilla_demand_denies_new_grant():
    sim = Simulator(Config())
    r = sim.tick(sample(0, bz=None))
    assert not r.virtual_heater_on
    assert r.state == "WAITING_FOR_POWER"


def test_unconstrained_brewzilla_reserves_full_power():
    sim = Simulator(Config(usable_budget_w=2500, hlt_heater_w=1800))
    r = sim.tick(Inputs(0, 20, 440))
    assert not r.virtual_heater_on
    assert r.brewzilla_would_grant_w == 2200
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
