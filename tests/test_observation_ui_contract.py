"""Static regression checks for beta.14's explicitly guarded legacy UI surfaces.

These tests check repository YAML contracts, NOT browser rendering or backend
safety. All other dashboards and user-customized cards need separate review.
"""

from pathlib import Path

import pytest

CARDS = Path(__file__).resolve().parents[1] / "dashboard" / "cards"
OBSERVE = "switch.brewassistant_brewzilla_observe_only"
MODE = "sensor.brewassistant_brewzilla_orchestration_mode"


@pytest.mark.parametrize("filename", [
    "brewday_operator_actions_sv.yaml",
    "brewday_operator_actions.yaml",
    "rapt_sparge_controls_sv.yaml",
    "rapt_sparge_controls.yaml",
])
def test_operator_actions_are_hidden_until_explicit_rearm(filename):
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
def test_local_readback_cannot_toggle_rcl_entities_in_entities_card(filename):
    content = (CARDS / filename).read_text(encoding="utf-8")
    assert "type: markdown" in content
    assert "tap_action:" not in content
    assert "type: entities" not in content
    assert "switch.brewzilla_heater" in content
    assert "number.brewzilla_target_temperature" in content
    assert "observe_only_effective" in content


def test_abort_ui_does_not_promise_physical_shutdown():
    sv = (CARDS / "brewday_operator_actions_sv.yaml").read_text(encoding="utf-8")
    en = (CARDS / "brewday_operator_actions.yaml").read_text(encoding="utf-8")
    assert "Fysisk OFF är inte garanterad" in sv
    assert "Physical OFF is not guaranteed" in en
