"""Regression checks for physical Brewday ramp timing semantics."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BREWDAY_INIT = ROOT / "custom_components/brewassistant/brewday/__init__.py"
BASE_TIMING = ROOT / "custom_components/brewassistant/brewday/brewday_physical_timing.py"
PATCH = ROOT / "custom_components/brewassistant/brewday/brewday_physical_timing_phase_patch.py"


def test_physical_timing_patch_is_installed() -> None:
    source = BREWDAY_INIT.read_text(encoding="utf-8")
    assert "install_physical_timing_phase_patch" in source
    assert "install_physical_timing_phase_patch()" in source


def test_ramp_candidate_does_not_start_equipment_clock() -> None:
    source = PATCH.read_text(encoding="utf-8")
    assert 'active["timer_started_at"] = None' in source
    assert 'active["physical_start_pending"] = True' in source
    assert '"waiting_for_physical_start"' in source
    assert 'snapshot["elapsed_seconds"] = 0' in source
    assert 'snapshot["average_c_per_min"] = None' in source


def test_physical_ramp_start_requires_applied_target_and_actuation_or_motion() -> None:
    source = PATCH.read_text(encoding="utf-8")
    assert "target_applied = bool(" in source
    assert "abs(device_target - target) <= _TARGET_TOLERANCE_C" in source
    assert "energized = bool(heater_on and heat is not None and heat > 0.1)" in source
    assert "return bool(target_applied and (energized or moved))" in source
    assert 'active["physical_started_at"] = now.isoformat()' in source
    assert 'active["start_temperature"] = current_temp' in source


def test_source_schedule_pause_does_not_freeze_active_ramp() -> None:
    source = PATCH.read_text(encoding="utf-8")
    assert 'if active.get("kind") == "ramp":' in source
    assert 'active["pause_started_at"] = None' in source
    assert 'snapshot["source_schedule_paused"] = runtime_paused' in source
    assert 'snapshot["physical_ramp_clock_follows_source_pause"] = False' in source
    assert 'mode.removesuffix("_paused")' in source


def test_hold_target_semantics_and_abort_remain_in_base_timing() -> None:
    source = BASE_TIMING.read_text(encoding="utf-8")
    assert 'if kind == "hold" and active.get("timer_started_at") is None:' in source
    assert 'if reached and runtime_state != "paused" and _mash_in_complete(hass):' in source
    assert 'if runtime_state == "aborted":' in source
    assert 'active["aborted"] = True' in source


def test_timing_patch_is_read_only() -> None:
    source = PATCH.read_text(encoding="utf-8")
    for forbidden in ("number.set_value", "switch.turn_on", "switch.turn_off", "async_call("):
        assert forbidden not in source
