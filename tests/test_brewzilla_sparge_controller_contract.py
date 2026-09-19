"""Execute production Sparge decision functions with simulated readback only.

No Home Assistant integration import, network, or physical service calls.
"""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
CONTROLLER = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_rapt_sparge_controller.py"
INIT = ROOT / "custom_components/brewassistant/brewzilla/__init__.py"


def _functions(path, *names):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    selected = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names]
    assert set(names) == {node.name for node in selected}
    namespace = {}
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), "exec"), namespace)
    return namespace


SOURCE = CONTROLLER.read_text(encoding="utf-8")
METHODS = _functions(CONTROLLER, "_decorate", "_num", "_pump_safe_for_preboil", "_preboil_temperature", "_plan_policy")


class FakeHass:
    def __init__(self, values):
        self.values = values
        self.states = SimpleNamespace(get=lambda entity: object() if entity in values else None)


def _snapshot(phase="heat_to_boil", changes=None, values=None):
    state = SimpleNamespace(phase=phase, lift_confirmed=phase == "heat_to_boil",
                            session_id="session-1", step_id="sparge-1", step_number=5)
    observed = {
        "switch.brewzilla_heater": ("off", True),
        "switch.brewzilla_pump": ("off", True),
        "number.brewzilla_heat_utilization": ("0", True),
        "number.brewzilla_pump_utilization": ("0", True),
        "sensor.brewzilla_temperature": ("80", True),
    }
    observed.update(values or {})
    base = SimpleNamespace(BREWZILLA_HEATER_SWITCH="switch.brewzilla_heater",
                           BREWZILLA_PUMP_SWITCH="switch.brewzilla_pump",
                           BREWZILLA_HEAT_UTILIZATION="number.brewzilla_heat_utilization",
                           BREWZILLA_PUMP_UTILIZATION="number.brewzilla_pump_utilization",
                           BREWZILLA_TEMP_SENSOR="sensor.brewzilla_temperature",
                           UTILIZATION_TOLERANCE=0.1, TARGET_SYNC_TOLERANCE=0.1)
    ns = dict(METHODS, base=base, _observe=lambda hass: state,
              _readback=lambda hass, entity: hass.values.get(entity, (None, False)),
              PREBOIL_TARGET_C=95.0)
    ns["_pump_safe_for_preboil"] = METHODS["_pump_safe_for_preboil"].__class__(**{}) if False else METHODS["_pump_safe_for_preboil"]
    # Production functions use their global namespace; rebind only test dependencies.
    scope = METHODS["_decorate"].__globals__
    scope.update(ns)
    inputs = {"connected": True, "applied_target": 78.0, "current_temperature": 80.0,
              "abort_lockout_active": False, "fail_passive_active": False}
    inputs.update(changes or {})
    return METHODS["_decorate"](FakeHass(observed), inputs)


def test_sparge_lift_phase_requests_only_off_and_zero():
    out = _snapshot("awaiting_lift", values={
        "switch.brewzilla_heater": ("on", True),
        "switch.brewzilla_pump": ("on", True),
        "number.brewzilla_heat_utilization": ("60", True),
        "number.brewzilla_pump_utilization": ("50", True),
    })
    assert out["heater_stop_needed"] and out["pump_stop_needed"]
    assert out["desired_heat_utilization"] == out["desired_pump_utilization"] == 0
    assert out["requested_target"] is None
    assert not out["heater_action_needed"] and not out["pump_action_needed"]
    assert not out["target_sync_needed"]


def test_preboil_requires_fresh_off_zero_pump_and_fresh_kettle():
    healthy = _snapshot()
    assert healthy["rapt_sparge_phase"] == "heat_to_boil"
    assert healthy["requested_target"] == 95.0
    assert healthy["heater_action_needed"]
    assert healthy["desired_heat_utilization"] == 100.0
    assert not healthy["pump_action_needed"]
    for entity, unsafe in (
        ("switch.brewzilla_pump", ("on", True)),
        ("switch.brewzilla_pump", ("off", False)),
        ("number.brewzilla_pump_utilization", ("50", True)),
        ("number.brewzilla_pump_utilization", ("0", False)),
        ("sensor.brewzilla_temperature", ("80", False)),
        ("switch.brewzilla_heater", ("off", False)),
    ):
        out = _snapshot(values={entity: unsafe})
        assert out["orchestration_mode"] == "sparge-preboil-blocked", entity
        assert out["requested_target"] is None, entity
        assert out["desired_heat_utilization"] == 0.0, entity
        assert not out["heater_action_needed"] and not out["target_sync_needed"], entity


def test_abort_and_fail_passive_cannot_issue_sparge_commands():
    for key in ("abort_lockout_active", "fail_passive_active"):
        out = _snapshot(changes={key: True})
        assert not out["can_apply_target"]
        assert not out["target_sync_needed"] and not out["heater_action_needed"]
        assert not out["pump_action_needed"]


def test_sparge_does_not_override_read_only_policy():
    ns = METHODS["_plan_policy"].__globals__
    ns["_PREVIOUS_PLAN_POLICY"] = lambda hass, snapshot, actions: "read_only"
    assert METHODS["_plan_policy"](None, {"rapt_sparge_active": True,
           "rapt_sparge_phase": "heat_to_boil"}, []) == "read_only"
    ns["_PREVIOUS_PLAN_POLICY"] = lambda hass, snapshot, actions: "direct"
    assert METHODS["_plan_policy"](None, {"rapt_sparge_active": True,
           "rapt_sparge_phase": "heat_to_boil"}, []) == "confirm"


def test_sparge_is_installed_inside_source_authority_boundary():
    source = INIT.read_text(encoding="utf-8")
    assert source.index("_physical_mash_interlock.install_physical_mash_interlock()") < source.index(
        "_rapt_sparge_controller.install_rapt_sparge_controller()") < source.index(
        "_source_authority_runtime.install_source_authority_runtime()")
    assert "button.brewassistant_confirm_sparge_lift" not in SOURCE  # No device action on module import.
