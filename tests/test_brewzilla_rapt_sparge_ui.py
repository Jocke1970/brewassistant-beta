"""Sparge UI: RAPT-only, dynamically discovered profile, guarded observation and lift."""

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
            'entity: switch.brewassistant_brewzilla_observe_only\n    state: "off"',
            "entity: sensor.brewassistant_brewzilla_orchestration_mode\n    state_not: observe-only",
            'entity: sensor.brewassistant_brewday_runtime_source\n    state: "RAPT BrewZilla Profile"',
            'entity: sensor.brewassistant_brewday_runtime_step\n        state: "Sparge"',
            'entity: sensor.brewassistant_brewday_runtime_step\n        state: "Lakning"',
            "condition: or",
            "entity: button.brewassistant_confirm_sparge_lift",
            "service: button.press",
            "confirmation:",
            "operator_confirmation_available",
            "outputs_confirmed_off",
            "rapt_cloud_link_brewzilla_profile_runtime",
            "hot_side_actuator_writes_allowed === true",
            "observe_only_effective === false",
        ):
            assert guard in source
        assert "binary_sensor.brewzilla_profile_active" not in source
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
