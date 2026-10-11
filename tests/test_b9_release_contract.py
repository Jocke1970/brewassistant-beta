"""BrewAssistant b9 HACS release / physical sensor-owner contract."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]


def test_b9_release_tag_manifest_and_prerelease_notes():
    manifest = json.loads(
        (ROOT / "custom_components/brewassistant/manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["version"] == "2026.10.0b11"  # b9 notes/tags remain historical
    notes = (ROOT / "docs/2026.10.0b9-prerelease-notes_sv.md").read_text(encoding="utf-8")
    assert "v2026.10.0b9" in notes
    assert "2026.10.0b8" in notes
    assert "2026.10.0b4" in notes
    assert "Pre-release" in notes and "HACS" in notes
    assert "manuellt växla BrewZillas egen reglergivare" in notes
    assert "sensor.brewzilla_temperature" in notes
    assert "BA → RCL" not in notes or "direkta BA→BZ-kommandon" in notes


def test_active_publisher_checks_seven_required_beta_sha_jobs_and_is_prerelease():
    ci = (ROOT / ".github/workflows/b11-hacs-prerelease.yml").read_text(encoding="utf-8")
    assert "2026.10.0b11" in ci
    assert "v2026.10.0b11" in ci
    assert "--prerelease" in ci
    assert "GITHUB_SHA" in ci
    for name in ("quality", "test (3.11)", "test (3.12)", "test (3.13)",
                 "Hassfest", "HACS", "ha-rcl-observer-smoke"):
        assert name in ci
    assert not (ROOT / ".github/workflows/b10-hacs-prerelease.yml").exists()
    assert not (ROOT / ".github/workflows/b9-hacs-prerelease.yml").exists()
    assert not (ROOT / ".github/workflows/b8-hacs-prerelease.yml").exists()
