"""Dashboard regressions found during the 2026-08-29 water-only validation."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CARDS = ROOT / "dashboard" / "cards"


def test_hub_manual_prepare_is_only_visible_when_runtime_idle() -> None:
    for filename in ("brewassistant_hub.yaml", "brewassistant_hub_sv.yaml"):
        source = (CARDS / filename).read_text(encoding="utf-8")
        marker = "name: Prepare Manual Brewday" if filename == "brewassistant_hub.yaml" else "name: Förbered manuell bryggdag"
        pos = source.index(marker)
        block_start = source.rfind("- type: conditional", 0, pos)
        block_end = source.find("- type: custom:button-card", pos + len(marker))
        block = source[block_start:block_end if block_end != -1 else None]
        assert "sensor.brewassistant_brewday_runtime_state" in block
        assert 'state: "idle"' in block
        assert "entity: sensor.brewassistant_manual_brewday_status" in block
        assert "sensor.brewfather_brew_tracker_status" not in block


def test_safety_rcl_card_accepts_canonical_and_legacy_visibility_ids() -> None:
    for filename in ("brewzilla_safety_rcl.yaml", "brewzilla_safety_rcl_sv.yaml"):
        source = (CARDS / filename).read_text(encoding="utf-8")
        assert "switch.brewassistant_show_brewzilla_safety_rcl" in source
        assert "switch.brewassistant_show_safety_rcl" in source
        assert "const visibility =" in source
