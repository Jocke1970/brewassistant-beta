"""Exercise task-bound Sparge write guard without HA or live equipment."""

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


FUNCTIONS = _methods("_positive_sparge_write", "_supervised_task_has_grant",
                     "_write_allowed", "_execute_confirmed_plan")
BASE = SimpleNamespace(BREWZILLA_TARGET_NUMBER="number.brewzilla_target_temperature",
                       BREWZILLA_HEATER_SWITCH="switch.brewzilla_heater",
                       BREWZILLA_HEAT_UTILIZATION="number.brewzilla_heat_utilization")


def test_positive_commands_require_exact_executor_task_not_inherited_context():
    scope = FUNCTIONS["_write_allowed"].__globals__
    flag = ContextVar("sparge_test_grant", default=None)
    accepted = []

    def previous(hass, entity, **kwargs):
        accepted.append((entity, kwargs))
        return True

    scope.update(base=BASE, asyncio=asyncio, _PREVIOUS_WRITE=previous,
                 _SUPERVISED_SPARGE_EXECUTION=flag,
                 _supervised_task_has_grant=FUNCTIONS["_supervised_task_has_grant"],
                 source=SimpleNamespace(_live_authority=lambda hass: (SimpleNamespace(mode="rapt_controller"), {})),
                 sparge=SimpleNamespace(_observe=lambda hass: SimpleNamespace(phase="heat_to_boil")))
    write = FUNCTIONS["_write_allowed"]
    assert not write(None, BASE.BREWZILLA_HEATER_SWITCH, switch_action="on")
    assert not write(None, BASE.BREWZILLA_HEAT_UTILIZATION, value=100)
    assert not write(None, BASE.BREWZILLA_TARGET_NUMBER, value=95)
    assert write(None, BASE.BREWZILLA_HEATER_SWITCH, switch_action="off")
    assert write(None, BASE.BREWZILLA_HEAT_UTILIZATION, value=0)

    async def child_attempt():
        # create_task inherits the ContextVar VALUE, but must not inherit authority.
        assert flag.get() is not None
        assert flag.get() is not asyncio.current_task()
        assert not write(None, BASE.BREWZILLA_HEATER_SWITCH, switch_action="on")
        assert not write(None, BASE.BREWZILLA_TARGET_NUMBER, value=95)

    async def run():
        assert not write(None, BASE.BREWZILLA_HEATER_SWITCH, switch_action="on")
        token = flag.set(asyncio.current_task())
        try:
            assert write(None, BASE.BREWZILLA_HEATER_SWITCH, switch_action="on")
            assert write(None, BASE.BREWZILLA_TARGET_NUMBER, value=95)
            await asyncio.create_task(child_attempt())
        finally:
            flag.reset(token)
        assert flag.get() is None
        assert not write(None, BASE.BREWZILLA_HEATER_SWITCH, switch_action="on")

    asyncio.run(run())
    assert not write(None, BASE.BREWZILLA_HEATER_SWITCH, switch_action="on")
    assert len(accepted) == 4  # two safe-down, two explicitly confirmed positive


def test_confirmation_capability_always_resets_even_on_failure():
    scope = FUNCTIONS["_execute_confirmed_plan"].__globals__
    flag = ContextVar("sparge_test_executor", default=None)
    scope.update(asyncio=asyncio, _SUPERVISED_SPARGE_EXECUTION=flag)
    events = []

    async def previous(hass, pending):
        events.append(flag.get() is asyncio.current_task())
        async def child():
            events.append(flag.get() is asyncio.current_task())
            events.append(FUNCTIONS["_supervised_task_has_grant"]())
        await asyncio.create_task(child())
        raise RuntimeError("hardware refused")

    scope["_PREVIOUS_EXECUTE"] = previous

    async def run():
        try:
            await FUNCTIONS["_execute_confirmed_plan"](None, {})
        except RuntimeError:
            pass
        return flag.get()

    assert asyncio.run(run()) is None
    assert events == [True, False, False]


def test_guard_is_installed_after_source_and_replaces_registered_executor():
    identity = IDENTITY.read_text(encoding="utf-8")
    source = SOURCE.read_text(encoding="utf-8")
    guard = GUARD.read_text(encoding="utf-8")
    assert "brewzilla_sparge_execution_guard.install_sparge_execution_guard()" in identity
    assert "source._write_allowed = _write_allowed" in guard
    assert "register_supervised_executor(supervised.SOURCE, supervised.KIND, _execute_confirmed_plan)" in guard
    assert "if not _write_allowed(hass, entity_id" in source
    assert "if not _write_allowed(hass, entity_id, switch_action" in source
    assert "_SUPERVISED_SPARGE_EXECUTION.get() is task" in guard
