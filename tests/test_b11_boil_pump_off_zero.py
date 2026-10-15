"""0b11: active BOIL requests pump OFF/0 through verified RCL authority.

The assertions execute production snapshot and source-writer Python bodies.
No HA services/cloud hardware are invoked by these isolated tests.
"""
from __future__ import annotations

import ast
import asyncio
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
import math
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
BREWZILLA = ROOT / "custom_components/brewassistant/brewzilla"
GUARD = BREWZILLA / "brewzilla_boil_pump_guard.py"
ORCH = BREWZILLA / "brewzilla_orchestration.py"
AUTH = BREWZILLA / "brewzilla_source_authority_runtime.py"
INIT = BREWZILLA / "__init__.py"

PUMP = "switch.brewzilla_pump"
PCT = "number.brewzilla_pump_utilization"


def extract(path, *names):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    nodes = [node for node in tree.body
             if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names]
    assert {node.name for node in nodes} == set(names)
    module = ast.Module(
        body=[ast.ImportFrom(module="__future__",
                             names=[ast.alias(name="annotations")], level=0), *nodes],
        type_ignores=[],
    )
    scope = {}
    exec(compile(ast.fix_missing_locations(module), str(path), "exec"), scope)
    return scope


def kettle(pump="on", utilization=55):
    vals = {PUMP: SimpleNamespace(state=pump)}
    return SimpleNamespace(
        states=SimpleNamespace(get=lambda entity: vals.get(entity)),
        pct=utilization,
    )


def prep_guard(pump="on", utilization=55, active=True):
    ns = extract(GUARD, "_boil_pump_snapshot")
    h = kettle(pump, utilization)
    ns["_current_boil"] = lambda ha: active
    ns["math"] = math
    ns["_pump_utilization_fresh"] = lambda ha: getattr(ha, "util_fresh", True)
    ns["cooling_gate"] = SimpleNamespace(
        observe=lambda ha, active_boil: {"boil_cooling_recirc_allowed": False}
    )
    ns["base"] = SimpleNamespace(
        _float=lambda ha, entity: ha.pct if entity == PCT else None,
        BREWZILLA_PUMP_UTILIZATION=PCT, BREWZILLA_PUMP_SWITCH=PUMP,
        UTILIZATION_TOLERANCE=0.1,
    )
    return ns["_boil_pump_snapshot"], h


@pytest.mark.parametrize(("pump", "utilization", "expected_off", "expected_zero"), [
    ("on", 50.0, True, True),
    ("off", 50.0, False, True),
    ("on", 0.0, True, False),
    ("off", 0.0, False, False),
])
def test_boil_commands_off_and_zero_independently(pump, utilization, expected_off, expected_zero):
    fn, h = prep_guard(pump, utilization)
    snap = {
        "connected": True, "can_apply_target": False,
        "orchestration_mode": "monitor", "runtime_source": "RAPT BrewZilla Profile",
        "pump_stop_needed": False, "pump_action_needed": True,
        "desired_pump_on": True, "desired_pump_utilization": 70,
        "ba_owned_reassert_action_needed": True,
    }
    out = fn(h, snap)
    assert out["desired_pump_on"] is False
    assert out["desired_pump_utilization"] == 0
    assert out["pump_stop_needed"] is expected_off
    assert out["pump_utilization_action_needed"] is expected_zero
    assert out["pump_action_needed"] is False
    assert out["pump_recommended"] is False
    assert out["ba_owned_reassert_action_needed"] is False
    assert out["boil_pump_readback_verified"] is True
    assert out["can_apply_target"] is (expected_off or expected_zero)
    assert snap["desired_pump_on"] is True  # no mutation of previous plan


@pytest.mark.parametrize("block", [
    {"fail_passive_active": True},
    {"resync_required": True},
    {"fallback_active": True},
    {"hot_side_actuator_writes_allowed": False},
    {"abort_lockout_active": True},
    {"rapt_cooling_handoff_active": True},
    {"completed_runtime": True},
    {"connected": False},
    {"can_apply_target": False, "orchestration_mode": "source-observer"},
    {"can_apply_target": False, "orchestration_mode": "blocked"},
])
def test_boil_does_not_override_loss_abort_cooling_readonly_or_blocked_owner(block):
    fn, h = prep_guard()
    original = {
        "connected": True, "can_apply_target": True, "orchestration_mode": "monitor",
        "desired_pump_on": None, "desired_pump_utilization": None,
        "pump_stop_needed": False,
    }
    original.update(block)
    out = fn(h, original)
    assert out["desired_pump_on"] is original["desired_pump_on"]
    assert out["desired_pump_utilization"] is original["desired_pump_utilization"]
    assert out["pump_stop_needed"] is False


