"""UI contract for the consolidated Brewday Runtime flow card."""

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


def test_runtime_flow_distinguishes_physical_and_brewfather_targets() -> None:
    for path in CARDS:
        source = path.read_text(encoding="utf-8")
        assert "sensor.brewassistant_brewzilla_runtime_target_temperature" in source
        assert "sensor.brewassistant_brewday_target_temperature" in source


def test_runtime_flow_keeps_pending_and_abort_operator_paths() -> None:
    for path in CARDS:
        source = path.read_text(encoding="utf-8")
        assert "button.brewassistant_confirm_supervised_apply" in source
        assert "button.brewassistant_cancel_supervised_apply" in source
        assert "button.brewassistant_abort_brewday" in source


def test_runtime_flow_does_not_expose_direct_brewzilla_hardware_toggles() -> None:
    for path in CARDS:
        source = path.read_text(encoding="utf-8")
        assert "switch.brewzilla_heater" not in source
        assert "switch.brewzilla_pump" not in source
        assert "number.brewzilla_heat_utilization" not in source
        assert "number.brewzilla_pump_utilization" not in source
