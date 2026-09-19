"""Sparge controls: hide outside active RAPT, require dual explicit confirmation."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARDS = ROOT / "dashboard/cards"
BUTTON = ROOT / "custom_components/brewassistant/button.py"
CONTROLLER = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_rapt_sparge_controller.py"


def test_sparge_cards_source_and_step_scoped_with_matching_machine_ids():
    english = (CARDS / "rapt_sparge_controls.yaml").read_text(encoding="utf-8")
    swedish = (CARDS / "rapt_sparge_controls_sv.yaml").read_text(encoding="utf-8")
    for source in (english, swedish):
        for guard in (
            "entity: binary_sensor.brewzilla_profile_active\n    state: \"on\"",
            "entity: sensor.brewassistant_brewday_runtime_source\n    state: \"RAPT BrewZilla Profile\"",
            "entity: sensor.brewassistant_brewday_runtime_step\n    state: \"Sparge\"",
            "entity: button.brewassistant_confirm_sparge_lift",
            "service: button.press",
            "confirmation:",
            "operator_confirmation_available",
            "outputs_confirmed_off",
        ):
            assert guard in source
        assert "number.set_value" not in source
        assert "switch.turn_on" not in source
        assert "brewassistant.apply_brewzilla_target" not in source
    assert "malt pipe is safely lifted" in english
    assert "heating elements" in english
    assert "maltpipan är säkert upplyft" in swedish
    assert "värmeelementen" in swedish


def test_confirm_button_is_a_single_attestation_not_an_implicit_heat_command():
    button = BUTTON.read_text(encoding="utf-8")
    controller = CONTROLLER.read_text(encoding="utf-8")
    assert "BrewAssistantBrewZillaSpargeLiftButton(coordinator)" in button
    assert "async_confirm_sparge_lift(self.coordinator.hass)" in button
    assert '"sparge_lift_operator_confirmation"' in button
    assert '"sparge_lift_confirmed_requires_supervised_preboil"' in controller
    assert 'return "read_only" if policy == "read_only" else "confirm"' in controller
    assert "RAPT remains responsible for manual Boil transition" in controller
