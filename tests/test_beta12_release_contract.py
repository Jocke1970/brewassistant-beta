"""Preserve published beta.12 evidence and verify the current beta.13 candidate.

Artifact identity/preservation checks only; not a real HA or hardware test.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLISHED_VERSION = "0.2.0-beta.12"
PUBLISHED_TAG = "v" + PUBLISHED_VERSION
PUBLISHED_NAME = "2026_09-01"
CANDIDATE_VERSION = "0.2.0-beta.13"
CANDIDATE_TAG = "v" + CANDIDATE_VERSION
CANDIDATE_NAME = "2026_09-02"


def test_published_beta12_release_notes_preserve_historical_identity():
    """A new candidate must not repurpose the already published beta.12 notes."""
    notes = (ROOT / "docs/beta12-prerelease-notes_sv.md").read_text(encoding="utf-8")
    assert notes.startswith(f"# BrewAssistant {PUBLISHED_NAME} — beta-prerelease ({PUBLISHED_TAG})")
    assert f"**Releasenamn:** `{PUBLISHED_NAME}`" in notes
    assert f"GitHub-tagg `{PUBLISHED_TAG}`" in notes
    assert f"integrationsmanifest `{PUBLISHED_VERSION}`" in notes
    assert PUBLISHED_TAG in notes
    assert "Create a merge commit" in notes
    assert "HACS" in notes and "water-only" in notes
    assert "beta-mergecommit" in notes and "main" in notes
    assert "78 °C" in notes and "95 °C" in notes
    assert (ROOT / "docs/beta11-prerelease-notes_sv.md").is_file()


def test_current_manifest_and_beta13_notes_have_unique_new_version():
    manifest = json.loads((ROOT / "custom_components/brewassistant/manifest.json").read_text(encoding="utf-8"))
    notes = (ROOT / "docs/beta13-prerelease-notes_sv.md").read_text(encoding="utf-8")
    assert manifest["version"] == CANDIDATE_VERSION
    assert CANDIDATE_VERSION != PUBLISHED_VERSION
    assert notes.startswith(f"# BrewAssistant {CANDIDATE_NAME} — beta ({CANDIDATE_TAG})")
    assert CANDIDATE_TAG in notes and CANDIDATE_VERSION in notes
    assert "v0.5.0-beta.1" in notes
    assert "Create a merge commit" in notes
    assert "Pre-release" in notes and "HACS" in notes
    assert "beta-merge-SHA" in notes and "main" in notes
    assert "STOP" in notes and "ABORT" in notes
    assert "fysiskt" in notes


def test_installer_retains_existing_safety_and_all_new_restrictions():
    installer = (ROOT / "custom_components/brewassistant/brewzilla/__init__.py").read_text(encoding="utf-8")
    identity = (ROOT / "custom_components/brewassistant/brewzilla/brewzilla_rapt_identity_guard.py").read_text(encoding="utf-8")
    assert "_physical_mash_interlock.install_physical_mash_interlock()" in installer
    assert "_rapt_identity_guard.install_rapt_identity_guard()" in installer
    for guard in (
        "brewzilla_sparge_execution_guard.install_sparge_execution_guard()",
        "brewzilla_rapt_brewing_read_isolation.install_rapt_brewing_read_isolation()",
        "brewzilla_sparge_local_target_guard.install_sparge_local_target_guard()",
        "brewzilla_supervised_fallback_guard.install_supervised_fallback_guard()",
        "brewzilla_policy_payload_guard.install_policy_payload_guard()",
        "brewday_rapt_audit_context.install_rapt_audit_context()",
    ):
        assert guard in identity


def test_brewfather_cards_and_hlt_simulation_preserved():
    for suffix in ("", "_sv"):
        card = (ROOT / f"dashboard/cards/brewfather_feed{suffix}.yaml").read_text(encoding="utf-8")
        assert "sensor.brewfather_brew_tracker_status" in card
        assert "brew_tracker_batch_id" in card
        assert "brew_tracker_recipe_name" in card
        assert "climate.fermentation_chamber" in card
        sparge = (ROOT / f"dashboard/cards/rapt_sparge_controls{suffix}.yaml").read_text(encoding="utf-8")
        assert "RAPT BrewZilla Profile" in sparge
    hlt = (ROOT / "custom_components/brewassistant/hlt/runtime.py").read_text(encoding="utf-8")
    trace = (ROOT / "custom_components/brewassistant/hlt/trace.py").read_text(encoding="utf-8")
    assert "build_brewday_runtime_snapshot(hass)" in hlt
    assert "hass.services.async_call" not in hlt
    assert '"physical_writes": False' in trace
