"""Exercise production writer entry points with recorded mock service dispatch.

This tests the BA-owned call boundary, not a complete Home Assistant setup.
A forbidden write must never reach a mocked HA service under BT/unknown RAPT.
"""

from __future__ import annotations

import ast
import asyncio
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_source_authority_runtime.py"
SOURCE = PATH.read_text(encoding="utf-8")


def _functions(*names):
    selected = [node for node in ast.parse(SOURCE).body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names]
    assert {node.name for node in selected} == set(names)
    env = {}
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(PATH), "exec"), env)
    return env


F = _functions("_safe_off_allowed", "_write_allowed", "_set_number",
               "_call_switch", "_policy_execute", "_apply", "_rapt_stop",
               "_observer_snapshot")
TARGET = "number.brewzilla_target_temperature"
HEATER = "switch.brewzilla_heater"
PUMP = "switch.brewzilla_pump"
HEAT = "number.brewzilla_heat_utilization"
PUMP_PCT = "number.brewzilla_pump_utilization"
ENTITIES = frozenset({TARGET, HEATER, PUMP, HEAT, PUMP_PCT})
BASE = SimpleNamespace(BREWZILLA_TARGET_NUMBER=TARGET, BREWZILLA_HEATER_SWITCH=HEATER,
                       BREWZILLA_PUMP_SWITCH=PUMP, BREWZILLA_HEAT_UTILIZATION=HEAT,
                       BREWZILLA_PUMP_UTILIZATION=PUMP_PCT)


class FakeHass:
    def __init__(self):
        self.data = {}
        self.service_calls = []


async def _run_case(mode, *, stop=False, abort=False):
    hass = FakeHass()
    context = {
        "runtime": {"source": "RAPT BrewZilla Profile" if stop else "Brewfather Brew Tracker",
                    "profile_stop_confirmed": stop, "profile_stop_guard_active": stop},
        "operator": {"active": abort,
                     "source": "RAPT BrewZilla Profile" if abort else None},
    }
    decision = SimpleNamespace(mode=mode, may_write_brewzilla=(
        True if mode == "rapt_controller" else None if mode == "manual_legacy_unresolved" else False),
        reason=mode)
    env = F["_write_allowed"].__globals__

    async def send_number(hass, entity, value):
        hass.service_calls.append(("number", "set_value", entity, value))
        return True

    async def send_switch(hass, service, entity):
        hass.service_calls.append(("switch", service, entity, None))

    async def dispatch_policy(hass, action):
        hass.service_calls.append(("policy", action.get("service"), action.get("entity_id"),
                                   (action.get("service_data") or {}).get("value")))
        return {"status": "executed"}

    async def apply(hass):
        hass.service_calls.append(("apply", "run", None, None))
        return {"applied": True}

    async def stop_handler(hass, token):
        hass.service_calls.append(("stop", "off", token, None))

    denied = []
    env.update(
        BREWZILLA_ENTITIES=ENTITIES, base=BASE, DOMAIN="brewassistant",
        _live_authority=lambda hass: (decision, context),
        _safe_off_allowed=F["_safe_off_allowed"],
        _sparge_write_allowed=lambda hass, entity, **kwargs: True,
        _write_allowed=F["_write_allowed"],
        _observer_snapshot=F["_observer_snapshot"],
        _PREVIOUS_SET=send_number, _PREVIOUS_SWITCH=send_switch,
        _PREVIOUS_POLICY_EXECUTE=dispatch_policy, _PREVIOUS_APPLY=apply,
        _PREVIOUS_STOP=stop_handler, _PREVIOUS_BUILD=lambda hass: {"can_apply_target": True},
        control_policy=SimpleNamespace(_store_policy_result=lambda hass, result: (denied.append(result) or result)),
        supervised=SimpleNamespace(SOURCE="brewzilla_orchestration"),
        clear_pending_action_from_source=lambda hass, source: None,
        rapt_profile_runtime=SimpleNamespace(_store=lambda hass: hass.data.setdefault("rapt", {})),
        sparge=SimpleNamespace(_observe=lambda hass: SimpleNamespace(phase="inactive")),
    )

    for entity, value in ((TARGET, 95), (HEAT, 100), (PUMP_PCT, 70)):
        try:
            await F["_set_number"](hass, entity, value)
        except PermissionError:
            pass
    for entity in (HEATER, PUMP):
        for service in ("on", "off"):
            try:
                await F["_call_switch"](hass, service, entity)
            except PermissionError:
                pass
    for action in (
        {"entity_id": TARGET, "service": "set_value", "service_data": {"value": 95}},
        {"entity_id": HEATER, "service": "turn_on", "service_data": {}},
        {"entity_id": PUMP, "service": "turn_off", "service_data": {}},
    ):
        await F["_policy_execute"](hass, action)
    result = await F["_apply"](hass)
    await F["_rapt_stop"](hass, "session-a")
    return hass, result, denied


def test_bt_observer_all_writer_entry_points_are_noop_including_off():
    hass, result, denied = asyncio.run(_run_case("brewfather_observer"))
    assert hass.service_calls == []
    assert result["applied"] is False and result["actions"] == []
    assert len(denied) == 3
    assert all(row["status"] == "source_authority_denied" for row in denied)


def test_unknown_rapt_contract_never_emits_positive_or_off_writes():
    hass, result, denied = asyncio.run(_run_case("blocked"))
    assert hass.service_calls == []
    assert result["applied"] is False
    assert len(denied) == 3


def test_rapt_stop_only_allows_off_and_zero_not_positive():
    hass, result, denied = asyncio.run(_run_case("blocked", stop=True))
    assert ("switch", "on", HEATER, None) not in hass.service_calls
    assert ("switch", "off", HEATER, None) in hass.service_calls
    assert ("switch", "off", PUMP, None) in hass.service_calls
    assert ("stop", "off", "session-a", None) in hass.service_calls
    assert all(not (call[0] == "number" and call[3] > 0) for call in hass.service_calls if call[0] == "number")
    assert result["applied"] is False
    # Current legacy policy allows a direct pump OFF during confirmed RAPT STOP,
    # while refusing any positive policy actions. It is not a physical OFF proof.
    assert ("policy", "turn_off", PUMP, None) in hass.service_calls
    assert len(denied) == 2


def test_unrelated_fermentation_actuator_is_not_blocked_by_hot_side_guard():
    env = F["_write_allowed"].__globals__
    env["BREWZILLA_ENTITIES"] = ENTITIES
    assert F["_write_allowed"](None, "switch.fermentation_heat_mat", switch_action="on")
