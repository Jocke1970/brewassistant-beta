"""No-hardware contract tests for the actual #217 guard and runtime functions."""

from __future__ import annotations

import ast
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1] / "custom_components/brewassistant"
GUARD = ROOT / "brewzilla/brewzilla_rapt_link_loss_guard.py"
RUNTIME = ROOT / "brewday/rapt_profile_runtime.py"
IDENTITY = ROOT / "brewzilla/brewzilla_rapt_identity_guard.py"
AUTHORITY = ROOT / "brewzilla/brewzilla_source_authority_runtime.py"
NOW = datetime(2026, 9, 19, 21, 30, tzinfo=timezone.utc)
DOMAIN = "brewassistant"
MARKER = "rapt_cloud_link_brewzilla_profile_runtime"
ID = "binary_sensor.brewzilla_gen4_1_35l_profile_active"


class State:
    def __init__(self, value="on", *, entity_id=ID, age=5, changed=5, **attrs):
        self.entity_id = entity_id
        self.state = value
        self.attributes = {"ba_source": MARKER, "profile_session_id": "run", **attrs}
        self.last_updated = NOW - timedelta(seconds=age)
        self.last_reported = NOW - timedelta(seconds=age)
        self.last_changed = NOW - timedelta(seconds=changed)


class States:
    def __init__(self, entries=()):
        self.entities = {s.entity_id: s for s in entries}

    def get(self, eid):
        return self.entities.get(eid)

    def async_all(self):
        return list(self.entities.values())


class Hass:
    def __init__(self, entries=()):
        self.states = States(entries)
        self.data = {}
        self.scheduled = []

    def async_create_task(self, coro):
        self.scheduled.append(coro)


def load_guard():
    text = GUARD.read_text(encoding="utf-8")
    tree = ast.parse(text)
    funcs = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
             and node.name in {"_recent", "_profile_state", "_active_fresh", "_attested_stop",
                               "_ensure_transition_listener", "_guarded_safe_off_call"}]
    dt_util = SimpleNamespace(utcnow=lambda: NOW, as_utc=lambda value: value.astimezone(timezone.utc))
    runtime = SimpleNamespace(
        RAPT_PROFILE_ENTITY="binary_sensor.brewzilla_profile_active", LISTENER_KEY="listener",
        _store=lambda hass: hass.data.setdefault("store", {"last_known": {"entity_id": ID,
                                                                          "profile_session_id": "run"}}),
        _is_rcl_contract=lambda s: bool(s is not None and s.attributes.get("ba_source") == MARKER
                                        and not s.attributes.get("restored")),
        _async_process_transition=None, _profile_state=None, _fresh_stopped_contract=None,
    )
    calls = []

    def track(hass, ids, callback):
        calls.append((ids, callback))
        return lambda: calls.append(("unsubscribed", None))

    ns = {"dt_util": dt_util, "runtime": runtime, "_MAX_AGE_SECONDS": 90,
          "_LISTENER_ENTITY_KEY": "listener_entity", "DOMAIN": DOMAIN,
          "_OBSERVED_SESSIONS": {}, "_BASE_ACTIVE": lambda s: s is not None and s.state == "on"
          and runtime._is_rcl_contract(s),
          "_BASE_STOP": lambda s: s is not None and s.state == "off"
          and runtime._is_rcl_contract(s),
          "_BASE_CALL": None, "callback": lambda f: f,
          "async_track_state_change_event": track}
    exec(compile(ast.Module(body=funcs, type_ignores=[]), str(GUARD), "exec"), ns)
    runtime._profile_state = ns["_profile_state"]
    runtime._fresh_stopped_contract = ns["_attested_stop"]
    return ns, runtime, calls


