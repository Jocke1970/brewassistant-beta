"""One-task execution capability for positive RAPT Sparge commands.

Lift acknowledgement does not grant arbitrary BA actuator writes. Only the
registered explicitly confirmed Supervised Apply executor can send positive
preboil commands, subject to the live source/step/readback gates on EACH write.
A ContextVar alone is insufficient: asyncio child tasks inherit its context.
Bind the grant to the exact executing task and revoke it in a finally block.
"""

from __future__ import annotations

import asyncio
from contextvars import ContextVar

from ..supervised_apply import register_supervised_executor
from . import brewzilla_orchestration as base
from . import brewzilla_rapt_sparge_controller as sparge
from . import brewzilla_source_authority_runtime as source
from . import brewzilla_supervised_runtime_guard as supervised

_INSTALLED = False
_PREVIOUS_WRITE = None
_PREVIOUS_EXECUTE = None
_SUPERVISED_SPARGE_EXECUTION: ContextVar[asyncio.Task | None] = ContextVar(
    "brewassistant_supervised_sparge_execution_task", default=None
)


def _supervised_task_has_grant() -> bool:
    """Reject child-task context inheritance and synchronous/non-task calls."""
    try:
        task = asyncio.current_task()
    except RuntimeError:
        return False
    return task is not None and _SUPERVISED_SPARGE_EXECUTION.get() is task


def _positive_sparge_write(entity: str, *, switch_action: str | None, value: float | None) -> bool:
    """Only OFF and zero are available outside confirmed positive execution."""
    if entity == base.BREWZILLA_HEATER_SWITCH:
        return switch_action != "off"
    if entity == base.BREWZILLA_TARGET_NUMBER:
        return value is None or value > 0
    if entity == base.BREWZILLA_HEAT_UTILIZATION:
        return value is None or value > 0
    return False  # Pump restrictions are handled by the underlying Sparge gate.


def _write_allowed(hass, entity: str, *, switch_action: str | None = None, value: float | None = None) -> bool:
    assert _PREVIOUS_WRITE is not None
    decision, _ = source._live_authority(hass)
    if decision.mode == "rapt_controller":
        state = sparge._observe(hass)
        if state.phase == "heat_to_boil" and _positive_sparge_write(
            entity, switch_action=switch_action, value=value
        ) and not _supervised_task_has_grant():
            return False
    return _PREVIOUS_WRITE(hass, entity, switch_action=switch_action, value=value)


async def _execute_confirmed_plan(hass, pending):
    """Grant only the current CONFIRM executor task, not its child tasks."""
    assert _PREVIOUS_EXECUTE is not None
    task = asyncio.current_task()
    if task is None:
        return {"applied": False, "actions": [],
                "apply_result": "supervised_sparge_missing_executor_task",
                "supervised_confirmation_consumed": False}
    token = _SUPERVISED_SPARGE_EXECUTION.set(task)
    try:
        # The original executor independently rechecks the live plan ID,
        # source, step, ABORT, policy and readback before physical apply.
        return await _PREVIOUS_EXECUTE(hass, pending)
    finally:
        _SUPERVISED_SPARGE_EXECUTION.reset(token)


def install_sparge_execution_guard():
    """Install last after identity and source guards; replace registered executor."""
    global _INSTALLED, _PREVIOUS_WRITE, _PREVIOUS_EXECUTE
    if _INSTALLED:
        return
    _PREVIOUS_WRITE = source._write_allowed
    _PREVIOUS_EXECUTE = supervised.async_execute_confirmed_plan
    source._write_allowed = _write_allowed
    register_supervised_executor(supervised.SOURCE, supervised.KIND, _execute_confirmed_plan)
    _INSTALLED = True
