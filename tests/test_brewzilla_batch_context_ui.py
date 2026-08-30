"""Regression checks for BrewZilla Batch Context operator UI."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CARDS = (
    ROOT / "dashboard/cards/brewzilla_batch_context.yaml",
    ROOT / "dashboard/cards/brewzilla_batch_context_sv.yaml",
)


def test_batch_context_cards_expose_manual_overrides_and_effective_context() -> None:
    for path in CARDS:
        source = path.read_text(encoding="utf-8")
        assert "select.brewassistant_brewzilla_learning_context" in source
        assert "number.brewassistant_batch_context_mash_water_l" in source
        assert "number.brewassistant_batch_context_strike_water_l" in source
        assert "number.brewassistant_batch_context_grain_amount_kg" in source
        assert "number.brewassistant_batch_context_grain_temperature_c" in source
        assert "number.brewassistant_batch_context_sparge_water_l" in source
        assert "number.brewassistant_batch_context_pre_boil_volume_l" in source
        assert "sensor.brewassistant_brewzilla_learning_status" in source
        assert "batch_context_source" in source
        assert "mash_water_l" in source


def test_batch_context_card_explains_blank_manual_value_fallback() -> None:
    english = CARDS[0].read_text(encoding="utf-8")
    swedish = CARDS[1].read_text(encoding="utf-8")
    assert "A blank value means" in english
    assert "Ett tomt värde betyder" in swedish
    assert "actual water volume" in english
    assert "faktiska vattenmängden" in swedish
