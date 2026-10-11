"""0b8 safety regression: Manual service mutations and resync owner masking.

Runs production function bodies with isolated fake HA states; no real equipment.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
ACCESS = ROOT / "custom_components/brewassistant/brewday/manual_brewday_access.py"
MODE = ROOT / "custom_components/brewassistant/brewday/brewday_execution_mode.py"
INIT = ROOT / "custom_components/brewassistant/__init__.py"


class Denied(Exception):
    """Fake HA service rejection."""


def load(path: Path, *names: str):
    module = ast.parse(path.read_text(encoding="utf-8"))
    funcs = [node for node in module.body if isinstance(node, ast.FunctionDef)
             and node.name in names]
    assert {fn.name for fn in funcs} == set(names)
    future = ast.ImportFrom(module="__future__",
                            names=[ast.alias(name="annotations")], level=0)
    ns = {}
    exec(compile(ast.fix_missing_locations(ast.Module(
        body=[future, *funcs], type_ignores=[],
    )), str(path), "exec"), ns)
    return ns


def test_manual_mutation_guards_actual_branch_conditions():
    ns = load(ACCESS, "assert_manual_brewday_mutation_allowed")
    active = dict(abort=False, resync=False, fallback=False,
                  retained=False, rapt=False, brewfather=False)
    calls = []

    def configure(**changes):
        values = {**active, **changes}
        calls.clear()
        ns.update(
            HomeAssistantError=Denied,
            brewday_operator_abort_active=lambda hass: values["abort"],
            execution_mode=type("Mode", (), {
                "resync_required": staticmethod(lambda hass: values["resync"]),
                "fallback_active": staticmethod(lambda hass: values["fallback"]),
                "last_external_mode": staticmethod(
                    lambda hass: "RCL Brewing" if values["retained"] else None
                ),
                "has_external_snapshot": staticmethod(
                    lambda hass, mode: values["retained"]
                ),
            })(),
            build_rapt_profile_runtime_snapshot=lambda hass: (
                {"profile_active": None} if values["rapt"] else None
            ),
            brewfather_session_active=lambda hass: values["brewfather"],
        )
        return ns["assert_manual_brewday_mutation_allowed"]

    for kind in ("abort", "resync", "fallback", "retained", "rapt", "brewfather"):
        gate = configure(**{kind: True})
        with pytest.raises(Denied, match="nekad"):
            gate(object(), action="start")
    configure()(object(), action="prepare")  # no owner/locks permits process preparation


def test_all_manual_services_check_backend_guard_before_mutation():
    tree = ast.parse(INIT.read_text(encoding="utf-8"))
    expected = (
        "prepare", "start", "pause", "next", "start_mash", "start_boil",
        "start_whirlpool", "start_cooling", "finish", "reset",
    )
    handlers = {
        node.name: node for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef)
        and node.name.startswith("_handle_manual_")
    }
    for action in expected:
        fn = handlers[f"_handle_manual_{action}"]
        first = fn.body[0]
        assert isinstance(first, ast.Expr)
        assert isinstance(first.value, ast.Call)
        assert isinstance(first.value.func, ast.Name)
        assert first.value.func.id == "assert_manual_brewday_mutation_allowed"
        assert first.value.keywords[0].arg == "action"
        assert first.value.keywords[0].value.value == action


def test_decorated_resync_cannot_claim_manual_or_reveal_positive_write_flags():
    ns = load(MODE, "_owners", "decorate_snapshot")
    store = {
        "resync_required": True,
        "resync_from_mode": "RCL Brewing",
        "resync_reason": "ha_restart_requires_external_reconciliation",
        "fallback_active": True,
        "fallback_from_mode": "RCL Brewing",
        "last_external_mode": "RCL Brewing",
    }
    ns.update(_store=lambda hass: store,
              MANUAL_BREWING="Manual Brewing",
              BREWFATHER_BREWING="Brewfather Brewing",
              RCL_BREWING="RCL Brewing")
    out = ns["decorate_snapshot"](
        object(), {
            "source": "Manual Brewday", "runtime_state": "idle",
            "target_temperature": 68.0, "time_remaining_minutes": 0,
        },
        "Manual Brewing",
    )
    assert out["source"] == "None"
    assert out["runtime_state"] == "resync_required"
    assert out["recipe_owner"] == "external_owner_unverified"
    assert out["target_owner"] == "external_owner_unverified"
    assert out["fallback_active"] is True
    assert out["resync_from_mode"] == "RCL Brewing"
    assert out["target_temperature"] is None
    assert out["time_remaining_minutes"] is None
    assert store["fallback_active"] is True  # can't silently clear the latch
    for key in ("target_write_allowed_by_mode", "heater_switch_write_allowed_by_mode",
                "heat_utilization_write_allowed_by_mode", "pump_write_allowed_by_mode",
                "direct_brewzilla_control_allowed"):
        assert out[key] is False, key

    aborted = ns["decorate_snapshot"](
        object(), {"source": "None", "runtime_state": "aborted",
                   "target_temperature": 72.0}, "Manual Brewing",
    )
    assert aborted["runtime_state"] == "aborted"
    assert aborted["target_temperature"] is None
    assert aborted["target_write_allowed_by_mode"] is False

    store["resync_required"] = False
    no_external = ns["decorate_snapshot"](
        object(), {"source": "Manual Brewday", "runtime_state": "idle",
                   "target_temperature": 60.0}, "Manual Brewing",
    )
    assert no_external["recipe_owner"] == "brewassistant_manual_recipe"
    assert no_external["target_write_allowed_by_mode"] is True
