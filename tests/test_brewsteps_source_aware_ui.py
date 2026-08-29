"""Regression checks for the source-aware Brewsteps dashboard surface."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CARDS = ROOT / "dashboard" / "cards"
EN = CARDS / "brewassistant_brewsteps.yaml"
SV = CARDS / "brewassistant_brewsteps_sv.yaml"
MANUAL_EN = CARDS / "brewassistant_manual_brewday.yaml"
MANUAL_SV = CARDS / "brewassistant_manual_brewday_sv.yaml"


def test_brewsteps_cards_exist_as_en_sv_pair() -> None:
    assert EN.is_file()
    assert SV.is_file()


def test_brewsteps_is_brewtracker_owned_and_read_only() -> None:
    for path in (EN, SV):
        source = path.read_text(encoding="utf-8")
        assert "sensor.brewassistant_brewday_runtime_source" in source
        assert 'state: "Brewfather Brew Tracker"' in source
        assert "READ ONLY" in source
        assert "service:" not in source
        assert "brewassistant.manual_brewday_" not in source


def test_brewsteps_uses_normalized_runtime_and_physical_heatstrike_context() -> None:
    for path in (EN, SV):
        source = path.read_text(encoding="utf-8")
        assert "sensor.brewassistant_brewday_runtime_stage" in source
        assert "sensor.brewassistant_brewday_runtime_step" in source
        assert "sensor.brewassistant_brewday_runtime_next_step" in source
        assert "sensor.brewassistant_brewzilla_control_reason" in source
        assert "advice_physical_phase" in source
        assert "pre_mash_in" in source
        for stage_label in ("Heat strike", "Hopstand"):
            assert stage_label in source


def test_manual_brewday_controls_remain_manual_source_only() -> None:
    for path in (MANUAL_EN, MANUAL_SV):
        source = path.read_text(encoding="utf-8")
        assert "sensor.brewassistant_brewday_runtime_source" in source
        assert 'state: "Manual Brewday"' in source
        assert "brewassistant.manual_brewday_start_mash" in source
        assert "brewassistant.manual_brewday_start_boil" in source
