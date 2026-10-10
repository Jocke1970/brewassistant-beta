"""0b6 field regression: ABORT must enter emergency lane before ManualPlan logic.

Execute the *actual* button async_press AST without importing Home Assistant.
No hardware/cloud involved; device-order acceptance is in isolated HA smoke.
"""

from __future__ import annotations

import ast
import asyncio
from pathlib import Path
from types import SimpleNamespace

SOURCE = Path(__file__).resolve().parents[1] / "custom_components/brewassistant/button.py"


def _load(namespace):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "BrewAssistantAbortBrewdayButton")
    method = next(n for n in cls.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "async_press")
    exec(compile(ast.Module(body=[method], type_ignores=[]), str(SOURCE), "exec"), namespace)
    return namespace["async_press"]


class HomeAssistantError(Exception):
    pass


class Logger:
    def exception(self, message):
        raise AssertionError(f"Unexpected logging exception: {message}")


def _run(*, persistence_failed=False):
    events = []

    async def emergency(hass):
        events.append("EMERGENCY_OFF_ZERO_FIRST")
        return {
            "output_off_requests_sent": True,
            "errors": ["abort_latch_persistence: fake failure"] if persistence_failed else [],
        }

    async def audit(hass, event, **kwargs):
        assert event == "brewday_abort"
        events.append("audit")

    async def refresh():
        events.append("refresh")

    press = _load({
        "async_abort_brewzilla": emergency,
        "async_record_brewday_audit_event": audit,
        "HomeAssistantError": HomeAssistantError,
        "_LOGGER": Logger(),
    })
    self_obj = SimpleNamespace(
        coordinator=SimpleNamespace(hass=object(), async_request_refresh=refresh),
        async_write_ha_state=lambda: events.append("state"),
    )
    try:
        asyncio.run(press(self_obj))
    except HomeAssistantError:
        if not persistence_failed:
            raise
        events.append("LOCKOUT_STORAGE_UNVERIFIED")
    return events


def test_active_rapt_abort_never_mutates_manual_runtime_before_emergency():
    assert _run() == ["EMERGENCY_OFF_ZERO_FIRST", "audit", "refresh", "state"]
    code = SOURCE.read_text(encoding="utf-8").split("class BrewAssistantAbortBrewdayButton", 1)[1].split(
        "class BrewAssistantRearmBrewdayControlButton", 1
    )[0]
    assert "get_manual_brewday_session" not in code
    assert "cancel_pending_action" not in code
    assert "build_brewday_runtime_snapshot" not in code


def test_abort_reports_failed_persistence_without_skipping_emergency():
    assert _run(persistence_failed=True) == [
        "EMERGENCY_OFF_ZERO_FIRST", "audit", "refresh", "state", "LOCKOUT_STORAGE_UNVERIFIED"
    ]
