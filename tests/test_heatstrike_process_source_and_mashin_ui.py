"""Regression contracts from the 2026-08-30 physical Heatstrike test."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPERATURE = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_temperature.py"
MASH_IN_GATE = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_mash_in_gate.py"
MASH_IN_CARDS = (
    ROOT / "dashboard/cards/brewzilla_mash_in_confirm.yaml",
    ROOT / "dashboard/cards/brewzilla_mash_in_confirm_sv.yaml",
)


def test_auto_process_source_is_latched_during_active_hot_side() -> None:
    source = TEMPERATURE.read_text(encoding="utf-8")

    assert "def _hot_side_process_sensor_owned" in source
    assert "def _resolve_auto_with_hot_side_ownership" in source
    assert '"latched_auto_entity"' in source
    assert '"verified_external_entities"' in source
    assert "_basic_external_usable(latched)" in source
    assert '"active_hot_side_latches_verified_external_source_across_convergence": True' in source
    assert '"mash_temperature_source_lock_active": source_lock_active' in source


def test_hot_side_source_lock_is_released_at_boil_or_later() -> None:
    source = TEMPERATURE.read_text(encoding="utf-8")

    assert 'BREWDAY_RUNTIME_STAGE_SENSOR = "sensor.brewassistant_brewday_runtime_stage"' in source
    assert '_RELEASE_STAGE_WORDS = ("boil", "kok", "chill", "kyl", "transfer", "cleanup", "rengör")' in source
    assert 'if "pre-boil" in combined or "pre boil" in combined or "förkok" in combined:' in source
    assert 'return not any(word in combined for word in _RELEASE_STAGE_WORDS)' in source


def test_latched_external_source_may_fallback_without_losing_identity() -> None:
    source = TEMPERATURE.read_text(encoding="utf-8")
    resolver_body = source.split("def _resolve_auto_with_hot_side_ownership", 1)[1].split(
        "def brewzilla_temperature_snapshot", 1
    )[0]

    assert 'store["latched_auto_entity"] = None' in resolver_body  # only outside active ownership
    assert "latched_external_temporarily_unusable" in resolver_body
    assert "return fallback, True" in resolver_body
    assert '"latched_external_may_fallback_when_stale_or_unavailable": True' in source


def test_mash_in_backend_has_distinct_started_and_complete_actions() -> None:
    source = MASH_IN_GATE.read_text(encoding="utf-8")
    assert "async def async_mark_mash_in_started" in source
    assert '"state": STARTED_STATE' in source
    assert '"desired_pump_on": False' in source
    assert '"desired_pump_utilization": PUMP_OFF_UTILIZATION' in source
    assert "async def async_confirm_mash_in_complete" in source


def test_mash_in_cards_call_started_before_complete() -> None:
    for path in MASH_IN_CARDS:
        source = path.read_text(encoding="utf-8")
        started_pos = source.index("button.brewassistant_mash_in_started")
        complete_pos = source.index("button.brewassistant_mash_in_complete")

        assert started_pos < complete_pos, f"started action must precede complete in {path.name}"
        assert "entity: button.brewassistant_mash_in_started" in source
        assert "entity_id: button.brewassistant_mash_in_started" in source
        assert "gate?.attributes?.state === 'mash_in_started'" in source
        assert "entity: button.brewassistant_mash_in_complete" in source
