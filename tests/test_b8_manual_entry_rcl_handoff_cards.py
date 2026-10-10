"""Manual idle landing and clear operator-owned RCL Assist START (view-only UX).

No tests in this module actuate hardware; backend owner gates remain active.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARDS = ROOT / "dashboard" / "cards"


def test_manual_brewday_has_idle_no_external_landing_separate_from_active_controls():
    for p in ("brewassistant_manual_brewday_sv.yaml", "brewassistant_manual_brewday.yaml"):
        text = (CARDS / p).read_text(encoding="utf-8")
        assert text.startswith("# Manual Brewday entry")
        assert "type: vertical-stack\ncards:" in text
        assert "sensor.brewassistant_brewday_runtime_source\n        state: \"None\"" in text
        assert "sensor.brewassistant_brewday_runtime_state\n        state: \"idle\"" in text
        assert "sensor.brewassistant_manual_brewday_status\n        state: \"idle\"" in text
        assert "service: brewassistant.manual_brewday_prepare" in text
        assert "service: brewassistant.manual_brewday_start" in text
        assert "type: conditional\n    conditions:" in text
        assert 'state: "Manual Brewday"' in text
        assert 'state_not: "idle"' in text
        assert "switch.brewassistant_show_brewday" in text
        assert "confirmation:" in text
        # Manual entry must not change the RCL ownership or directly energize BZ.
        assert "service: switch.turn_off" not in text
        assert "service: number.set_value" not in text
        assert "rapt_cloud_link.start_brewzilla_profile" not in text


def test_rcl_start_is_labeled_as_assist_only_not_profile_start():
    for p in ("brewday_control_status_sv.yaml", "brewday_control_status.yaml"):
        text = (CARDS / p).read_text(encoding="utf-8")
        assert "brewassistant.brewday_start_verified" in text
        assert "ENABLE BA ASSIST" in text or "AKTIVERA BA-ASSISTANS" in text
        assert "BA READ-ONLY ·" in text
        assert "Do NOT turn off manually" in text or "Slå INTE av manuellt" in text
        assert "ALREADY running" in text or "kör REDAN" in text
        assert "service: switch.turn_off" not in text
        assert "entity_id: button.brewassistant_abort_brewday" in text


def test_brewday_manual_cards_are_valid_yaml_with_two_conditional_cards():
    """Catch the former 'No type provided' dashboard regression at parse time."""
    import yaml

    for file in ("brewassistant_manual_brewday_sv.yaml", "brewassistant_manual_brewday.yaml"):
        doc = yaml.safe_load((CARDS / file).read_text(encoding="utf-8"))
        assert doc["type"] == "vertical-stack"
        assert isinstance(doc.get("cards"), list)
        assert len(doc["cards"]) == 2
        entry, active = doc["cards"]
        assert entry["type"] == "conditional"
        assert active["type"] == "conditional"
        assert entry["card"]["type"] == "custom:button-card"
        assert active["card"]["type"] == "vertical-stack"
        assert any(
            cond.get("entity") == "sensor.brewassistant_brewday_runtime_state"
            and cond.get("state") == "idle"
            for cond in entry["conditions"]
        )
        assert any(
            cond.get("entity") == "sensor.brewassistant_brewday_runtime_source"
            and cond.get("state") == "None"
            for cond in entry["conditions"]
        )
        assert any(
            cond.get("entity") == "sensor.brewassistant_brewday_runtime_source"
            and cond.get("state") == "Manual Brewday"
            for cond in active["conditions"]
        )
        assert all(isinstance(card, dict) and card.get("type") for card in active["card"]["cards"])
