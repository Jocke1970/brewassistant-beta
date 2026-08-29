"""Regression checks for process-scoped BrewTracker/Brewfather dashboard roles."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_SENSOR = ROOT / "custom_components/brewassistant/brewday/brewday_runtime_sensor.py"
CARDS = ROOT / "dashboard/cards"


def test_brewfather_batch_phase_sensor_uses_authoritative_ownership_phase() -> None:
    """UI phase must come from the same normalized backend policy as ownership."""
    source = RUNTIME_SENSOR.read_text(encoding="utf-8")
    ast.parse(source)
    assert "from .brewfather_ownership import brewfather_batch_phase" in source
    assert "class BrewAssistantBrewfatherBatchPhaseSensor" in source
    assert 'super().__init__(coordinator, "brewfather_batch_phase")' in source
    assert "return brewfather_batch_phase(self.coordinator.hass)" in source


def test_brewtracker_card_is_limited_to_planning_and_brewing() -> None:
    """BrewTracker is the brewday card, including ready/pre-start states."""
    for filename in ("brewtracker_runtime.yaml", "brewtracker_runtime_sv.yaml"):
        source = (CARDS / filename).read_text(encoding="utf-8")
        assert "sensor.brewassistant_brewfather_batch_phase" in source
        assert 'state: "planning"' in source
        assert 'state: "brewing"' in source
        assert 'state: "fermenting"' not in source
        assert "prestart" in source
        assert "runtime === 'idle'" in source
        assert "String(bfStatus).toLowerCase() === 'paused'" in source


def test_brewfather_card_is_fermentation_batch_context_only() -> None:
    """The former feed card becomes post-brew Brewfather batch context."""
    for filename in ("brewfather_feed.yaml", "brewfather_feed_sv.yaml"):
        source = (CARDS / filename).read_text(encoding="utf-8")
        assert "sensor.brewassistant_brewfather_batch_phase" in source
        assert 'state: "fermenting"' in source
        assert 'state: "planning"' not in source
        assert 'state: "brewing"' not in source
        assert "climate.fermentation_chamber" in source
        assert "brewassistant.force_brewfather_refresh" not in source


def test_old_brewing_equals_ownership_wording_is_gone() -> None:
    """Brewing phase alone must never be presented as the takeover boundary."""
    sv = (CARDS / "brewtracker_runtime_sv.yaml").read_text(encoding="utf-8")
    en = (CARDS / "brewtracker_runtime.yaml").read_text(encoding="utf-8")
    assert "Först då får BrewTracker hot-side ownership" in sv
    assert "Only then can BrewTracker take hot-side ownership" in en
    assert "tar över först när batchen går till <b>Brewing</b>" not in sv
    assert "takes over only when the batch enters <b>Brewing</b>" not in en
