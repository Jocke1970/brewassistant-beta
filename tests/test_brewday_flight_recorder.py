"""Regression checks for automatic Brewday flight recorder v3."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "custom_components/brewassistant/brewday/brewday_audit_autostart.py"
AUDIT_SOURCE = ROOT / "custom_components/brewassistant/brewday/brewday_audit.py"
BOUNDARY_SOURCE = ROOT / "custom_components/brewassistant/brewday/brewday_audit_session_boundary.py"
BREWDAY_INIT = ROOT / "custom_components/brewassistant/brewday/__init__.py"


def test_flight_recorder_source_parses() -> None:
    ast.parse(SOURCE.read_text(encoding="utf-8"))
    ast.parse(AUDIT_SOURCE.read_text(encoding="utf-8"))
    ast.parse(BOUNDARY_SOURCE.read_text(encoding="utf-8"))


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


def test_deterministic_boundary_guard_is_installed_before_autostart_import() -> None:
    source = BREWDAY_INIT.read_text(encoding="utf-8")
    assert "install_core_ownership_policy()" in source
    assert "install_audit_session_boundary_guard()" in source
    assert source.index("install_core_ownership_policy()") < source.index(
        "install_audit_session_boundary_guard()"
    )


def test_terminal_boundary_is_latched_outside_the_event_log() -> None:
    source = BOUNDARY_SOURCE.read_text(encoding="utf-8")
    assert 'DATA_KEY_BOUNDARY = "brewday_audit_session_boundary"' in source
    assert "def _arm_boundary(" in source
    assert '"log_started_at": _log_started_at(hass)' in source
    assert "def _current_session_is_terminal(" in source
    assert "_runtime_source(hass) == \"\"" in source
    assert "_runtime_state(hass) in TERMINAL_STATES" in source
    assert "_manual_state(hass) in TERMINAL_STATES" in source
    assert "_brewfather_phase(hass) in INACTIVE_BREWFATHER_PHASES" in source


def test_new_manual_and_brewfather_sessions_rotate_only_when_boundary_is_armed() -> None:
    source = BOUNDARY_SOURCE.read_text(encoding="utf-8")
    assert '== "prepared"' in source
    assert "ACTIVE_BREWFATHER_PHASES" in source
    assert "old_phase not in ACTIVE_BREWFATHER_PHASES" in source
    assert "boundary = _boundary(hass)" in source
    assert 'if not boundary or not boundary.get("armed")' in source
    assert "await async_start_brewday_audit_log(hass, note=note)" in source


def test_rotation_guard_detects_existing_rotation_and_avoids_double_rotate() -> None:
    source = BOUNDARY_SOURCE.read_text(encoding="utf-8")
    assert 'armed_started_at = boundary.get("log_started_at")' in source
    assert "current_started_at = _log_started_at(hass)" in source
    assert "current_started_at != armed_started_at" in source
    assert "Another autostart callback already rotated the recorder" in source
    assert "lock = asyncio.Lock()" in source


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


def test_flight_recorder_distinguishes_effective_and_physical_device_target() -> None:
    source = AUDIT_SOURCE.read_text(encoding="utf-8")
    assert 'BREWZILLA_EFFECTIVE_TARGET = "sensor.brewassistant_brewzilla_target_temperature"' in source
    assert 'BREWZILLA_DEVICE_TARGET = "sensor.brewassistant_brewzilla_device_target_temperature"' in source
    assert '"brewzilla_effective_target": _float_state(hass, BREWZILLA_EFFECTIVE_TARGET)' in source
    assert '"brewzilla_device_target": _float_state(hass, BREWZILLA_DEVICE_TARGET)' in source


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
