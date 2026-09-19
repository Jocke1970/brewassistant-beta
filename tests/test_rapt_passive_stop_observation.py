"""Regression: delayed STOP status is not a second STOP/ABORT command."""

from __future__ import annotations

import ast
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1] / "custom_components/brewassistant"
GUARD = ROOT / "brewzilla/brewzilla_rapt_link_loss_guard.py"
RUNTIME = ROOT / "brewday/rapt_profile_runtime.py"
NOW = datetime(2026, 9, 20, tzinfo=timezone.utc)


class FailIfWritten:
    async def async_call(self, *args, **kwargs):
        raise AssertionError("STOP telemetry caused a second physical command")


class FakeHass:
    def __init__(self):
        self.data = {}
        self.services = FailIfWritten()


def observe_stop():
    source = GUARD.read_text(encoding="utf-8")
    tree = ast.parse(source)
    node = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef)
                and n.name == "_observe_stop_without_output_commands")
    runtime = SimpleNamespace(_store=lambda hass: hass.data.setdefault("profile", {}))
    dt_util = SimpleNamespace(utcnow=lambda: NOW)
    logger = SimpleNamespace(info=lambda *args: None)
    ns = {"runtime": runtime, "dt_util": dt_util, "_LOGGER": logger}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(GUARD), "exec"), ns)
    return ns["_observe_stop_without_output_commands"]


class PassiveStopTest(unittest.IsolatedAsyncioTestCase):
    async def test_delayed_stop_status_sends_no_output_commands(self):
        hass = FakeHass()
        await observe_stop()(hass, "run-1:observation-time")
        record = hass.data["profile"]["last_safe_off"]
        self.assertEqual(record["actions"], [])
        self.assertEqual(record["reason"], "observed_profile_stop_status_only_no_output_commands")
        self.assertIsNone(record["ok"])
        self.assertIs(record["outputs_physically_off_verified"], False)

    async def test_duplicate_stop_observation_is_idempotent(self):
        hass = FakeHass()
        stop = observe_stop()
        await stop(hass, "run-1:observation-time")
        first = hass.data["profile"]["last_safe_off"]
        await stop(hass, "run-1:observation-time")
        self.assertIs(first, hass.data["profile"]["last_safe_off"])

    def test_runtime_status_transition_uses_passive_override(self):
        guard = GUARD.read_text(encoding="utf-8")
        runtime = RUNTIME.read_text(encoding="utf-8")
        self.assertIn("runtime._async_safe_off_after_profile_stop = _observe_stop_without_output_commands", guard)
        self.assertIn("await _async_safe_off_after_profile_stop(hass, token)", runtime)
        self.assertIn('clear_owned_control(hass, reason="rapt_profile_stop_confirmed")', runtime)


if __name__ == "__main__":
    unittest.main()
