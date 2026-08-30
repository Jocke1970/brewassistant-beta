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


def test_brewday_supervised_action_row_is_only_rendered_for_real_pending_action() -> None:
    """CONFIRM/REJECT should disappear completely when no operator action is pending."""
    expected_guard = '''    - type: conditional
      conditions:
        - entity: sensor.brewassistant_brewzilla_pending_action
          state_not: "unknown"
        - entity: sensor.brewassistant_brewzilla_pending_action
          state_not: "unavailable"
        - entity: sensor.brewassistant_brewzilla_pending_action
          state_not: "none"
        - entity: sensor.brewassistant_brewzilla_pending_action
          state_not: "idle"
      card:
        type: horizontal-stack
'''

    for filename in ("brewassistant_brewday.yaml", "brewassistant_brewday_sv.yaml"):
        source = (CARDS_DIR / filename).read_text(encoding="utf-8")
        assert expected_guard in source
        assert "button.brewassistant_confirm_supervised_apply" in source
        assert "button.brewassistant_cancel_supervised_apply" in source


def test_legacy_mash_circulation_fallback_is_tightly_scoped() -> None:
    """The compatibility circulation button belongs only to post-mash-in active Mash."""
    for filename in ("brewzilla_mash_in_confirm.yaml", "brewzilla_mash_in_confirm_sv.yaml"):
        source = (CARDS_DIR / filename).read_text(encoding="utf-8")
        assert "sensor.brewassistant_brewday_runtime_state" in source
        assert "sensor.brewassistant_brewday_runtime_stage" in source
        assert "runtimeStage.includes('mash')" in source
        assert "const pumpStopped = !pumpOn && !Number.isNaN(util) && util <= 0.1;" in source
        assert "(!pending && completed && activeMash && pumpStopped)" in source


def test_brewzilla_direct_service_controls_are_idle_only() -> None:
    """Direct heater/pump/target/safe-down controls must not compete with active Brewday ownership."""
    idle_guard = '''        - condition: state
          entity: sensor.brewassistant_brewday_runtime_state
          state: "idle"
'''

    for filename in ("brewzilla.yaml", "brewzilla_sv.yaml"):
        source = (CARDS_DIR / filename).read_text(encoding="utf-8")
        assert source.count(idle_guard) >= 2
        assert "switch.brewzilla_heater" in source
        assert "switch.brewzilla_pump" in source
        assert "brewassistant.apply_brewzilla_target" in source
        assert "brewassistant.abort_brewzilla" in source
        assert "BZ SAFE-DOWN" in source
