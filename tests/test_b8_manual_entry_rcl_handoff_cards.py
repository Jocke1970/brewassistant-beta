"""Manual idle landing and clear operator-owned RCL Assist START (view-only UX).

No tests in this module actuate hardware; backend owner gates remain active.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARDS = ROOT / "dashboard" / "cards"


def test_manual_brewday_entry_is_always_visible_but_backend_guarded():
    for p in ("brewassistant_manual_brewday_sv.yaml", "brewassistant_manual_brewday.yaml"):
        text = (CARDS / p).read_text(encoding="utf-8")
        assert text.startswith("# Manual Brewday entry")
        assert "type: vertical-stack\ncards:" in text
        # The landing panel must not disappear when source=Manual Brewday + idle.
        assert "  - type: custom:button-card\n    entity: sensor.brewassistant_manual_brewday_status" in text
        assert "['None','Manual Brewday'].includes(source)" in text
        assert "runtime === 'idle' && manual === 'idle'" in text
        assert "rapt_cloud_link_brewzilla_profile_runtime" in text
        assert "a.resync_required === true" in text
        assert "a.operator_abort_active === true" in text
        assert "return ready ? 'call-service' : 'more-info';" in text
        assert "service: brewassistant.manual_brewday_prepare" in text
        assert "service: brewassistant.manual_brewday_start" in text
        # The operational Manual panel remains conditional on real Manual ownership.
        assert 'state: "Manual Brewday"' in text
        assert 'state_not: "idle"' in text
        assert "switch.brewassistant_show_brewday" in text
        assert "confirmation:" in text
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


def test_brewday_manual_cards_are_valid_yaml_with_permanent_entry_and_conditional_process():
    """Never lose the Manual entry panel through mutually exclusive conditions."""
    import yaml

    for file in ("brewassistant_manual_brewday_sv.yaml", "brewassistant_manual_brewday.yaml"):
        doc = yaml.safe_load((CARDS / file).read_text(encoding="utf-8"))
        assert doc["type"] == "vertical-stack"
        assert isinstance(doc.get("cards"), list)
        assert len(doc["cards"]) == 2
        entry, active = doc["cards"]
        assert entry["type"] == "custom:button-card"
        assert active["type"] == "conditional"
        assert active["card"]["type"] == "vertical-stack"
        assert entry["tap_action"]["service"] == "brewassistant.manual_brewday_prepare"
        assert any(
            cond.get("entity") == "sensor.brewassistant_brewday_runtime_source"
            and cond.get("state") == "Manual Brewday"
            for cond in active["conditions"]
        )
        assert all(isinstance(card, dict) and card.get("type") for card in active["card"]["cards"])
