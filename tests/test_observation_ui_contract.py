"""Static beta.14 UI regression checks; not browser rendering or hardware proof."""

from pathlib import Path

import pytest

CARDS = Path(__file__).resolve().parents[1] / "dashboard" / "cards"
OBSERVE = "switch.brewassistant_brewzilla_observe_only"
MODE = "sensor.brewassistant_brewzilla_orchestration_mode"


@pytest.mark.parametrize("filename", [
    "brewday_operator_actions_sv.yaml", "brewday_operator_actions.yaml",
    "rapt_sparge_controls_sv.yaml", "rapt_sparge_controls.yaml",
])
def test_ordinary_ba_actions_are_hidden_until_explicit_rearm(filename):
    content = (CARDS / filename).read_text(encoding="utf-8")
    assert "type: conditional" in content
    assert f"- entity: {OBSERVE}\n          state: \"off\"" in content or (
        f"- entity: {OBSERVE}\n    state: \"off\"" in content
    )
    assert f"- entity: {MODE}\n          state_not: observe-only" in content or (
        f"- entity: {MODE}\n    state_not: observe-only" in content
    )
    assert "action: call-service" in content


@pytest.mark.parametrize("filename", [
    "rapt_sparge_controls_sv.yaml", "rapt_sparge_controls.yaml",
])
def test_sparge_uses_dynamic_rcl_profile_and_requires_effective_write_permission(filename):
    content = (CARDS / filename).read_text(encoding="utf-8")
    assert "binary_sensor.brewzilla_profile_active" not in content
    assert "rapt_cloud_link_brewzilla_profile_runtime" in content
    assert "observe_only_effective === false" in content
    assert "hot_side_actuator_writes_allowed === true" in content


@pytest.mark.parametrize("filename", [
    "brewzilla_local_control_sv.yaml", "brewzilla_local_control.yaml",
])
def test_legacy_local_readback_is_not_a_hidden_rcl_control_card(filename):
    content = (CARDS / filename).read_text(encoding="utf-8")
    assert "type: markdown" in content
    assert "tap_action:" not in content
    assert "type: entities" not in content
    assert "switch.brewzilla_heater" in content
    assert "number.brewzilla_target_temperature" in content
    assert "observe_only_effective" in content


def test_abort_ui_remains_available_and_does_not_claim_physical_shutdown():
    sv = (CARDS / "brewday_operator_actions_sv.yaml").read_text(encoding="utf-8")
    en = (CARDS / "brewday_operator_actions.yaml").read_text(encoding="utf-8")
    for source, marker, warning in (
        (sv, "ABORT · NÖDSTOPP", "kontrollera fysisk avstängning"),
        (en, "ABORT · EMERGENCY STOP", "verify physical shutdown"),
    ):
        assert marker in source and warning in source
        assert source.index("entity: button.brewassistant_abort_brewday") < source.index(
            f"entity: {OBSERVE}"
        )
        assert source.index("service: brewassistant.manual_brewday_prepare") < source.index(
            f"entity: {OBSERVE}"
        )
        assert source.count("entity: button.brewassistant_abort_brewday") == 1
        assert "physical shutdown guaranteed" not in source.lower()
