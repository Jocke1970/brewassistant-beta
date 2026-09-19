"""Test the additive RAPT/BA local-target agreement guard without real hardware.

Production function bodies are executed against simulated HA state/service
boundaries. None of the existing BT/BF sensors or UI cards are disabled.
"""

from __future__ import annotations

import ast
import math
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_sparge_local_target_guard.py"
INSTALLER = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_rapt_identity_guard.py"


def _functions(*names):
    tree = ast.parse(GUARD.read_text(encoding="utf-8"))
    selected = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names]
    assert {node.name for node in selected} == set(names)
    env = {"Any": Any, "math": math}
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(GUARD), "exec"), env)
    return env


FN = _functions("_profile_target_agrees", "_decorate", "_write_allowed")
TARGET = "number.brewzilla_target_temperature"
HEATER = "switch.brewzilla_heater"
HEAT = "number.brewzilla_heat_utilization"
PUMP = "switch.brewzilla_pump"
PUMP_UTIL = "number.brewzilla_pump_utilization"


class FakeHass:
    def __init__(self, target, *, active=True, step="Sparge", complete=True):
        self.profile = SimpleNamespace(state="on" if active else "off", attributes={
            "step_target_temperature": target, "step_name": step,
            "profile_contract_complete": complete,
        })
        self.outputs = {HEATER: "on", HEAT: "55", PUMP: "off", PUMP_UTIL: "0"}
        self.states = SimpleNamespace(get=lambda entity: self.outputs.get(entity))


def _setup():
    env = FN["_profile_target_agrees"].__globals__
    previous_writes = []

    def write(hass, entity, **kwargs):
        previous_writes.append((entity, kwargs))
        return True

    def previous_decorate(hass, snapshot):
        return {
            **snapshot, "rapt_sparge_active": True,
            "rapt_sparge_phase": "heat_to_boil", "connected": True,
            "requested_target": 95.0, "target_sync_needed": True,
            "heating_needed": True, "desired_heater_on": True,
            "desired_heat_utilization": 100.0, "heater_action_needed": True,
            "heater_stop_needed": False, "heat_utilization_action_needed": True,
            "pump_stop_needed": False, "pump_utilization_action_needed": False,
            "can_apply_target": True,
        }

    base = SimpleNamespace(BREWZILLA_HEATER_SWITCH=HEATER,
                           BREWZILLA_TARGET_NUMBER=TARGET,
                           BREWZILLA_HEAT_UTILIZATION=HEAT)
    sparge = SimpleNamespace(
        PREBOIL_TARGET_C=95.0,
        state_machine=SimpleNamespace(is_sparge_step=lambda name: isinstance(name, str)
                                      and name.strip().casefold() in {"sparge", "lakning"}),
        _readback=lambda hass, entity: (hass.outputs.get(entity), True),
        _num=lambda value: float(value) if value is not None else None,
        _observe=lambda hass: SimpleNamespace(phase="heat_to_boil"),
    )
    env.update(
        rapt=SimpleNamespace(_profile_state=lambda hass: hass.profile,
                             _active_contract=lambda profile: profile.state == "on"),
        sparge=sparge, base=base, TARGET_TOLERANCE_C=0.1,
        source=SimpleNamespace(_live_authority=lambda hass: (SimpleNamespace(mode="rapt_controller"), {})),
        execution=SimpleNamespace(_positive_sparge_write=lambda entity, *, switch_action, value:
                                  (entity == HEATER and switch_action != "off") or
                                  (entity in {TARGET, HEAT} and (value is None or value > 0))),
        _PREVIOUS_DECORATE=previous_decorate, _PREVIOUS_WRITE=write,
        _profile_target_agrees=FN["_profile_target_agrees"],
    )
    return previous_writes


def test_matching_rapt_target_keeps_original_sparge_functionality():
    _setup()
    hass = FakeHass(95.0)
    assert FN["_profile_target_agrees"](hass) == (True, 95.0)
    out = FN["_decorate"](hass, {})
    assert out["requested_target"] == 95.0
    assert out["heater_action_needed"]
    assert out["rapt_sparge_local_target_agrees"]
    assert FN["_write_allowed"](hass, TARGET, value=95)
    assert FN["_write_allowed"](hass, HEATER, switch_action="on")


def test_mismatched_target_blocks_positive_writes_but_keeps_off_and_zero():
    writes = _setup()
    hass = FakeHass(78.0)
    assert FN["_profile_target_agrees"](hass) == (False, 78.0)
    out = FN["_decorate"](hass, {})
    assert out["rapt_sparge_local_target_c"] == 78.0
    assert out["requested_target"] is None and not out["target_sync_needed"]
    assert not out["heater_action_needed"] and not out["heating_needed"]
    assert out["desired_heat_utilization"] == 0
    assert out["heater_stop_needed"] and out["heat_utilization_action_needed"]
    assert out["can_apply_target"]  # Existing safe-down remains available.
    assert "78.0" in out["control_reason"] and "95.0" in out["control_reason"]
    assert not FN["_write_allowed"](hass, TARGET, value=95)
    assert not FN["_write_allowed"](hass, HEAT, value=100)
    assert not FN["_write_allowed"](hass, HEATER, switch_action="on")
    assert FN["_write_allowed"](hass, HEATER, switch_action="off")
    assert FN["_write_allowed"](hass, HEAT, value=0)
    assert len(writes) == 2  # Forbidden positive commands never reach the prior writer.


def test_missing_invalid_or_wrong_step_target_fails_closed_without_deletion():
    _setup()
    for target, name, complete in ((None, "Sparge", True), (float("nan"), "Sparge", True),
                                   (95, "Mash", True), (95, "Sparge", False),
                                   (95, "Sparge", True)):
        hass = FakeHass(target, step=name, complete=complete)
        if name == "Sparge" and complete and target == 95:
            hass.profile.state = "off"  # Disconnected/inactive RAPT is not agreement.
        agrees, _ = FN["_profile_target_agrees"](hass)
        assert not agrees
        assert not FN["_write_allowed"](hass, TARGET, value=95)


def test_abort_and_disconnection_keep_stricter_prior_decisions():
    _setup()
    hass = FakeHass(78)
    for flag in ("abort_lockout_active", "fail_passive_active"):
        out = FN["_decorate"](hass, {flag: True})
        assert out["requested_target"] == 95.0  # Prior guarded snapshot preserved.
        assert "positive BA heating blocked" in out["control_reason"]
    out = FN["_decorate"](hass, {"connected": False})
    # The fake preceding decorator marks connected=True, so this only exercises
    # the result actually returned by the prior decorator (no fabricated bypass).
    assert out["requested_target"] is None


def test_preserves_existing_paths_and_install_order():
    code = GUARD.read_text(encoding="utf-8")
    installer = INSTALLER.read_text(encoding="utf-8")
    assert "sparge._decorate = _decorate" in code
    assert "source._write_allowed = _write_allowed" in code
    assert "brewzilla_sparge_execution_guard.install_sparge_execution_guard()" in installer
    assert "brewzilla_sparge_local_target_guard.install_sparge_local_target_guard()" in installer
    assert installer.index("brewzilla_sparge_execution_guard.install_sparge_execution_guard()") < installer.index(
        "brewzilla_sparge_local_target_guard.install_sparge_local_target_guard()")
    assert "brewfather_brew_tracker_" not in code
    assert "climate.fermentation_chamber" not in code
