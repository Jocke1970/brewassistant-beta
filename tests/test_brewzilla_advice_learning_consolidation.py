"""Regression checks for the consolidated BrewZilla Brewing Advice card."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CARDS = ROOT / "dashboard/cards"
LEARNING_EN = CARDS / "brewzilla_learning.yaml"
LEARNING_SV = CARDS / "brewzilla_learning_sv.yaml"
ADVICE_EN = CARDS / "brewzilla_advice_auto.yaml"
ADVICE_SV = CARDS / "brewzilla_advice_auto_sv.yaml"


def test_legacy_advice_auto_cards_are_retired() -> None:
    assert not ADVICE_EN.exists()
    assert not ADVICE_SV.exists()


def test_learning_card_is_the_single_advice_and_learning_surface() -> None:
    required = (
        "sensor.brewassistant_brewzilla_learning_recommendation_state",
        "sensor.brewassistant_brewzilla_learning_recommendation_reason",
        "sensor.brewassistant_brewzilla_learning_confidence",
        "sensor.brewassistant_brewzilla_overshoot_risk",
        "sensor.brewassistant_brewzilla_temp_rate",
        "sensor.brewassistant_brewzilla_suggested_heat_utilization",
        "button.brewassistant_brewzilla_learning_apply",
        "button.brewassistant_brewzilla_learning_deny",
        "custom:expander-card",
    )
    for path in (LEARNING_EN, LEARNING_SV):
        source = path.read_text(encoding="utf-8")
        for token in required:
            assert token in source