@pytest.mark.parametrize(("pump", "pct"), [
    ("unavailable", 50),
    ("unknown", None),
    (None, None),
    ("on", None),
    ("off", float("nan")),
    ("off", float("inf")),
    ("off", float("-inf")),
    ("off", -0.1),
    ("off", 100.1),
])
def test_missing_readback_does_not_guess_physical_off(pump, pct):
    fn, h = prep_guard(pump, pct)
    out = fn(h, {"connected": True, "orchestration_mode": "monitor",
                 "can_apply_target": False, "desired_pump_on": None})
    assert out["boil_pump_readback_verified"] is False
    assert out["boil_pump_policy_block_reason"] == "pump_readback_unavailable"
    assert out["pump_stop_needed"] is False
    assert out["pump_utilization_action_needed"] is False
    assert out["pump_action_needed"] is False
    assert out["can_apply_target"] is False
    assert out["desired_pump_on"] is None
    assert out["desired_pump_utilization"] is None


def test_non_boil_stage_does_not_force_zero_or_off():
    fn, h = prep_guard(active=False)
    source = {"connected": True, "pump_action_needed": True,
              "desired_pump_on": True, "desired_pump_utilization": 45}
    out = fn(h, source)
    assert out["desired_pump_on"] is True
    assert out["desired_pump_utilization"] == 45



@pytest.mark.parametrize(("current_heat", "expected_change"), [
    (0.0, True), (40.0, True), (75.0, True), (100.0, False),
])
def test_boil_heat_100_independent_of_pump_without_forcing_heater_on(current_heat, expected_change):
    fn, h = prep_guard(pump="off", utilization=0)
    out = fn(h, {
        "connected": True, "can_apply_target": False,
        "orchestration_mode": "monitor",
        "heat_utilization": current_heat,
        "desired_heat_utilization": 30, "heat_utilization_action_needed": True,
        "desired_heater_on": None, "heater_action_needed": False,
    })
    assert out["desired_heat_utilization"] == 100.0
    assert out["heat_utilization_action_needed"] is expected_change
    assert out["can_apply_target"] is expected_change
    assert out["desired_heater_on"] is None
    assert out["heater_action_needed"] is False
    assert out["desired_pump_on"] is False
    assert out["desired_pump_utilization"] == 0.0
    assert out["boil_heat_readback_verified"] is True


def test_boil_heat_100_overrides_previous_mash_advice():
    fn, h = prep_guard(pump="on", utilization=50)
    out = fn(h, {
        "connected": True, "can_apply_target": False,
        "orchestration_mode": "monitor",
        "heat_utilization": 60.0, "desired_heat_utilization": 25.0,
        "heat_utilization_action_needed": True,
        "ba_owned_reassert_action_needed": True,
    })
    assert out["desired_heat_utilization"] == 100
    assert out["heat_utilization_action_needed"] is True
    assert out["ba_owned_reassert_action_needed"] is False
    assert out["pump_stop_needed"] is True
    assert out["pump_utilization_action_needed"] is True


@pytest.mark.parametrize("raw", [None, "unavailable", "NaN", -1.0, 130.0])
def test_boil_heat_unknown_never_guessed_as_zero(raw):
    fn, h = prep_guard(pump="off", utilization=0)
    out = fn(h, {
        "connected": True, "can_apply_target": False,
        "orchestration_mode": "monitor",
        "heat_utilization": raw, "desired_heat_utilization": 40.0,
        "heat_utilization_action_needed": True,
    })
    assert out["heat_utilization_action_needed"] is False
    assert out["desired_heat_utilization"] is None
    assert out["can_apply_target"] is False
    assert out["boil_heat_readback_verified"] is False


