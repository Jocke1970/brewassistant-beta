"""UI contract for the Brewday Runtime process companion card."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CARDS = (
    ROOT / "dashboard/cards/brewassistant_brewday_runtime_flow.yaml",
    ROOT / "dashboard/cards/brewassistant_brewday_runtime_flow_sv.yaml",
)


def test_runtime_flow_contains_physical_timing_and_mash_in_actions() -> None:
    for path in CARDS:
        source = path.read_text(encoding="utf-8")
        assert "sensor.brewassistant_brewday_physical_timing_summary" in source
        assert "sensor.brewassistant_brewday_physical_timing_mode" in source
        assert "button.brewassistant_mash_in_started" in source
        assert "button.brewassistant_mash_in_complete" in source
        assert "binary_sensor.brewassistant_brewzilla_mash_in_gate_pending" in source


def test_runtime_flow_preserves_two_step_mash_in_contract() -> None:
    for path in CARDS:
        source = path.read_text(encoding="utf-8")
        assert "ready_for_mash_in" in source
        assert "mash_in_started" in source
        assert "button.press" in source


def test_runtime_flow_does_not_duplicate_generic_runtime_actions() -> None:
    for path in CARDS:
        source = path.read_text(encoding="utf-8")
        assert "button.brewassistant_confirm_supervised_apply" not in source
        assert "button.brewassistant_cancel_supervised_apply" not in source
        assert "button.brewassistant_abort_brewday" not in source


def test_runtime_flow_does_not_expose_direct_brewzilla_hardware_toggles() -> None:
    for path in CARDS:
        source = path.read_text(encoding="utf-8")
        assert "switch.brewzilla_heater" not in source
        assert "switch.brewzilla_pump" not in source
        assert "number.brewzilla_heat_utilization" not in source
        assert "number.brewzilla_pump_utilization" not in source
