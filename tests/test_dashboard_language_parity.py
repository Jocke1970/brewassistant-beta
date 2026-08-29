"""Regression checks for canonical English and Swedish dashboard mirrors."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_DIR = ROOT / "dashboard"
CARDS_DIR = DASHBOARD_DIR / "cards"

ENTITY_REF_RE = re.compile(
    r"\b(?:sensor|binary_sensor|switch|number|select|button|climate|update|"
    r"input_boolean|input_number|input_select|input_button|script|automation)\."
    r"[a-z0-9_]+\b"
)
ACTION_REF_RE = re.compile(
    r"(?m)^\s*(?:service|perform_action):\s*([a-z0-9_]+\.[a-z0-9_]+)\s*$"
)


def _canonical_cards() -> dict[str, Path]:
    """Return canonical English dashboard cards keyed by stem."""
    return {
        path.stem: path
        for path in CARDS_DIR.glob("*.yaml")
        if not path.stem.endswith("_sv")
    }


def _swedish_cards() -> dict[str, Path]:
    """Return Swedish dashboard mirrors keyed by canonical stem."""
    return {
        path.stem.removesuffix("_sv"): path
        for path in CARDS_DIR.glob("*_sv.yaml")
    }


def _refs(path: Path, pattern: re.Pattern[str]) -> set[str]:
    """Extract stable machine references from a dashboard file."""
    return set(pattern.findall(path.read_text(encoding="utf-8")))


def test_every_dashboard_card_has_swedish_mirror() -> None:
    """Every canonical dashboard card must have exactly one Swedish mirror."""
    canonical = _canonical_cards()
    swedish = _swedish_cards()

    assert canonical, "No canonical dashboard cards found"
    assert canonical.keys() == swedish.keys(), (
        "Dashboard EN/SV filename mismatch. "
        f"Missing Swedish: {sorted(canonical.keys() - swedish.keys())}; "
        f"orphan Swedish: {sorted(swedish.keys() - canonical.keys())}"
    )


def test_sanity_dashboard_has_swedish_mirror() -> None:
    """The post-restart sanity dashboard must also have a Swedish mirror."""
    assert (DASHBOARD_DIR / "brewassistant_sanity.yaml").is_file()
    assert (DASHBOARD_DIR / "brewassistant_sanity_sv.yaml").is_file()


def test_swedish_cards_do_not_introduce_new_entity_references() -> None:
    """Swedish presentation must not invent or translate machine entity IDs."""
    for stem, canonical_path in _canonical_cards().items():
        swedish_path = CARDS_DIR / f"{stem}_sv.yaml"
        canonical_refs = _refs(canonical_path, ENTITY_REF_RE)
        swedish_refs = _refs(swedish_path, ENTITY_REF_RE)
        unexpected = swedish_refs - canonical_refs

        assert not unexpected, (
            f"{swedish_path.name} introduces entity references not present in "
            f"{canonical_path.name}: {sorted(unexpected)}"
        )


def test_swedish_cards_keep_same_action_references() -> None:
    """Localized cards must call the same Home Assistant actions as canonical UI."""
    for stem, canonical_path in _canonical_cards().items():
        swedish_path = CARDS_DIR / f"{stem}_sv.yaml"
        canonical_actions = _refs(canonical_path, ACTION_REF_RE)
        swedish_actions = _refs(swedish_path, ACTION_REF_RE)

        assert canonical_actions == swedish_actions, (
            f"{swedish_path.name} action references differ from "
            f"{canonical_path.name}: EN={sorted(canonical_actions)}, "
            f"SV={sorted(swedish_actions)}"
        )


def test_brewday_confirm_attention_is_pending_driven_and_reduced_motion_safe() -> None:
    """The general Brewday CONFIRM control must only pulse for a pending plan."""
    for filename in ("brewassistant_brewday.yaml", "brewassistant_brewday_sv.yaml"):
        source = (CARDS_DIR / filename).read_text(encoding="utf-8")
        assert "sensor.brewassistant_brewzilla_pending_action" in source
        assert "ba-confirm-pulse" in source
        assert "1.4s ease-in-out infinite" in source
        assert "prefers-reduced-motion: reduce" in source
        assert "animation: none !important" in source