def test_boil_explicit_heat_safety_reduction_wins():
    fn, h = prep_guard(pump="on", utilization=35)
    out = fn(h, {
        "connected": True, "can_apply_target": True,
        "orchestration_mode": "monitor",
        "heat_utilization": 60.0,
        "desired_heat_utilization": 0.0,
        "desired_heater_on": False, "heater_stop_needed": True,
        "heat_utilization_action_needed": True,
    })
    assert out["desired_heat_utilization"] == 0.0
    assert out["heat_utilization_action_needed"] is True
    assert out["boil_heat_safety_reduction_preserved"] is True
    assert out["desired_heater_on"] is False
    assert out["desired_pump_utilization"] == 0.0


def test_non_boil_does_not_force_heat_100():
    fn, h = prep_guard(active=False)
    source = {"connected": True, "heat_utilization": 50,
              "desired_heat_utilization": 30, "heat_utilization_action_needed": True}
    assert fn(h, source)["desired_heat_utilization"] == 30

def test_base_boil_detection_ignores_upcoming_and_preboil():
    ns = extract(ORCH, "_stage_is_boil")
    ns.update(_current_stage_text=lambda r: f"{r.get('stage') or ''} {r.get('step') or ''} {r.get('raw_step_name') or ''}".lower())
    fn = ns["_stage_is_boil"]
    assert fn({"stage": "Mash", "step": "Mash Out", "next_step": "Boil"}) is False
    assert fn({"stage": "Mash", "step": "Pre-Boil", "next_step": "Boil"}) is False
    assert fn({"stage": "Boil", "step": "Heat to Boil", "next_step": "Chill"}) is True
    assert fn({"stage": "Boil", "step": "Boil Hold"}) is True
    assert fn({"stage": "Cooling", "step": "ChillOut"}) is False


def test_source_authority_pump_positive_rejected_even_by_manual_write_path():
    ns = extract(AUTH, "_write_allowed")
    ns.update(
        BREWZILLA_ENTITIES={PUMP, PCT},
        _BOIL_EXECUTION_IDENTITY=SimpleNamespace(get=lambda: None),
        boil_pump_guard=SimpleNamespace(_current_boil=lambda ha: True),
        cooling_gate=SimpleNamespace(
            observe=lambda ha, active_boil: {"boil_cooling_recirc_allowed": False}
        ),
        math=math,
        base=SimpleNamespace(BREWZILLA_PUMP_SWITCH=PUMP,
            BREWZILLA_PUMP_UTILIZATION=PCT, UTILIZATION_TOLERANCE=0.1),
        _live_authority=lambda ha: (
            SimpleNamespace(may_write_brewzilla=True, write_scope="rcl_assist",
                            mode="rapt_controller"), {}),
        RCL_ASSIST_SCOPE="rcl_assist", FULL_SCOPE="full",
        _rcl_assist_write_allowed=lambda ha, ent, **kwargs: True,
    )
    fn = ns["_write_allowed"]
    assert fn(None, PUMP, switch_action="on") is False
    assert fn(None, PCT, value=75.0) is False
    assert fn(None, PUMP, switch_action="off") is True
    assert fn(None, PCT, value=0.0) is True


def test_interlock_loads_before_source_authority_and_never_changes_emergency():
    src = INIT.read_text(encoding="utf-8")
    assert src.index("_boil_pump_guard.install_boil_pump_guard()") < src.index(
        "_source_authority_runtime.install_source_authority_runtime()")
    assert src.index("_source_authority_runtime.install_source_authority_runtime()") < src.index(
        "_emergency_abort.install_emergency_abort()")
    assert "rapt_cloud_link.start_brewzilla_profile" not in GUARD.read_text(encoding="utf-8")
    assert "hass.services.async_call" not in GUARD.read_text(encoding="utf-8")

