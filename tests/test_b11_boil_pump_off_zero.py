"""0b11: active BOIL requests pump OFF/0 through verified RCL authority.

The assertions execute production snapshot and source-writer Python bodies.
No HA services/cloud hardware are invoked by these isolated tests.
"""
from __future__ import annotations

import ast
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
             if isinstance(node, ast.FunctionDef) and node.name in names]
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
])
def test_missing_readback_does_not_guess_physical_off(pump, pct):
    fn, h = prep_guard(pump, pct)
    out = fn(h, {"connected": True, "orchestration_mode": "monitor",
                 "can_apply_target": False, "desired_pump_on": None})
    assert out["boil_pump_readback_verified"] is False
    assert out["boil_pump_policy_block_reason"] == "pump_readback_unavailable"
    assert out.get("pump_stop_needed") is None
    assert out.get("pump_utilization_action_needed") is None


def test_non_boil_stage_does_not_force_zero_or_off():
    fn, h = prep_guard(active=False)
    source = {"connected": True, "pump_action_needed": True,
              "desired_pump_on": True, "desired_pump_utilization": 45}
    out = fn(h, source)
    assert out["desired_pump_on"] is True
    assert out["desired_pump_utilization"] == 45


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
        boil_pump_guard=SimpleNamespace(_current_boil=lambda ha: True),
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