class LinkLossTest(unittest.IsolatedAsyncioTestCase):
    def test_dynamic_entity_id_discovered_by_ba_marker(self):
        ns, runtime, _ = load_guard()
        hass = Hass([State()])
        self.assertEqual(ns["_profile_state"](hass).entity_id, ID)
        self.assertIsNone(ns["_profile_state"](Hass([State(entity_id=ID, restored=True)])))

    def test_stale_active_never_grants_fresh_contract(self):
        ns, _, _ = load_guard()
        self.assertFalse(ns["_active_fresh"](State(age=180)))
        self.assertTrue(ns["_active_fresh"](State(age=5)))
        self.assertEqual(ns["_OBSERVED_SESSIONS"][ID], "run")

    def test_off_without_attestation_is_not_stop(self):
        ns, _, _ = load_guard()
        ns["_active_fresh"](State())
        for bad in (State("off"), State("off", profile_stop_confirmed=False,
                                        profile_stopped_session_id="run"),
                    State("off", profile_stop_confirmed=True,
                          profile_stopped_session_id="another"),
                    State("off", profile_stop_confirmed=True,
                          profile_stopped_session_id="run", age=180),
                    State("off", profile_stop_confirmed=True,
                          profile_stopped_session_id="run", changed=180),
                    State("off", profile_stop_confirmed=True,
                          profile_stopped_session_id="run", restored=True)):
            self.assertFalse(ns["_attested_stop"](bad))
        self.assertTrue(ns["_attested_stop"](State(
            "off", profile_stop_confirmed=True, profile_stopped_session_id="run")))

    async def test_listener_binds_real_entity_and_loss_cannot_trigger_stop(self):
        ns, runtime, calls = load_guard()
        hass = Hass([State()])
        runtime._async_process_transition = self._record_transition(hass)
        ns["_ensure_transition_listener"](hass)
        self.assertEqual(calls[0][0], [ID])
        self.assertEqual(hass.data[DOMAIN]["listener_entity"], ID)
        calls[0][1](SimpleNamespace(data={"new_state": State("unavailable")}))
        await hass.scheduled.pop()
        self.assertEqual(hass.data["transitions"], ["unavailable"])
        ns["_ensure_transition_listener"](hass)
        self.assertEqual(len(calls), 1)

    @staticmethod
    def _record_transition(hass):
        async def transition(_hass, state):
            hass.data.setdefault("transitions", []).append(state.state if state else "missing")
        return transition

    async def test_no_output_calls_on_loss_and_recheck_stop_session(self):
        ns, runtime, _ = load_guard()
        hass = Hass([State("unavailable")])
        writes = []

        async def call(*args):
            writes.append(args)
            return "called"

        ns["_BASE_CALL"] = call
        with self.assertRaises(PermissionError):
            await ns["_guarded_safe_off_call"](hass, "switch", "turn_off", "switch.brewzilla_heater")
        self.assertEqual(writes, [])
        ns["_active_fresh"](State())
        hass.states = States([State("off", profile_stop_confirmed=True,
                                    profile_stopped_session_id="run")])
        self.assertEqual(await ns["_guarded_safe_off_call"](
            hass, "switch", "turn_off", "switch.brewzilla_heater"), "called")
        self.assertEqual(len(writes), 1)
        hass.states = States([State("unavailable")])
        with self.assertRaises(PermissionError):
            await ns["_guarded_safe_off_call"](
                hass, "number", "set_value", "number.brewzilla_heat_utilization", {"value": 0})
        self.assertEqual(len(writes), 1)

    def test_original_runtime_and_authority_have_no_timeout_safe_off(self):
        source = RUNTIME.read_text(encoding="utf-8")
        authority = AUTHORITY.read_text(encoding="utf-8")
        identity = IDENTITY.read_text(encoding="utf-8")
        assert 'if _fresh_stopped_contract(state) and store.get("was_active")' in source
        assert 'if store.get("was_active"):\n        _mark_source_unavailable(hass)' in source
        assert 'if authority.may_write_brewzilla is False and not _safe_off_allowed' in authority
        assert 'clear_pending_action_from_source(hass, supervised.SOURCE)' in authority
        assert 'brewzilla_rapt_link_loss_guard.install_rapt_link_loss_guard()' in identity


if __name__ == "__main__":
    unittest.main()