def test_verified_cfc_last_15_minutes_requests_positive_pump_without_heater_on():
    # Pump utilization must already be a finite, verified 100% readback.
    fn, h = prep_guard(pump="off", utilization=100)
    # Test only the production snapshot body; a separate test executes the
    # real session-bound RCL timer and operator-choice gate.
    fn.__globals__["cooling_gate"] = SimpleNamespace(
        observe=lambda ha, active_boil: {"boil_cooling_recirc_allowed": True}
    )
    out = fn(h, {
        "connected": True, "can_apply_target": False,
        "orchestration_mode": "monitor",
        "heat_utilization": 100,
        "desired_heater_on": None, "heater_action_needed": False,
    })
    assert out["desired_pump_on"] is True
    assert out["desired_pump_utilization"] == 100.0
    assert out["pump_action_needed"] is True
    assert out["pump_stop_needed"] is False
    assert out["pump_utilization_action_needed"] is False
    assert out["can_apply_target"] is True
    assert out["heater_action_needed"] is False


def test_cfc_last_15_minutes_still_respects_abort_and_rcl_loss():
    fn, h = prep_guard(pump="off", utilization=0)
    fn.__globals__["cooling_gate"] = SimpleNamespace(
        observe=lambda ha, active_boil: {"boil_cooling_recirc_allowed": True}
    )
    for block in ({"fail_passive_active": True},
                  {"abort_lockout_active": True},
                  {"resync_required": True},
                  {"connected": False},
                  {"hot_side_actuator_writes_allowed": False}):
        original = {"connected": True, "can_apply_target": False,
                    "orchestration_mode": "monitor", "desired_pump_on": None}
        original.update(block)
        out = fn(h, original)
        assert out["desired_pump_on"] is None
        assert out.get("pump_action_needed") is None


@pytest.mark.parametrize("utilization", [0.0, 55.0, float("nan"), float("inf"), -1.0, 101.0])
def test_cfc_never_requests_pump_on_without_verified_100_pct(utilization):
    fn, h = prep_guard(pump="off", utilization=utilization)
    fn.__globals__["cooling_gate"] = SimpleNamespace(
        observe=lambda ha, active_boil: {"boil_cooling_recirc_allowed": True}
    )
    out = fn(h, {"connected": True, "orchestration_mode": "monitor",
                 "can_apply_target": False, "heat_utilization": 100})
    assert out["pump_action_needed"] is False
    assert out["boil_pump_readback_verified"] is (math.isfinite(utilization) and 0 <= utilization <= 100)
    if math.isfinite(utilization) and 0 <= utilization <= 100:
        assert out["desired_pump_utilization"] == 100.0
        assert out["pump_utilization_action_needed"] is True
    else:
        assert out["desired_pump_utilization"] is None
        assert out["pump_utilization_action_needed"] is False
        assert out["can_apply_target"] is False


def test_cfc_pump_on_denied_in_alternate_write_path_until_100_pct_readback():
    ns = extract(AUTH, "_write_allowed")
    util = SimpleNamespace(value=50.0, fresh=True)
    ns.update(
        BREWZILLA_ENTITIES={PUMP, PCT},
        _BOIL_EXECUTION_IDENTITY=SimpleNamespace(get=lambda: None),
        boil_pump_guard=SimpleNamespace(
            _current_boil=lambda ha: True,
            _pump_utilization_fresh=lambda ha: util.fresh,
        ),
        cooling_gate=SimpleNamespace(
            observe=lambda ha, active_boil: {"boil_cooling_recirc_allowed": True}
        ),
        math=math,
        base=SimpleNamespace(
            BREWZILLA_PUMP_SWITCH=PUMP,
            BREWZILLA_PUMP_UTILIZATION=PCT, UTILIZATION_TOLERANCE=0.1,
            _float=lambda ha, entity: util.value,
        ),
        _live_authority=lambda ha: (
            SimpleNamespace(may_write_brewzilla=True, write_scope="rcl_assist",
                            mode="rapt_controller"), {}),
        RCL_ASSIST_SCOPE="rcl_assist", FULL_SCOPE="full",
        _rcl_assist_write_allowed=lambda ha, ent, **kwargs: True,
    )
    fn = ns["_write_allowed"]
    for value in [float("nan"), float("inf"), -1, 0, 50, 99.0, 100.1, None]:
        util.value = value
        assert fn(None, PUMP, switch_action="on") is False
        assert fn(None, PCT, value=100.0) is True
    util.value = 100.0
    util.fresh = False
    assert fn(None, PUMP, switch_action="on") is False
    util.fresh = True
    assert fn(None, PUMP, switch_action="on") is True
    assert fn(None, PUMP, switch_action="off") is True


