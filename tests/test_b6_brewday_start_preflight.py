"""0b6 START acceptance: live session, fresh outputs, explicit confirmation.

Execute the production preflight and START methods in mocked HA state.
No physical/network operations occur in these tests.
"""

from __future__ import annotations

import ast
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "custom_components/brewassistant/brewday/brewday_start_preflight.py"
UI = ROOT / "dashboard/cards/brewday_control_status_sv.yaml"
OBS = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_observe_only.py"


class FakeError(Exception):
    pass


class StripImports(ast.NodeTransformer):
    def visit_ImportFrom(self, node):
        return None


def build_environment(*, age_seconds=5, profile_active=True, aborted=False):
    now = datetime.now(timezone.utc)
    telemetry = now - timedelta(seconds=age_seconds)
    ids = SimpleNamespace(
        BREWZILLA_TEMP_SENSOR="sensor.brewzilla_temperature",
        BREWZILLA_TARGET_NUMBER="number.brewzilla_target_temperature",
        BREWZILLA_HEATER_SWITCH="switch.brewzilla_heater",
        BREWZILLA_PUMP_SWITCH="switch.brewzilla_pump",
        BREWZILLA_HEAT_UTILIZATION="number.brewzilla_heat_utilization",
        BREWZILLA_PUMP_UTILIZATION="number.brewzilla_pump_utilization",
        BREWZILLA_MAIN_SWITCH="switch.brewzilla",
    )
    state_map = {}
    def state(id, value, attrs=None):
        state_map[id] = SimpleNamespace(
            entity_id=id, state=value, attributes=attrs or {},
            last_reported=telemetry, last_updated=telemetry,
        )

    profile = "binary_sensor.bryggeriet_brewzilla_gen4_1_35l_profile_active"
    state(profile, "on" if profile_active else "off", {
        "ba_source": "rapt_cloud_link_brewzilla_profile_runtime",
        "profile_contract_complete": True,
        "profile_id": "water-profile",
        "profile_session_id": "session-123",
        "step_id": "step-mash",
        "step_name": "Mash Rest",
        "step_target_temperature": 31,
        "raw_device_id": "brewzilla-a",
    })
    for id, value in (
        (ids.BREWZILLA_TEMP_SENSOR, "30.8"),
        (ids.BREWZILLA_TARGET_NUMBER, "31"),
        (ids.BREWZILLA_HEATER_SWITCH, "on"),
        (ids.BREWZILLA_PUMP_SWITCH, "on"),
        (ids.BREWZILLA_HEAT_UTILIZATION, "0"),
        (ids.BREWZILLA_PUMP_UTILIZATION, "100"),
        (ids.BREWZILLA_MAIN_SWITCH, "on"),
    ):
        state(id, value)
    read_only = {"enabled": True}
    calls = []

    async def switch_call(domain, action, payload, blocking=False):
        calls.append((domain, action, dict(payload)))
        assert blocking is True and domain == "switch"
        if action == "turn_off":
            read_only["enabled"] = False
        if action == "turn_on":
            read_only["enabled"] = True

    hass = SimpleNamespace(
        data={},
        states=SimpleNamespace(
            get=state_map.get,
            async_all=lambda: list(state_map.values()),
        ),
        services=SimpleNamespace(async_call=switch_call),
    )
    runtime_override = {}
    def runtime(h):
        source = state_map[profile].attributes
        result = {
            "brewday_mode": "RCL Brewing",
            "source": "RAPT BrewZilla Profile",
            "source_entity": profile,
            "step": source["step_name"],
            "profile_step_id": source["step_id"],
            "profile_id": source["profile_id"],
            "profile_session_id": source["profile_session_id"],
            "target_temperature": source["step_target_temperature"],
            "fallback_active": False,
            "resync_required": False,
        }
        result.update(runtime_override)
        return result
    namespace = {
        "asyncio": asyncio,
        "math": __import__("math"),
        "Any": Any,
        "DOMAIN": "brewassistant",
        "DATA_KEY": "brewday_start_preflight",
        "FRESH_SECONDS": 90,
        "RCL_SOURCE": "RAPT BrewZilla Profile",
        "RCL_MODE": "RCL Brewing",
        "RCL_MARKER": "rapt_cloud_link_brewzilla_profile_runtime",
        "HomeAssistantError": FakeError,
        "dt_util": SimpleNamespace(utcnow=lambda: now, as_utc=lambda x: x),
        "build_brewday_runtime_snapshot": runtime,
        "runtime_override": runtime_override,
        "brewday_operator_abort_active": lambda h: aborted,
        "bz": ids,
        "observe": SimpleNamespace(observation_required=lambda h: read_only["enabled"]),
        "observation_required": lambda h: read_only["enabled"],
    }
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    stripped = StripImports().visit(ast.Module(body=nodes, type_ignores=[]))
    ast.fix_missing_locations(stripped)
    exec(compile(stripped, str(MODULE), "exec"), namespace)
    return hass, state_map, read_only, calls, namespace


def test_preflight_ready_when_verified_rcl_source_and_fresh_readbacks():
    hass, states, ro, calls, funcs = build_environment()
    pre = funcs["preflight_snapshot"](hass)
    assert pre["status"] == "ready"
    assert pre["ready"] is True
    assert pre["identity"]["session_id"] == "session-123"
    assert pre["identity"]["step_id"] == "step-mash"
    assert ro["enabled"] is True
    assert calls == []


