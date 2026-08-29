"""Regression checks for #157 physical Brewday timing telemetry."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TIMING = ROOT / "custom_components/brewassistant/brewday/brewday_physical_timing.py"
RUNTIME_SENSOR = ROOT / "custom_components/brewassistant/brewday/brewday_runtime_sensor.py"
CARD = ROOT / "dashboard/cards/brewday_physical_timing.yaml"
CARD_SV = ROOT / "dashboard/cards/brewday_physical_timing_sv.yaml"


def test_physical_timing_is_read_only_and_not_in_control_path() -> None:
    source = TIMING.read_text(encoding="utf-8")
    assert '"read_only": True' in source
    assert '"control_side_effects": False' in source
    assert "async_apply_brewzilla" not in source
    assert "number.set_value" not in source
    assert "switch.turn" not in source
    assert "brewzilla_orchestration" not in source


def test_hold_starts_in_target_band_and_requires_mash_in_complete() -> None:
    source = TIMING.read_text(encoding="utf-8")
    assert 'abs(current_temp - target) <= TARGET_TOLERANCE_C' in source
    assert 'reached and runtime_state != "paused" and _mash_in_complete(hass)' in source
    assert 'active["timer_started_at"] = now.isoformat()' in source
    assert 'active["target_reached_at"] = now.isoformat()' in source


def test_ramp_uses_physical_target_and_records_rate() -> None:
    source = TIMING.read_text(encoding="utf-8")
    assert 'current_temp >= target - TARGET_TOLERANCE_C' in source
    assert '"wall_duration_seconds"' in source
    assert '"average_c_per_min"' in source
    assert '"process_temperature_source"' in source
    assert '"context"' in source


def test_pause_freezes_active_timer_and_source_race_is_visible() -> None:
    source = TIMING.read_text(encoding="utf-8")
    assert 'active["pause_started_at"] = now.isoformat()' in source
    assert 'elapsed = max(0.0, wall - paused)' in source
    assert '"source_schedule_mismatch": source_mismatch' in source
    assert "Preserve the physical timer even if Brewfather's schedule races" in source


def test_physical_timing_sensors_are_registered() -> None:
    source = RUNTIME_SENSOR.read_text(encoding="utf-8")
    assert "from .brewday_physical_timing import create_brewday_physical_timing_sensors" in source
    assert "+ create_brewday_physical_timing_sensors(coordinator)" in source


def test_physical_timing_dashboard_has_sv_mirror_and_expander() -> None:
    for path in (CARD, CARD_SV):
        source = path.read_text(encoding="utf-8")
        assert "type: custom:expander-card" in source
        assert "sensor.brewassistant_brewday_physical_timing_summary" in source
        assert "sensor.brewassistant_brewday_physical_remaining_seconds" in source
        assert "source_schedule_mismatch" in source
        assert "history" in source
