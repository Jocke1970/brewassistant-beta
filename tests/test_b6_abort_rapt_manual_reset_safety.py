"""Regress the real ABORT button's active-RAPT manual-reset exception (0b5 field finding).

Tests run the production async_press AST method with fake HA state. No hardware
is touched. A successful HA service response never proves physical OFF.
"""

from __future__ import annotations

import ast
import asyncio
from pathlib import Path
from types import SimpleNamespace

BUTTON_FILE = Path(__file__).resolve().parents[1] / "custom_components/brewassistant/button.py"


def _load_abort_press(namespace):
    tree = ast.parse(BUTTON_FILE.read_text(encoding="utf-8"))
    button_cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "BrewAssistantAbortBrewdayButton")
    method = next(n for n in button_cls.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "async_press")
    exec(compile(ast.Module(body=[method], type_ignores=[]), str(BUTTON_FILE), "exec"), namespace)
    return namespace["async_press"]


class _Logger:
    def __init__(self):
        self.errors = []

    def exception(self, msg):
        self.errors.append(msg)


def _case(*, source, manual_reset_raises=False, latch_raises=False):
    calls = []
    logger = _Logger()
    holder = SimpleNamespace(hass=object())

    async def latch(hass, **context):
        calls.append("latch")
        assert context["source"] == source
        if latch_raises:
            raise RuntimeError("storage temporarily unavailable")

    async def emergency(hass):
        calls.append("EMERGENCY_BREWZILLA_OFF_REQUEST")
        return {"actions": ["heater_off", "pump_off"], "safe_state_enforced": False}

    async def audit(hass, event, **kwargs):
        calls.append("audit")
        assert event == "brewday_abort"

    def manual_session(hass):
        calls.append("get_manual_session")
        if source != "Manual Brewday":
            raise AssertionError("ABORT must not access ManualPlan under active RAPT ownership")
        return SimpleNamespace(reset=reset)

    def reset():
        calls.append("manual_reset")
        if manual_reset_raises:
            raise RuntimeError("manual reset failed")

    async def refresh():
        calls.append("refresh")

    namespace = {
        "build_brewday_runtime_snapshot": lambda hass: {"source": source, "stage": "Mash", "step": "Mash Rest"},
        "async_latch_brewday_operator_abort": latch,
        "async_abort_brewzilla": emergency,
        "cancel_pending_action": lambda hass: calls.append("cancel_pending"),
        "get_manual_brewday_session": manual_session,
        "async_record_brewday_audit_event": audit,
        "_LOGGER": logger,
    }
    press = _load_abort_press(namespace)
    self_obj = SimpleNamespace(
        coordinator=SimpleNamespace(hass=holder.hass, async_request_refresh=refresh),
        async_write_ha_state=lambda: calls.append("write_state"),
    )
    asyncio.run(press(self_obj))
    return calls, logger.errors


def test_abort_with_active_rapt_skips_manual_guard_and_requests_physical_off():
    calls, errors = _case(source="RAPT BrewZilla Profile")
    assert not errors
    assert calls == [
        "latch",
        "EMERGENCY_BREWZILLA_OFF_REQUEST",
        "cancel_pending",
        "audit",
        "refresh",
        "write_state",
    ]


def test_manual_reset_error_is_not_allowed_to_cancel_emergency_off_request():
    calls, errors = _case(source="Manual Brewday", manual_reset_raises=True)
    assert calls.index("EMERGENCY_BREWZILLA_OFF_REQUEST") < calls.index("manual_reset")
    assert "audit" in calls
    assert len(errors) == 1


def test_abort_attempts_emergency_even_when_abort_latch_storage_fails():
    calls, errors = _case(source="RAPT BrewZilla Profile", latch_raises=True)
    assert calls.index("EMERGENCY_BREWZILLA_OFF_REQUEST") == 1
    assert len(errors) == 1
