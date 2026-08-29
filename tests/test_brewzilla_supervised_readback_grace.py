"""Regression checks for confirmed-plan RCL readback grace."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_supervised_readback_grace.py"
BREWZILLA_INIT = ROOT / "custom_components/brewassistant/brewzilla/__init__.py"


def test_supervised_readback_grace_source_parses() -> None:
    ast.parse(SOURCE.read_text(encoding="utf-8"))


def test_grace_wraps_explicit_confirm_executor_after_supervised_guard() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    init_source = BREWZILLA_INIT.read_text(encoding="utf-8")
    assert "register_supervised_executor" in source
    assert "async def async_execute_confirmed_plan(" in source
    assert "_BASE_EXECUTE = supervised.async_execute_confirmed_plan" in source
    assert "result.get(\"supervised_confirmation_consumed\")" in source
    supervised_pos = init_source.index("_supervised_runtime_guard.install_supervised_runtime_guard()")
    grace_pos = init_source.index("_supervised_readback_grace.install_supervised_readback_grace()")
    assert grace_pos > supervised_pos


def test_grace_is_bounded_and_scoped_to_same_runtime_intent() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    assert "CONFIRMED_READBACK_GRACE_SECONDS = 240" in source
    assert '"runtime_source"' not in source  # context comes from canonical supervised plan payload
    assert "supervised._plan_payload(snapshot, [])" in source
    assert "if not _same_intent(snapshot, grace):" in source
    assert "_clear_grace(hass)" in source
    assert "expires_at" in source


def test_only_confirmed_config_numbers_are_covered_by_grace() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    assert '_CONFIG_ACTION_KEYS = {"target_up", "heat_up", "pump_up"}' in source
    assert 'action.startswith("set_target:")' in source
    assert 'action.startswith("set_heat_utilization:")' in source
    assert 'action.startswith("set_pump_utilization:")' in source
    assert '"heater_on"' not in source.split("_CONFIG_ACTION_KEYS", 1)[1].split("\n", 1)[0]
    assert "_covered_by_grace(positives, grace)" in source


def test_stale_duplicate_config_readback_does_not_write_or_reprompt() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    assert '"apply_result": "confirmed_plan_readback_grace"' in source
    assert "clear_pending_action_from_source(hass, supervised.SOURCE)" in source
    assert '"supervised_runtime_plan_pending": False' in source
    assert '"supervised_readback_grace_active": True' in source
    assert "direct_actions = await supervised._apply_nonpositive_or_manual_actions" in source


def test_abort_never_inherits_confirmed_readback_grace() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    assert 'if snapshot.get("abort_lockout_active"):' in source
    abort_block = source.split('if snapshot.get("abort_lockout_active"):', 1)[1].split(
        'if not _same_intent', 1
    )[0]
    assert "_clear_grace(hass)" in abort_block
    assert "return await _BASE_APPLY(hass)" in abort_block