@pytest.mark.parametrize("age,active,aborted", [
    (100, True, False),
    (5, False, False),
    (5, True, True),
])
def test_stale_inactive_or_aborted_never_ready(age, active, aborted):
    hass, _, _, _, env = build_environment(age_seconds=age, profile_active=active, aborted=aborted)
    pre = env["preflight_snapshot"](hass)
    assert pre["status"] != "ready"
    assert pre["reasons"]


def test_wrong_confirmation_or_identity_never_touches_switch():
    hass, _, _, calls, env = build_environment()
    start = env["async_start_verified"]
    async def cases():
        with pytest.raises(FakeError):
            await start(hass, confirmed=False, expected_session_id="session-123",
                        expected_step_id="step-mash", expected_profile_id="water-profile")
        with pytest.raises(FakeError):
            await start(hass, confirmed=True, expected_session_id="other",
                        expected_step_id="step-mash", expected_profile_id="water-profile")
    asyncio.run(cases())
    assert calls == []


def test_go_turns_red_only_for_confirmed_session_and_survives_step_advance():
    hass, states, ro, calls, env = build_environment()
    async def go():
        await env["async_start_verified"](
            hass, confirmed=True, expected_session_id="session-123",
            expected_step_id="step-mash", expected_profile_id="water-profile",
        )
    asyncio.run(go())
    assert calls == [("switch", "turn_off", {"entity_id": "switch.brewassistant_brewzilla_observe_only"})]
    assert ro["enabled"] is False
    assert env["preflight_snapshot"](hass)["status"] == "running"
    profile = states["binary_sensor.bryggeriet_brewzilla_gen4_1_35l_profile_active"]
    profile.attributes["step_id"] = "step-next"
    profile.attributes["step_name"] = "Mash Out"
    profile.attributes["step_target_temperature"] = 76
    assert env["preflight_snapshot"](hass)["status"] == "running"
    profile.attributes["profile_session_id"] = "other"
    assert env["preflight_snapshot"](hass)["status"] == "blocked"


def test_preflight_never_guesses_an_inactive_profile_id_and_direct_switch_requires_start():
    code = MODULE.read_text(encoding="utf-8")
    assert '"can_start_rapt_profile": False' in code
    guard = OBS.read_text(encoding="utf-8")
    assert '_start_store(hass).get("starting") is not True' in guard
    ui = UI.read_text(encoding="utf-8")
    assert "brewassistant.brewday_start_verified" in ui
    assert "ba-start-yellow" in ui and "ba-start-green" in ui
    assert "mdi:alert-octagon" in ui
    assert "service: switch.turn_off" not in ui
    assert "expected_session_id" in ui and "expected_step_id" in ui


def test_display_step_spelling_diff_does_not_override_matching_verified_step_id():
    hass, states, ro, calls, funcs = build_environment()
    funcs["runtime_override"]["step"] = "Mash  Rest"  # RAPT displays "Mash Rest"
    pre = funcs["preflight_snapshot"](hass)
    assert pre["status"] == "ready", pre["reasons"]
    assert pre["reasons"] == []
    by_id = {entry["id"]: entry for entry in pre["checks"]}
    assert by_id["step"]["status"] == "passed"
    assert by_id["step_label"]["status"] == "warning"
    assert by_id["step_label"]["blocking"] is False
    assert calls == []


def test_wrong_step_id_blocks_even_if_display_step_name_matches():
    hass, states, ro, calls, funcs = build_environment()
    funcs["runtime_override"]["profile_step_id"] = "different-step-id"
    pre = funcs["preflight_snapshot"](hass)
    assert pre["status"] == "waiting"
    assert pre["ready"] is False
    assert "Steg-ID skiljer" in " | ".join(pre["reasons"])
    assert {v["id"]: v for v in pre["checks"]}["step"]["status"] == "failed"
    assert calls == []


def test_wrong_session_id_blocks_even_when_step_id_and_target_match():
    hass, states, ro, calls, funcs = build_environment()
    funcs["runtime_override"]["profile_session_id"] = "stale-old-session"
    pre = funcs["preflight_snapshot"](hass)
    assert pre["status"] == "waiting"
    assert {v["id"]: v for v in pre["checks"]}["session"]["status"] == "failed"
    assert {v["id"]: v for v in pre["checks"]}["step"]["status"] == "failed"
    assert calls == []


def test_start_chips_explain_freshness_abort_and_confirmation_independently():
    hass, states, ro, calls, funcs = build_environment()
    pre = funcs["preflight_snapshot"](hass)
    statuses = {v["id"]: v["status"] for v in pre["checks"]}
    for key in ("source", "profile", "session", "step", "target", "bz_power",
                "telemetry", "heater", "pump", "read_only", "abort"):
        assert statuses[key] == "passed", (key, statuses[key])
    assert statuses["operator"] == "pending"
    states["switch.brewzilla"].state = "off"
    blocked = funcs["preflight_snapshot"](hass)
    assert blocked["status"] == "waiting"
    assert {v["id"]: v for v in blocked["checks"]}["bz_power"]["status"] == "failed"
    assert calls == []
