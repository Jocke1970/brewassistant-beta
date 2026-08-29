"""Regression checks for automatic Brewday flight recorder v3."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "custom_components/brewassistant/brewday/brewday_audit_autostart.py"


def test_flight_recorder_source_parses() -> None:
    ast.parse(SOURCE.read_text(encoding="utf-8"))


def test_manual_brewday_autostarts_audit_from_prepared_state() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    assert 'MANUAL_RUNTIME_SOURCE = "Manual Brewday"' in source
    assert '"prepared"' in source
    assert 'manual_state in ACTIVE_RUNTIME_STATES' in source
    assert 'async_start_brewday_audit_log' in source


def test_brewfather_and_manual_use_one_persistent_flight_recorder() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    assert 'brewfather_session_active(hass)' in source
    assert 'get_manual_brewday_session(hass).to_snapshot()' in source
    assert 'get_brewday_audit_log(hass).active' in source
    assert 'flight_recorder_transition' in source


def test_new_brewday_rotates_active_flight_recorder() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    assert 'def _last_audit_session_finished' in source
    assert 'last_state in {"completed", "finished"}' in source
    assert 'last_state in {"idle", "inactive"} and last_source in {"", "none"}' in source
    assert 'return True, f"new_brewday:{active_reason}", runtime' in source
    assert 'rotating = reason.startswith("new_brewday:")' in source
    assert 'verb = "rotated" if rotating else "started"' in source
    assert 'prefix = "rotate" if result.get("rotated") else "autostart"' in source


def test_handoff_does_not_define_a_terminal_session_boundary() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    assert 'Manual <-> Brewfather handoffs in one continuous flight-recorder log' in source
    assert 'last_source in {"", "none"}' in source


def test_flight_recorder_captures_ownership_setpoints_and_bz_readback() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    expected = (
        "brewassistant_brewzilla_manual_target_override",
        "brewassistant_brewzilla_allow_heater_control",
        "brewassistant_brewzilla_allow_pump_control",
        "brewassistant_brewzilla_manual_target_temperature",
        "brewassistant_brewzilla_manual_heat_utilization",
        "brewassistant_brewzilla_manual_pump_utilization",
        "number.brewzilla_target_temperature",
        "number.brewzilla_heat_utilization",
        "number.brewzilla_pump_utilization",
        "switch.brewzilla_heater",
        "switch.brewzilla_pump",
        "manual_pause_safe_down_active",
    )
    for token in expected:
        assert token in source


def test_temperature_and_power_are_context_not_event_triggers() -> None:
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    trigger_values: tuple[str, ...] | None = None
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "FLIGHT_RECORDER_TRIGGER_ENTITIES" for target in node.targets):
            continue
        # The tuple contains starred named tuples, so inspect source rather than
        # literal_eval; this still protects the intended no-noise contract.
        segment = ast.get_source_segment(SOURCE.read_text(encoding="utf-8"), node) or ""
        assert '"sensor.brewzilla_temperature"' not in segment
        assert '"sensor.brewzilla_power"' not in segment
        trigger_values = ()
        break
    assert trigger_values == ()
