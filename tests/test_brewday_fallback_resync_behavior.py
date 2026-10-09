"""Behavior tests for retained Brewday fallback; no HA hardware calls.

Exercise the actual Python function bodies in a controlled runtime instead of
testing only source substrings. Unverified reconnects must not grant ownership.
"""

from __future__ import annotations

import ast
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from pathlib import Path
from types import ModuleType, SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
EXEC = ROOT / "custom_components/brewassistant/brewday/brewday_execution_mode.py"
AUTH = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_source_authority_runtime.py"


def load_functions(path: Path, *names: str) -> dict:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    functions = [
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in names
    ]
    assert {node.name for node in functions} == set(names)
    future = ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)
    namespace = {}
    exec(compile(ast.fix_missing_locations(ast.Module(
        body=[future, *functions], type_ignores=[],
    )), str(path), "exec"), namespace)
    return namespace


F = load_functions(
    EXEC, "_identity_mismatch", "_block_reconnect",
    "external_reconnect_allowed", "reconnect_lockout_snapshot",
    "_prime_manual_fallback_plan",
)
F["_identity_mismatch"].__globals__.update(
    RCL_BREWING="RCL Brewing", BREWFATHER_BREWING="Brewfather Brewing",
)


def rcl_snapshot(*, session="session-A", step_id="step-1", step="Mash", number=1):
    return {
        "source": "RAPT BrewZilla Profile",
        "profile_session_id": session,
        "profile_id": "recipe-1",
        "profile_step_id": step_id,
        "profile_step_number": number,
        "stage": "RAPT Profile",
        "step": step,
        "raw_step_name": step,
    }


def test_rcl_reconnect_requires_original_session_and_step_identity():
    match = rcl_snapshot()
    check = F["_identity_mismatch"]
    assert check(match, deepcopy(match), "RCL Brewing") is None
    assert check(match, rcl_snapshot(session="session-B"), "RCL Brewing") == "rcl_profile_or_session_changed"
    assert check(match, rcl_snapshot(step_id="step-2"), "RCL Brewing") == "rcl_step_changed_during_outage"
    assert check(match, rcl_snapshot(number=2), "RCL Brewing") == "rcl_step_changed_during_outage"
    assert check(match, rcl_snapshot(step="Boil"), "RCL Brewing") == "external_stage_or_step_changed"
    missing_id = {**match, "profile_session_id": None}
    assert check(missing_id, match, "RCL Brewing") == "rcl_session_identity_unverified"


def test_brewfather_reconnect_never_infers_session_from_recipe_or_step():
    check = F["_identity_mismatch"]
    cached = {"stage": "Mash", "step": "Rest", "brewfather_batch_identity": None}
    assert check(cached, deepcopy(cached), "Brewfather Brewing") == "brewfather_reconnect_requires_operator_ack"
    old = {**cached, "brewfather_batch_identity": "batch-10"}
    assert check(old, {**old, "brewfather_batch_identity": "batch-11"}, "Brewfather Brewing") == "brewfather_reconnect_requires_operator_ack"
    assert check(old, deepcopy(old), "Brewfather Brewing") == "brewfather_reconnect_requires_operator_ack"


def test_reconnect_latches_on_local_progress_or_changed_source():
    store = {
        "fallback_active": True,
        "fallback_from_mode": "RCL Brewing",
        "external_snapshots": {"RCL Brewing": {"snapshot": rcl_snapshot()}},
    }
    ns = F["external_reconnect_allowed"].__globals__
    ns.update(
        _store=lambda hass: store,
        _manual_fallback_has_advanced=lambda hass: False,
        _identity_mismatch=F["_identity_mismatch"],
        _block_reconnect=F["_block_reconnect"],
        MANUAL_BREWING="Manual Brewing",
        RCL_BREWING="RCL Brewing",
        BREWFATHER_BREWING="Brewfather Brewing",
        _schedule_context_save=lambda hass: None,
    )
    assert F["external_reconnect_allowed"](object(), rcl_snapshot(), "RCL Brewing") is True
    ns["_manual_fallback_has_advanced"] = lambda hass: True
    assert F["external_reconnect_allowed"](object(), rcl_snapshot(), "RCL Brewing") is False
    assert store["resync_required"] is True
    assert store["resync_reason"] == "manual_plan_advanced_during_outage"
    ns["_manual_fallback_has_advanced"] = lambda hass: False
    assert F["external_reconnect_allowed"](object(), rcl_snapshot(), "RCL Brewing") is False