def test_100_percent_stale_utilization_blocks_cfc_pump_on_snapshot():
    fn, hass = prep_guard(pump="off", utilization=100.0)
    hass.util_fresh = False
    fn.__globals__["cooling_gate"] = SimpleNamespace(
        observe=lambda ha, active_boil: {"boil_cooling_recirc_allowed": True}
    )
    out = fn(hass, {"connected": True, "orchestration_mode": "monitor",
                    "can_apply_target": False, "heat_utilization": 100.0})
    assert out["boil_pump_utilization_fresh"] is False
    assert out["pump_action_needed"] is False
    assert out["can_apply_target"] is False


def test_production_pump_utilization_freshness_checks_independent_entity_age():
    ns = extract(GUARD, "_pump_utilization_fresh")
    now = datetime.now(timezone.utc)
    entity = SimpleNamespace(last_reported=now, last_updated=now)
    hass = SimpleNamespace(states=SimpleNamespace(get=lambda eid: entity if eid == PCT else None))
    ns.update(base=SimpleNamespace(BREWZILLA_PUMP_UTILIZATION=PCT),
              datetime=datetime, timezone=timezone,
              MAX_PUMP_READBACK_AGE_SECONDS=90)
    fresh = ns["_pump_utilization_fresh"]
    assert fresh(hass) is True
    entity.last_reported = now - timedelta(minutes=3)
    assert fresh(hass) is False
    entity.last_reported = None
    entity.last_updated = now - timedelta(minutes=3)
    assert fresh(hass) is False
    entity.last_updated = None
    assert fresh(hass) is False
    entity.last_reported = now + timedelta(minutes=2)
    assert fresh(hass) is False


def test_inflight_cfc_plan_cannot_start_pump_after_rcl_leaves_boil():
    # Execute the real task-bound authorization wrapper and real writer guard
    # under a simulated step change during an awaited RCL call.
    ns = extract(AUTH, "_write_allowed", "with_boil_execution_identity")
    expected = ("session-A", "profile-A", "boil-A", "transition-A")
    runtime = SimpleNamespace(identity=expected, current_boil=True)
    ns.update(
        _BOIL_EXECUTION_IDENTITY=ContextVar("test_boil_identity", default=None),
        _live_boil_cfc_identity=lambda ha: runtime.identity if runtime.current_boil else None,
        BREWZILLA_ENTITIES={PUMP, PCT},
        boil_pump_guard=SimpleNamespace(
            _current_boil=lambda ha: runtime.current_boil,
            _pump_utilization_fresh=lambda ha: True,
        ),
        cooling_gate=SimpleNamespace(
            observe=lambda ha, active_boil: {"boil_cooling_recirc_allowed": True}
        ),
        math=math,
        base=SimpleNamespace(
            BREWZILLA_PUMP_SWITCH=PUMP,
            BREWZILLA_PUMP_UTILIZATION=PCT, UTILIZATION_TOLERANCE=0.1,
            _float=lambda ha, entity: 100,
        ),
        _live_authority=lambda ha: (
            SimpleNamespace(may_write_brewzilla=True, write_scope="rcl_assist",
                            mode="rapt_controller"), {}),
        RCL_ASSIST_SCOPE="rcl_assist", FULL_SCOPE="full",
        _rcl_assist_write_allowed=lambda ha, ent, **kwargs: True,
    )
    write = ns["_write_allowed"]

    async def execute(_hass):
        assert write(None, PUMP, switch_action="on") is True
        await asyncio.sleep(0)  # RCL step advances during earlier await
        runtime.current_boil = False
        assert write(None, PUMP, switch_action="on") is False
        assert write(None, PCT, value=100.0) is False
        assert write(None, PUMP, switch_action="off") is True
        return "blocked_stale_step"

    assert asyncio.run(ns["with_boil_execution_identity"](None, execute)) == "blocked_stale_step"
    assert ns["_BOIL_EXECUTION_IDENTITY"].get() is None
    supervised = (BREWZILLA / "brewzilla_supervised_runtime_guard.py").read_text(encoding="utf-8")
    assert "source_authority.with_boil_execution_identity(hass, _BASE_APPLY)" in supervised
