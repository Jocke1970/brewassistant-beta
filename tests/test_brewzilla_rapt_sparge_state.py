"""Sparge reducer regression tests: pure/no HA/hardware writes."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

MODULE = Path(__file__).resolve().parents[1] / "custom_components/brewassistant/brewzilla/brewzilla_rapt_sparge_state.py"
spec = importlib.util.spec_from_file_location("brewzilla_rapt_sparge_state", MODULE)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def observe(previous=None, **changes):
    props = dict(source="RAPT BrewZilla Profile", profile_active=True, contract_valid=True,
                 telemetry_fresh=True, session_id="session-1", step_id="step-5",
                 step_number=5, raw_step_name="Sparge")
    props.update(changes)
    return module.observe(previous or module.SpargeState(), **props)


def confirm(state, **changes):
    props = dict(heater_off=True, pump_off=True, heat_utilization=0.0,
                 pump_utilization=0.0, output_telemetry_fresh=True,
                 kettle_has_sufficient_wort=True, malt_pipe_safely_lifted=True)
    props.update(changes)
    return module.confirm_lift(state, **props)


def test_requires_exact_active_sparge_and_session_identity():
    assert observe().phase == "awaiting_lift"
    assert observe(raw_step_name="Lakning").phase == "awaiting_lift"
    assert observe(raw_step_name="Sparge preparation").phase == "inactive"
    assert observe(source="Brewfather Brew Tracker").phase == "inactive"
    assert observe(session_id=None).phase == "inactive"
    assert observe(step_id=None, step_number=None).phase == "inactive"
    assert observe(profile_active=False).phase == "inactive"
    assert observe(contract_valid=False).phase == "inactive"
    assert observe(telemetry_fresh=False).phase == "inactive"
    assert observe(operator_abort=True).phase == "inactive"


def test_lift_confirmation_requires_operator_and_verified_safe_outputs():
    state = observe()
    assert confirm(state).phase == "heat_to_boil"
    for key, value in (
        ("heater_off", None), ("heater_off", False),
        ("pump_off", None), ("pump_off", False),
        ("heat_utilization", None), ("heat_utilization", 10.0),
        ("pump_utilization", None), ("pump_utilization", 25.0),
        ("output_telemetry_fresh", False),
        ("kettle_has_sufficient_wort", False),
        ("malt_pipe_safely_lifted", False),
    ):
        assert confirm(state, **{key: value}).phase == "awaiting_lift"


def test_confirmation_never_survives_source_session_step_loss_or_abort():
    ready = confirm(observe())
    assert observe(ready).phase == "heat_to_boil"
    for changes in (
        {"session_id": "session-2"}, {"step_id": "step-6"},
        {"step_number": 6}, {"source": "Brewfather Brew Tracker"},
        {"raw_step_name": "Boil"}, {"telemetry_fresh": False},
        {"profile_active": False}, {"operator_abort": True},
    ):
        changed = observe(ready, **changes)
        assert not changed.lift_confirmed
        assert changed.phase != "heat_to_boil"
    assert observe(module.SpargeState(), session_id="session-1").phase == "awaiting_lift"


def test_stale_confirmation_is_not_permission_to_actuate_after_recovery():
    confirmed = confirm(observe())
    unavailable = observe(confirmed, telemetry_fresh=False)
    restored = observe(unavailable)
    assert restored.phase == "awaiting_lift"
    assert restored.lift_confirmed is False
    assert confirm(restored).phase == "heat_to_boil"
