"""Regression checks for Brewday operator ABORT and explicit rearm semantics."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ABORT = ROOT / "custom_components/brewassistant/brewday/brewday_operator_abort.py"
OWNERSHIP = ROOT / "custom_components/brewassistant/brewday/brewfather_ownership.py"
RUNTIME = ROOT / "custom_components/brewassistant/brewday/brewday_runtime.py"
RUNTIME_SENSOR = ROOT / "custom_components/brewassistant/brewday/brewday_runtime_sensor.py"
BUTTON = ROOT / "custom_components/brewassistant/button.py"
COORDINATOR = ROOT / "custom_components/brewassistant/coordinator.py"
CARD_EN = ROOT / "dashboard/cards/brewassistant_brewday.yaml"
CARD_SV = ROOT / "dashboard/cards/brewassistant_brewday_sv.yaml"


def test_abort_python_sources_parse() -> None:
    for path in (ABORT, OWNERSHIP, RUNTIME, RUNTIME_SENSOR, BUTTON, COORDINATOR):
        ast.parse(path.read_text(encoding="utf-8"))


def test_operator_abort_is_persisted_and_requires_explicit_rearm() -> None:
    source = ABORT.read_text(encoding="utf-8")
    for token in (
        "Store(hass, STORAGE_VERSION, STORE_KEY)",
        "async_load_brewday_operator_abort",
        '"active": True',
        "async_clear_brewday_operator_abort",
        '"active": False',
        '"control_state"] = "aborted" if state.get("active") else "armed"',
    ):
        assert token in source


def test_persisted_abort_loads_before_any_coordinator_orchestration_tick() -> None:
    source = COORDINATOR.read_text(encoding="utf-8")
    assert "from .brewday.brewday_operator_abort import async_load_brewday_operator_abort" in source
    update = source.split("async def _async_update_data", 1)[1]
    assert "await async_load_brewday_operator_abort(self.hass)" in update
    assert update.index("async_load_brewday_operator_abort") < update.index("maybe_request_brewfather_refresh")
    assert update.index("async_load_brewday_operator_abort") < update.index("async_apply_brewzilla_target_if_allowed")


def test_brewfather_ownership_obeys_operator_abort_latch() -> None:
    source = OWNERSHIP.read_text(encoding="utf-8")
    assert "from .brewday_operator_abort import brewday_operator_abort_active" in source
    function = source.split("def brewfather_hot_side_active", 1)[1].split("def brewfather_cards_visible", 1)[0]
    assert "if brewday_operator_abort_active(hass):\n        return False" in function
    assert function.index("brewday_operator_abort_active") < function.index("brewfather_batch_phase")


def test_brewday_abort_reuses_physical_abort_and_discards_pending_intent() -> None:
    source = BUTTON.read_text(encoding="utf-8")
    abort_class = source.split("class BrewAssistantAbortBrewdayButton", 1)[1].split(
        "class BrewAssistantRearmBrewdayControlButton", 1
    )[0]
    for token in (
        "async_latch_brewday_operator_abort",
        "cancel_pending_action(hass)",
        "get_manual_brewday_session(hass).reset()",
        "await async_abort_brewzilla(hass)",
        '"brewday_abort"',
    ):
        assert token in abort_class

    rearm_class = source.split("class BrewAssistantRearmBrewdayControlButton", 1)[1].split(
        "class BrewAssistantCounterflowChillerReadyButton", 1
    )[0]
    assert "async_clear_brewday_operator_abort" in rearm_class
    assert '"brewday_control_rearmed"' in rearm_class
    assert "async_abort_brewzilla" not in rearm_class


def test_aborted_runtime_is_non_owning_and_visible_to_dashboard() -> None:
    runtime = RUNTIME.read_text(encoding="utf-8")
    sensor = RUNTIME_SENSOR.read_text(encoding="utf-8")
    assert '"source": "None"' in runtime
    assert '"status": "aborted"' in runtime
    assert '"runtime_state": "aborted"' in runtime
    assert '"operator_control_state"' in runtime
    assert '"brewday_operator_control_state": {"field": "operator_control_state"}' in sensor


def test_brewday_dashboard_separates_reject_from_abort() -> None:
    for path in (CARD_EN, CARD_SV):
        source = path.read_text(encoding="utf-8")
        assert "button.brewassistant_abort_brewday" in source
        assert "button.brewassistant_rearm_brewday_control" in source
        assert "sensor.brewassistant_brewday_operator_control_state" in source
        assert "aborted" in source

    en = CARD_EN.read_text(encoding="utf-8")
    sv = CARD_SV.read_text(encoding="utf-8")
    assert "REJECT ACTION" in en
    assert "ABORT BREWDAY" in en
    assert "REARM CONTROL" in en
    assert "AVVISA ÅTGÄRD" in sv
    assert "ABORT BRYGGDAG" in sv
    assert "ÅTERAKTIVERA STYRNING" in sv
