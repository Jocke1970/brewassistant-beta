"""Keep the exact beta candidate's version, test notes and safety graph aligned.

This is an artifact identity/preservation check, not a real HA or hardware test.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.2.0-beta.12"
TAG = "v" + VERSION


def test_manifest_and_new_release_notes_have_same_unique_version():
    manifest = json.loads((ROOT / "custom_components/brewassistant/manifest.json").read_text(encoding="utf-8"))
    notes = (ROOT / "docs/beta12-prerelease-notes_sv.md").read_text(encoding="utf-8")
    assert manifest["version"] == VERSION
    assert f"BrewAssistant v{VERSION}" in notes
    assert TAG in notes
    assert "Create a merge commit" in notes
    assert "HACS" in notes and "water-only" in notes
    assert "beta-mergecommit" in notes and "main" in notes
    assert "78 °C" in notes and "95 °C" in notes
    assert (ROOT / "docs/beta11-prerelease-notes_sv.md").is_file()


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
