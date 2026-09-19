"""Additive contract checks for existing EN/SV Sparge cards.

No sensors, buttons, BT views or BF fermentation paths may be removed to
implement the RAPT local-target safety rule. These are structural tests, not
Home Assistant browser-rendering verification.
"""

from pathlib import Path

CARDS = Path(__file__).resolve().parents[1] / "dashboard" / "cards"


def test_existing_sparge_cards_preserve_confirmation_and_both_step_names():
    for name in ("rapt_sparge_controls.yaml", "rapt_sparge_controls_sv.yaml"):
        card = (CARDS / name).read_text(encoding="utf-8")
        assert 'state: "RAPT BrewZilla Profile"' in card
        assert 'state: "Sparge"' in card
        assert 'state: "Lakning"' in card
        assert 'condition: or' in card
        assert "button.brewassistant_confirm_sparge_lift" in card
        assert "service: button.press" in card
        assert "confirmation:" in card
        assert "operator_confirmation_available" in card
        assert "outputs_confirmed_off" in card
        assert "number.brewzilla_heat_utilization" in card
        assert "number.brewzilla_pump_utilization" in card


def test_sparge_cards_explain_new_block_without_using_bt_as_source():
    for name in ("rapt_sparge_controls.yaml", "rapt_sparge_controls_sv.yaml"):
        card = (CARDS / name).read_text(encoding="utf-8")
        assert "sensor.brewassistant_brewzilla_orchestration_mode" in card
        assert "sensor.brewassistant_brewzilla_control_reason" in card
        assert "sparge-local-target-conflict-blocked" in card
        assert "positive BA heating blocked" in card
        assert "sensor.brewfather_brew_tracker_" not in card
        assert "sensor.brewfather_fermentation_" not in card
