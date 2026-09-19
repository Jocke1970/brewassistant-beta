"""RAPT Sparge is observational until external-owner write isolation exists."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CARDS = ROOT / "dashboard" / "cards"


def test_sparge_observer_is_a_separate_localized_read_only_card() -> None:
    """Both variants have identical read surfaces and no actuator actions."""
    refs = (
        "binary_sensor.brewzilla_profile_active",
        "switch.brewzilla_heater",
        "switch.brewzilla_pump",
        "number.brewzilla_heat_utilization",
        "number.brewzilla_pump_utilization",
        "number.brewzilla_target_temperature",
    )
    for name in ("rapt_sparge_observer.yaml", "rapt_sparge_observer_sv.yaml"):
        source = (CARDS / name).read_text(encoding="utf-8")
        assert "type: custom:button-card" in source
        assert "rapt_cloud_link_brewzilla_profile_runtime" in source
        assert "attrs.ba_source" in source
        assert "attrs.step_name" in source
        assert "['sparge', 'lakning'].includes(step)" in source
        assert "attrs.step_end_type" in source
        assert "action: more-info" in source
        for ref in refs:
            assert ref in source
        for forbidden in (
            "action: perform-action",
            "action: call-service",
            "action: toggle",
            "perform_action:",
            "service:",
            "button.press",
            "switch.turn_on",
            "switch.turn_off",
            "number.set_value",
            "brewassistant.apply_brewzilla_target",
            "11,38",
            "11.38",
        ):
            assert forbidden not in source, f"{name}: {forbidden}"


def test_sparge_observer_docs_do_not_claim_write_isolation() -> None:
    source = (ROOT / "docs" / "rapt-sparge-observer-2026-09-19_sv.md").read_text(encoding="utf-8")
    assert "INGEN verifierad central skrivspärr" in source
    assert "externägararkitektur" in source
    assert "ba-hot-side-pause-and-rapt-handoff-2026-09-19_sv.md" in source