def test_rcl_session_swap_between_polls_also_latches():
    store = {
        "fallback_active": False,
        "last_external_mode": "RCL Brewing",
        "external_snapshots": {"RCL Brewing": {"snapshot": rcl_snapshot()}},
    }
    ns = F["external_reconnect_allowed"].__globals__
    ns.update(
        _store=lambda hass: store,
        _block_reconnect=F["_block_reconnect"],
        _schedule_context_save=lambda hass: None,
    )
    assert F["external_reconnect_allowed"](
        object(), rcl_snapshot(session="session-B"), "RCL Brewing",
    ) is False
    assert store["resync_required"] is True
    assert store["resync_reason"] == "rcl_session_changed_without_verified_stop"

def test_blocked_reconnect_has_no_source_or_target_ownership():
    store = {"resync_required": True, "resync_reason": "rcl_session_identity_unverified"}
    ns = F["reconnect_lockout_snapshot"].__globals__
    ns.update(
        _store=lambda hass: store,
        decorate_snapshot=lambda hass, data, mode, **kwargs: {
            **data, "brewday_mode": mode, "fallback_active": True,
        },
        MANUAL_BREWING="Manual Brewing",
    )
    snapshot = F["reconnect_lockout_snapshot"](
        object(), {**rcl_snapshot(), "target_temperature": 66.0}, "RCL Brewing"
    )
    assert snapshot["source"] == "None"
    assert snapshot["target_temperature"] is None
    assert snapshot["direct_brewzilla_control_allowed"] is False
    assert snapshot["resync_required"] is True
    assert snapshot["reconnect_expected"] is False


class ManualRuntimeState(StrEnum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    AWAITING_CONFIRM = "awaiting_confirm"


def test_paused_fallback_preserves_remaining_and_running_preserves_elapsed(monkeypatch):
    package = "custom_components.brewassistant.brewday"
    recipe_mod = ModuleType(package + ".brewday_recipe_fallback")
    recipe_mod.plan_from_external_snapshot = lambda snap: SimpleNamespace(
        stages=(SimpleNamespace(steps=[SimpleNamespace(duration_seconds=600)]),),
    )
    recipe_mod.active_position_from_snapshot = lambda snap, plan: (0, 0)
    manual_mod = ModuleType(package + ".manual_brewday_runtime")
    manual_mod.ManualRuntimeState = ManualRuntimeState
    session = SimpleNamespace(
        _guard_enabled=True, state=ManualRuntimeState.IDLE,
        active_stage_index=0, active_step_index=0, step_started_at=None,
        paused_at=None, remaining_when_paused=None,
    )
    session.active_step = SimpleNamespace(duration_seconds=600)
    store_mod = ModuleType(package + ".manual_brewday_store")
    store_mod.get_manual_brewday_session = lambda hass: session
    monkeypatch.setitem(__import__("sys").modules, recipe_mod.__name__, recipe_mod)
    monkeypatch.setitem(__import__("sys").modules, manual_mod.__name__, manual_mod)
    monkeypatch.setitem(__import__("sys").modules, store_mod.__name__, store_mod)

    ns = F["_prime_manual_fallback_plan"].__globals__
    ns.update(
        __package__=package,
        timedelta=timedelta,
        _store=lambda hass: {},
        dt_util=SimpleNamespace(utcnow=lambda: datetime(2026, 10, 9, 12, tzinfo=timezone.utc)),
    )
    for state in ("paused", "running"):
        assert F["_prime_manual_fallback_plan"](
            object(), {
                "runtime_state": state,
                "current_step_remaining_seconds": 240,
            },
        )
        if state == "paused":
            assert session.state == ManualRuntimeState.PAUSED
            assert session.remaining_when_paused == 240
            assert session.step_started_at is None
        else:
            assert session.state == ManualRuntimeState.RUNNING
            assert session.remaining_when_paused is None
            assert (datetime(2026, 10, 9, 12, tzinfo=timezone.utc)
                    - session.step_started_at).total_seconds() == 360


def test_authority_revoked_even_if_fallback_snapshot_says_manual():
    ns = load_functions(AUTH, "_live_authority")
    fn = ns["_live_authority"]
    env = fn.__globals__
    env.update(
        brewday_runtime=SimpleNamespace(
            build_brewday_runtime_snapshot=lambda hass: {
                "source": "Manual Brewday", "fallback_active": True,
            },
        ),
        rapt_profile_runtime=SimpleNamespace(_profile_state=lambda hass: None),
        brewday_operator_abort_snapshot=lambda hass: {"active": False},
        resolve_hot_side_authority=lambda *args, **kwargs: SimpleNamespace(
            mode="manual_legacy_unresolved", may_write_brewzilla=None,
        ),
        HotSideAuthority=lambda mode, may_write_brewzilla, reason, write_scope:
            SimpleNamespace(mode=mode, may_write_brewzilla=may_write_brewzilla,
                            reason=reason, write_scope=write_scope),
    )
    decision, _ = fn(object())
    assert decision.may_write_brewzilla is False
    assert decision.write_scope == "none"
    assert decision.reason == "external_source_lost_manual_plan_observe_only"
