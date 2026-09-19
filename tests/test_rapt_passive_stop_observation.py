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


def guard_method(name):
    tree = ast.parse(GUARD.read_text(encoding="utf-8"))
    node = next(n for n in tree.body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name)
    runtime = SimpleNamespace(_store=lambda hass: hass.data.setdefault("profile", {}))
    dt_util = SimpleNamespace(utcnow=lambda: NOW)
    logger = SimpleNamespace(info=lambda *args: None)
    base_snapshot = lambda hass, state, store: {
        "summary": "stopped · safe-off · RAPT handoff guard",
        "profile_name": "Test profile",
        "profile_stop_guard_active": True,
        "profile_stop_confirmed": True,
    }
    ns = {"runtime": runtime, "dt_util": dt_util, "_LOGGER": logger,
          "_BASE_STOPPED_SNAPSHOT": base_snapshot}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(GUARD), "exec"), ns)
    return ns[name]


class PassiveStopTest(unittest.IsolatedAsyncioTestCase):
    async def test_delayed_stop_status_sends_no_output_commands(self):
        hass = FakeHass()
        await guard_method("_observe_stop_without_output_commands")(
            hass, "run-1:observation-time"
        )
        record = hass.data["profile"]["last_safe_off"]
        self.assertEqual(record["actions"], [])
        self.assertEqual(record["reason"], "observed_profile_stop_status_only_no_output_commands")
        self.assertIsNone(record["ok"])
        self.assertIs(record["outputs_physically_off_verified"], False)

    async def test_duplicate_stop_observation_is_idempotent(self):
        hass = FakeHass()
        stop = guard_method("_observe_stop_without_output_commands")
        await stop(hass, "run-1:observation-time")
        first = hass.data["profile"]["last_safe_off"]
        await stop(hass, "run-1:observation-time")
        self.assertIs(first, hass.data["profile"]["last_safe_off"])

    def test_stop_snapshot_does_not_claim_physical_safe_off(self):
        snapshot = guard_method("_stopped_snapshot_status_only")(
            FakeHass(), None, {}
        )
        self.assertNotIn("safe-off", snapshot["summary"])
        self.assertEqual(snapshot["brewassistant_role"], "stop_status_observer")
        self.assertFalse(snapshot["profile_stop_guard_active"])
        self.assertTrue(snapshot["profile_stop_confirmed"])
        self.assertFalse(snapshot["hot_side_outputs_physically_off_verified"])

    def test_runtime_status_transition_uses_passive_override(self):
        guard = GUARD.read_text(encoding="utf-8")
        runtime = RUNTIME.read_text(encoding="utf-8")
        self.assertIn("runtime._async_safe_off_after_profile_stop = _observe_stop_without_output_commands", guard)
        self.assertIn("runtime._stopped_snapshot = _stopped_snapshot_status_only", guard)
        self.assertIn("await _async_safe_off_after_profile_stop(hass, token)", runtime)
        self.assertIn('clear_owned_control(hass, reason="rapt_profile_stop_confirmed")', runtime)


if __name__ == "__main__":
    unittest.main()
