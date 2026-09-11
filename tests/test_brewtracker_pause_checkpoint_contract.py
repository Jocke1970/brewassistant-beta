"""Regression contract for explicit BrewTracker zero-minute PAUS checkpoints."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_brewtracker_pause_checkpoint_guard.py"
PAUSED = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_paused_guard.py"
INIT = ROOT / "custom_components/brewassistant/brewzilla/__init__.py"


def test_checkpoint_is_narrow_brewtracker_paus_convention() -> None:
    source = GUARD.read_text(encoding="utf-8")
    detect = source.split("def _is_explicit_checkpoint", 1)[1].split(
        "def _process_temperature", 1
    )[0]

    assert '"Brewfather Brew Tracker"' in detect
    assert '!= "paused"' in detect
    assert '_CHECKPOINT_PREFIXES = ("paus", "pause")' in source
    assert "name.startswith(_CHECKPOINT_PREFIXES)" in detect
    assert 'runtime.get("time_remaining_seconds")' in detect
    assert "remaining is None or remaining <= 0.0" in detect


def test_checkpoint_uses_current_runtime_target_not_next_step() -> None:
    source = GUARD.read_text(encoding="utf-8")
    apply_body = source.split("def _apply_checkpoint_target", 1)[1].split(
        "def build_orchestration_snapshot", 1
    )[0]

    assert 'runtime.get("target_temperature")' in apply_body
    assert '"requested_target": target' in apply_body
    assert '"requested_target_source": "brewtracker_paused_checkpoint"' in apply_body
    assert '"paused_target_rewind_blocked": False' in apply_body
    assert "next_step" not in apply_body


def test_checkpoint_heat_can_only_be_capped_downward() -> None:
    source = GUARD.read_text(encoding="utf-8")
    apply_body = source.split("def _apply_checkpoint_target", 1)[1].split(
        "def build_orchestration_snapshot", 1
    )[0]

    assert 'advice_control._base_heat_profile("ramp"' in source
    assert "min(existing_heat, heat_cap)" in apply_body
    assert "desired_heat <= base.UTILIZATION_TOLERANCE" in apply_body
    assert 'desired_heater_on = False' in apply_body


def test_checkpoint_does_not_override_independent_safety_blocks() -> None:
    source = GUARD.read_text(encoding="utf-8")
    blocked = source.split("def _independent_block", 1)[1].split(
        "def _checkpoint_heat_cap", 1
    )[0]

    assert 'snapshot.get("abort_lockout_active")' in blocked
    assert 'snapshot.get("execution_desync_active")' in blocked
    assert 'snapshot.get("rcl_freshness_guard_blocking")' in blocked
    assert 'snapshot.get("rcl_degraded")' in blocked
    assert 'not snapshot.get("connected")' in blocked


def test_paused_guard_reopens_only_the_explicit_checkpoint() -> None:
    source = PAUSED.read_text(encoding="utf-8")
    allowed = source.split("def _checkpoint_control_allowed", 1)[1].split(
        "def _paused_hold_maintenance_allowed", 1
    )[0]
    apply_body = source.split("async def async_apply_brewzilla_target_if_allowed", 1)[1].split(
        "def install_paused_guard", 1
    )[0]

    assert 's.get("brewtracker_pause_checkpoint_active")' in allowed
    assert 's.get("brewtracker_pause_checkpoint_control_allowed")' in allowed
    assert 'not s.get("abort_lockout_active")' in allowed
    assert "if _checkpoint_control_allowed(snap):" in apply_body
    assert "return await _BASE_APPLY(hass)" in apply_body
    assert apply_body.index("_checkpoint_control_allowed") < apply_body.index("_paused_hold_maintenance_allowed")


def test_checkpoint_guard_sits_inside_final_fail_passive_boundary() -> None:
    source = INIT.read_text(encoding="utf-8")
    phase = source.index("_phase_authority.install_phase_authority()")
    checkpoint = source.index(
        "_brewtracker_pause_checkpoint_guard.install_brewtracker_pause_checkpoint_guard()"
    )
    rapt = source.index("_rapt_profile_control_bridge.install_rapt_profile_control_bridge()")
    fail_passive = source.index("_fail_passive_guard.install_fail_passive_guard()")

    assert phase < checkpoint < rapt < fail_passive
