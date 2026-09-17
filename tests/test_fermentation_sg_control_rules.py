"""Regression tests for the pure (not yet wired) SG-control decision engine."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path

MODULE = (
    Path(__file__).resolve().parents[1]
    / "custom_components/brewassistant/fermentation_tracking/sg_control_rules.py"
)


def _rules():
    spec = importlib.util.spec_from_file_location("brewassistant_sg_control_rules", MODULE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _stage(module, *, sg, now, stage=0, pending=None, pending_at=None, last_at=None):
    return module.evaluate_stage(
        stage=stage,
        pending_stage=pending,
        pending_since=pending_at,
        last_observed_at=last_at,
        sg=sg,
        observed_at=now,
        now=now,
        original_gravity=1.060,
    )


def test_fresh_pill_observation_requires_two_distinct_readings():
    rules = _rules()
    now = datetime(2026, 9, 17, 12, tzinfo=timezone.utc)
    first = _stage(rules, sg=1.035, now=now)
    assert first["stage"] == 0
    assert first["pending_stage"] == 1
    assert first["temperature_c"] == 18
    repeated = _stage(
        rules, sg=1.035, now=now, pending=1, pending_at=now, last_at=now
    )
    assert repeated["stage"] == 0
    assert repeated["reason"] == "duplicate_observation"
    second_at = now + timedelta(minutes=5)
    confirmed = _stage(
        rules, sg=1.034, now=second_at, pending=1, pending_at=now, last_at=now
    )
    assert confirmed["stage"] == 1
    assert confirmed["temperature_c"] == 19
    assert confirmed["advanced"] is True


def test_cannot_skip_final_stage_or_regress_after_noise():
    rules = _rules()
    now = datetime(2026, 9, 17, 12, tzinfo=timezone.utc)
    first = _stage(rules, sg=1.019, now=now)
    assert first["pending_stage"] == 1
    assert first["stage"] == 0
    raised = _stage(
        rules, sg=1.019, now=now + timedelta(minutes=10), stage=1
    )
    assert raised["pending_stage"] == 2
    assert raised["stage"] == 1
    rising_noise = _stage(rules, sg=1.040, now=now, stage=2)
    assert rising_noise["stage"] == 2
    assert rising_noise["temperature_c"] == 20.5


def test_untrusted_or_stale_gravity_holds_confirmed_target():
    rules = _rules()
    now = datetime(2026, 9, 17, 12, tzinfo=timezone.utc)
    for value, at, reason in (
        (1.019, now - timedelta(minutes=21), "stale_gravity"),
        (0.5, now, "implausible_gravity"),
        (1.080, now, "above_original_gravity"),
        (1.019, now + timedelta(minutes=2), "future_sample"),
    ):
        outcome = rules.evaluate_stage(
            stage=1,
            pending_stage=None,
            pending_since=None,
            last_observed_at=None,
            sg=value,
            observed_at=at,
            now=now,
            original_gravity=1.060,
        )
        assert outcome["stage"] == 1
        assert outcome["temperature_c"] == 19
        assert outcome["reason"] == reason


def _series(now, *, hours=72, sg=1.014, interval=6):
    return [
        (now - timedelta(hours=hours - step), sg)
        for step in range(0, hours + 1, interval)
    ]


def test_stability_requires_continuous_72_hour_history_near_fg():
    rules = _rules()
    now = datetime(2026, 9, 17, 12, tzinfo=timezone.utc)
    result = rules.evaluate_cold_crash_readiness(
        _series(now), now=now, target_fg=1.014
    )
    assert result["ready"] is True
    assert result["reason"] == "stable_near_fg_waiting_for_operator"
    assert result["span_hours"] == 72

    early = rules.evaluate_cold_crash_readiness(
        _series(now, hours=48), now=now, target_fg=1.014
    )
    assert early["ready"] is False
    assert early["reason"] == "insufficient_time_span"


def test_stability_rejects_gaps_trend_high_fg_and_stale_end():
    rules = _rules()
    now = datetime(2026, 9, 17, 12, tzinfo=timezone.utc)
    cases = (
        ([(now - timedelta(hours=72), 1.014), (now, 1.014)], "insufficient_history"),
        (_series(now, sg=1.019), "not_near_expected_fg"),
        ([(at, 1.013 if i == 0 else 1.015) for i, (at, _) in enumerate(_series(now))], "gravity_still_changing"),
        (_series(now)[:-1], "stale_gravity"),
    )
    for samples, reason in cases:
        outcome = rules.evaluate_cold_crash_readiness(
            samples, now=now, target_fg=1.014
        )
        assert outcome["ready"] is False
        assert outcome["reason"] == reason

    gap = _series(now)[:3] + _series(now)[7:]
    result = rules.evaluate_cold_crash_readiness(
        gap, now=now, target_fg=1.014
    )
    assert result["ready"] is False
    assert result["reason"] == "gaps_in_pill_history"


def test_48_hours_is_allowed_only_when_explicitly_requested():
    rules = _rules()
    now = datetime(2026, 9, 17, 12, tzinfo=timezone.utc)
    result = rules.evaluate_cold_crash_readiness(
        _series(now, hours=48), now=now, target_fg=1.014, stable_hours=48
    )
    assert result["ready"] is True


def test_rules_have_no_hardware_or_external_adapter_dependency():
    source = MODULE.read_text(encoding="utf-8")
    assert "homeassistant" not in source.lower()
    assert "climate.set_temperature" not in source
    assert "switch.turn_on" not in source
    assert "brewfather" not in source.lower().replace("brewfather-side", "")
