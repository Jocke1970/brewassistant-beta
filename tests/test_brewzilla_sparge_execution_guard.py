"""Exercise actual one-task Sparge write guard, no HA or live equipment."""

from __future__ import annotations

import ast
import asyncio
from contextvars import ContextVar
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_sparge_execution_guard.py"
IDENTITY = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_rapt_identity_guard.py"
SOURCE = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_source_authority_runtime.py"


def _methods(*names):
    tree = ast.parse(GUARD.read_text(encoding="utf-8"))
    methods = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in names]
    assert {n.name for n in methods} == set(names)
    scope = {}
    exec(compile(ast.Module(body=methods, type_ignores=[]), str(GUARD), "exec"), scope)
    return scope


FUNCTIONS = _methods("_positive_sparge_write", "_write_allowed", "_execute_confirmed_plan")
BASE = SimpleNamespace(BREWZILLA_TARGET_NUMBER="number.brewzilla_target_temperature",
                       BREWZILLA_HEATER_SWITCH="switch.brewzilla_heater",
                       BREWZILLA_HEAT_UTILIZATION="number.brewzilla_heat_utilization")


def test_positive_commands_are_not_inferred_from_lift_confirmation():
    scope = FUNCTIONS["_write_allowed"].__globals__
    flag = ContextVar("sparge_test_grant", default=False)
    accepted = []

    def previous(hass, entity, **kwargs):
        accepted.append((entity, kwargs))
        return True

    scope.update(base=BASE, _PREVIOUS_WRITE=previous,
                 _SUPERVISED_SPARGE_EXECUTION=flag,
                 source=SimpleNamespace(_live_authority=lambda hass: (SimpleNamespace(mode="rapt_controller"), {})),
                 sparge=SimpleNamespace(_observe=lambda hass: SimpleNamespace(phase="heat_to_boil")))
    write = FUNCTIONS["_write_allowed"]
    assert not write(None, BASE.BREWZILLA_HEATER_SWITCH, switch_action="on")
    assert not write(None, BASE.BREWZILLA_HEAT_UTILIZATION, value=100)
    assert not write(None, BASE.BREWZILLA_TARGET_NUMBER, value=95)
    assert write(None, BASE.BREWZILLA_HEATER_SWITCH, switch_action="off")
    assert write(None, BASE.BREWZILLA_HEAT_UTILIZATION, value=0)
    assert len(accepted) == 2
    grant = flag.set(True)
    try:
        assert write(None, BASE.BREWZILLA_HEATER_SWITCH, switch_action="on")
        assert write(None, BASE.BREWZILLA_TARGET_NUMBER, value=95)
    finally:
        flag.reset(grant)
    assert not write(None, BASE.BREWZILLA_HEATER_SWITCH, switch_action="on")


def test_confirmation_capability_always_resets_even_on_failure():
    scope = FUNCTIONS["_execute_confirmed_plan"].__globals__
    flag = ContextVar("sparge_test_executor", default=False)
    scope["_SUPERVISED_SPARGE_EXECUTION"] = flag
    events = []

    async def previous(hass, pending):
        events.append(flag.get())
        raise RuntimeError("hardware refused")

    scope["_PREVIOUS_EXECUTE"] = previous

    async def run():
        try:
            await FUNCTIONS["_execute_confirmed_plan"](None, {})
        except RuntimeError:
            pass
        return flag.get()

    assert asyncio.run(run()) is False
    assert events == [True]


def test_guard_is_installed_after_source_and_replaces_registered_executor():
    identity = IDENTITY.read_text(encoding="utf-8")
    source = SOURCE.read_text(encoding="utf-8")
    guard = GUARD.read_text(encoding="utf-8")
    assert "brewzilla_sparge_execution_guard.install_sparge_execution_guard()" in identity
    assert "source._write_allowed = _write_allowed" in guard
    assert "register_supervised_executor(supervised.SOURCE, supervised.KIND, _execute_confirmed_plan)" in guard
    assert "if not _write_allowed(hass, entity_id" in source
    assert "if not _write_allowed(hass, entity_id, switch_action" in source
