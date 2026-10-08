"""Dashboard contract for fermentation provider-aware UI."""

from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
CARDS = ROOT / "dashboard/cards"

PROVIDER_CARDS = (
    CARDS / "fermentation_provider.yaml",
    CARDS / "fermentation_provider_sv.yaml",
)
CHAMBER_CARDS = (
    CARDS / "fermentation.yaml",
    CARDS / "fermentation_sv.yaml",
)
GF30_CARDS = (
    CARDS / "gf30_supervised_target.yaml",
    CARDS / "gf30_supervised_target_sv.yaml",
)


def _machine_refs(source: str) -> set[str]:
    return set(
        re.findall(
            r"(?:sensor|select|switch|button|binary_sensor|climate)\.[a-z0-9_]+",
            source,
        )
    )


def test_provider_selector_card_exists_in_both_languages() -> None:
    for path in PROVIDER_CARDS:
        source = path.read_text(encoding="utf-8")
        assert "select.brewassistant_fermentation_provider" in source
        assert "sensor.brewassistant_fermentation_provider" in source
        assert "sensor.brewassistant_fermentation_provider_status" in source
        assert "switch.brewassistant_show_fermentation" in source


def test_provider_cards_have_machine_reference_parity() -> None:
    en = PROVIDER_CARDS[0].read_text(encoding="utf-8")
    sv = PROVIDER_CARDS[1].read_text(encoding="utf-8")

    assert _machine_refs(en) == _machine_refs(sv)


def test_chamber_cards_are_hidden_when_gf30_is_selected() -> None:
    for path in CHAMBER_CARDS:
        source = path.read_text(encoding="utf-8")
        assert "sensor.brewassistant_fermentation_provider" in source
        assert 'state: "fermentation_chamber"' in source


def test_gf30_cards_are_hidden_when_chamber_is_selected() -> None:
    for path in GF30_CARDS:
        source = path.read_text(encoding="utf-8")
        assert source.startswith("type: conditional\n")
        assert "sensor.brewassistant_fermentation_provider" in source
        assert 'state: "grainfather_gf30"' in source
        assert "switch.brewassistant_show_fermentation" in source


def test_provider_ui_never_uses_human_label_as_machine_condition() -> None:
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (*PROVIDER_CARDS, *CHAMBER_CARDS, *GF30_CARDS)
    )

    assert 'state: "Temperaturkontrollerat jässkåp"' not in combined
    assert 'state: "Grainfather GF30"' not in combined
