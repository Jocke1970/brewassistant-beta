"""Regression checks for BrewZilla/RCL active hot-side freshness semantics."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INIT = ROOT / "custom_components/brewassistant/brewzilla/__init__.py"
ACTIVE = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_active_rcl_recovery_guard.py"
VALUE = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_rcl_value_recovery_guard.py"
FAIL_PASSIVE = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_fail_passive_guard.py"


def test_control_freshness_uses_report_age_not_value_change_age() -> None:
    source = INIT.read_text(encoding="utf-8")

    assert "def _reported_entity_age_seconds" in source
    assert 'getattr(entity_state, "last_reported", None) or entity_state.last_updated' in source
    assert "def _value_entity_age_seconds" in source
    assert "timestamp: Any = entity_state.last_updated" in source
    assert "_orchestration._entity_age_seconds = _reported_entity_age_seconds" in source
    assert "_learning._age_seconds = _value_entity_age_seconds" in source


def test_value_stagnation_guard_does_not_own_canonical_temperature_freshness() -> None:
    source = VALUE.read_text(encoding="utf-8")

    assert "value stagnation" in source
    assert "_RCL_VALUE_STALE_WARN_SECONDS = 120" in source
    assert '"rcl_value_stale_guard_refresh_delegated": True' in source
    assert "brewzilla_temperature._state_age_seconds" not in source
    assert "homeassistant\",\n                    \"update_entity" not in source


def test_active_hot_side_requests_one_real_coordinator_refresh_every_30_seconds() -> None:
    source = ACTIVE.read_text(encoding="utf-8")

    assert "_ACTIVE_POLL_INTERVAL_SECONDS = 30" in source
    assert '"sensor.brewzilla_temperature"' in source
    assert "return known[:1]" in source
    assert '"homeassistant",\n                    "update_entity"' in source
    assert '"entity_id": entity_ids' in source
    assert 'reason="active_hot_side_poll"' in source
    assert '"rcl_active_hot_side_polling_active": True' in source
    assert '"rcl_active_hot_side_poll_interval_seconds": _ACTIVE_POLL_INTERVAL_SECONDS' in source


def test_hard_rcl_reload_remains_separate_and_throttled() -> None:
    source = ACTIVE.read_text(encoding="utf-8")

    assert "_RELOAD_MIN_INTERVAL_SECONDS = 900" in source
    assert "_HARD_RELOAD_STALE_MULTIPLIER = 3" in source
    assert '"reload_config_entry"' in source
    assert "reload_recently_requested" in source


def test_fail_passive_keeps_short_report_freshness_window() -> None:
    source = FAIL_PASSIVE.read_text(encoding="utf-8")

    # 90 s remains intentionally strict now that an active Brewday asks RCL for
    # a report every 30 s.  It no longer means "the temperature did not change".
    assert "MAX_ACTIVE_CONTROL_DATA_AGE_SECONDS = 90" in source
    assert "process_temperature_stale" in source
