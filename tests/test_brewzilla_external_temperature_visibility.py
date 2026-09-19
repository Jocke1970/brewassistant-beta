"""Regression checks for BrewZilla external-temperature dashboard visibility."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESOLVER = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_temperature.py"
BINARY_SENSOR = ROOT / "custom_components/brewassistant/binary_sensor.py"
EXTERNAL_CARDS = (
    ROOT / "dashboard/cards/brewzilla_ble_indicator.yaml",
    ROOT / "dashboard/cards/brewzilla_ble_indicator_sv.yaml",
    ROOT / "dashboard/cards/brewzilla_ble_status.yaml",
    ROOT / "dashboard/cards/brewzilla_ble_status_sv.yaml",
)
GAUGE_CARDS = (
    ROOT / "dashboard/cards/brewzilla_dual_temperature_gauge.yaml",
    ROOT / "dashboard/cards/brewzilla_dual_temperature_gauge_sv.yaml",
)
STACK_CARDS = (
    ROOT / "dashboard/cards/brewzilla.yaml",
    ROOT / "dashboard/cards/brewzilla_sv.yaml",
)
EXTERNAL_AVAILABLE = "binary_sensor.brewassistant_brewzilla_external_temperature_available"


def test_resolver_exposes_external_temperature_availability_independent_of_selection() -> None:
    source = RESOLVER.read_text(encoding="utf-8")
    assert 'external_ble = _with_diagnostics(ble, selected="Auto", internal=internal)' in source
    assert 'external_control = _with_diagnostics(control, selected="Auto", internal=internal)' in source
    assert '"external_temperature_available": external is not None' in source
    assert '"external_temperature_source": external.get("source") if external else None' in source
    assert '"external_temperature_entity": external.get("entity_id") if external else None' in source


def test_brewzilla_external_temperature_binary_sensor_is_registered() -> None:
    source = BINARY_SENSOR.read_text(encoding="utf-8")
    assert "class BrewAssistantBrewZillaExternalTemperatureAvailableBinarySensor" in source
    assert 'super().__init__(coordinator, "brewzilla_external_temperature_available")' in source
    assert 'snapshot.get("external_temperature_available")' in source
    assert "BrewAssistantBrewZillaExternalTemperatureAvailableBinarySensor(coordinator)" in source


def test_ble_cards_are_hidden_without_external_sensor() -> None:
    for path in EXTERNAL_CARDS:
        source = path.read_text(encoding="utf-8")
        assert EXTERNAL_AVAILABLE in source, f"external availability gate missing from {path.name}"
        assert 'state: "on"' in source, f"external availability state condition missing from {path.name}"


def test_temperature_gauge_remains_available_without_external_sensor() -> None:
    for path in GAUGE_CARDS:
        source = path.read_text(encoding="utf-8")
        assert EXTERNAL_AVAILABLE not in source, f"temperature gauge must not depend on external sensor in {path.name}"
        assert "sensor.brewassistant_brewzilla_wort_temperature" in source
        assert "sensor.brewassistant_brewzilla_mash_temperature" in source


def test_dual_temperature_gauge_uses_neutral_background_and_opposed_needles() -> None:
    for path in GAUGE_CARDS:
        source = path.read_text(encoding="utf-8")
        assert "thermal_state" not in source
        assert "type: custom:button-card" not in source
        assert "entity: sensor.brewassistant_brewzilla_mash_temperature" in source
        assert "entity2: sensor.brewassistant_brewzilla_wort_temperature" in source
        assert "mode: needle" in source
        assert 'main_needle: "M -49 -2 L -40 0 L -49 2 Z"' in source
        assert 'inner_needle: "M -27.5 -1.5 L -32 0 L -27.5 1.5 Z"' in source


def test_brewzilla_stack_uses_same_dual_temperature_gauge_geometry() -> None:
    for path in STACK_CARDS:
        source = path.read_text(encoding="utf-8")
        assert "entity: sensor.brewassistant_brewzilla_mash_temperature" in source
        assert "entity2: sensor.brewassistant_brewzilla_wort_temperature" in source
        assert "mode: needle" in source
        assert 'main_needle: "M -49 -2 L -40 0 L -49 2 Z"' in source
        assert 'inner_needle: "M -27.5 -1.5 L -32 0 L -27.5 1.5 Z"' in source
