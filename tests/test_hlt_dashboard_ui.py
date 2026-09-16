"""Static checks for the separate HLT visualization card (no HA dependency)."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARDS = ROOT / "dashboard" / "cards"
SENSORS = (ROOT / "custom_components" / "brewassistant" / "hlt" / "sensor.py").read_text(encoding="utf-8")
EN = CARDS / "hlt_power_dashboard.yaml"
SV = CARDS / "hlt_power_dashboard_sv.yaml"
REF = re.compile(r"sensor\.brewassistant_hlt_([a-z0-9_]+)")


def test_hlt_dashboard_mirrors_and_backend_entity_contract():
    assert EN.is_file() and SV.is_file()
    english = EN.read_text(encoding="utf-8")
    swedish = SV.read_text(encoding="utf-8")
    references = set(REF.findall(english))
    assert references == set(REF.findall(swedish))
    assert len(references) >= 25
    for name in references:
        assert f'"hlt_{name}":' in SENSORS, f"Unknown HLT backend entity: {name}"
    english_updates = set(re.findall(r"(?m)^  - (sensor\.brewassistant_hlt_[a-z0-9_]+)$", english))
    swedish_updates = set(re.findall(r"(?m)^  - (sensor\.brewassistant_hlt_[a-z0-9_]+)$", swedish))
    assert english_updates == swedish_updates
    assert len(english_updates) >= 25


def test_hlt_dashboard_is_read_only_and_explicit_about_simulation():
    for path in (EN, SV):
        text = path.read_text(encoding="utf-8")
        assert text.startswith("# HLT")
        assert text.count("action: none") == 3
        assert "service:" not in text
        assert "perform_action:" not in text
        assert "button.brewassistant_" not in text
        assert "switch.sparge_heater" not in text
        assert "number.brewzilla_heat_utilization" not in text
        assert "sensor.brewassistant_hlt_actual_energy_recipient" in text
        assert "sensor.brewassistant_hlt_virtual_energy_recipient" in text
        assert "sensor.brewassistant_hlt_power_observed" in text
        assert "sensor.brewassistant_hlt_power_virtual" in text
        assert "sensor.brewassistant_hlt_total_session_seconds" in text
        assert "sensor.brewassistant_hlt_virtual_heating_seconds" in text
        assert "sensor.brewassistant_hlt_observed_heating_estimate_seconds" in text
        assert "sensor.brewassistant_hlt_temperature_source" in text
        assert "thermostat_calibrated_estimate" in text
        assert "No physical" in text or "Inga fysiska" in text


def test_hlt_dashboard_never_casts_missing_power_to_zero_or_claims_safe_headroom():
    for path in (EN, SV):
        text = path.read_text(encoding="utf-8")
        assert "if (value === null) return null;" in text
        assert "value == null" in text
        assert "['unknown', 'unavailable', 'none', '']" in text
        assert "n === null ? '—'" in text
        assert "budget === null" in text
        assert "NO CONTROL" in text or "INGEN STYRNING" in text
        assert "NOT authorization" in text or "EJ starttillstånd" in text
        assert "30 s" in text
        assert "JSONL" in text
