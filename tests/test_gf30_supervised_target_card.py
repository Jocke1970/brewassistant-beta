"""Contract tests for the focused BrewAssistant GF30 supervised target card."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARDS = (
    ROOT / "dashboard/cards/gf30_supervised_target.yaml",
    ROOT / "dashboard/cards/gf30_supervised_target_sv.yaml",
)

REQUIRED_ENTITIES = (
    "sensor.brewassistant_gf30_recommended_target",
    "sensor.brewassistant_gf30_controller_target",
    "sensor.brewassistant_gf30_target_delta",
    "sensor.brewassistant_gf30_target_apply_state",
    "select.brewassistant_apply_mode",
    "button.brewassistant_gf30_prepare_target",
    "button.brewassistant_confirm_supervised_apply",
    "button.brewassistant_cancel_supervised_apply",
    "binary_sensor.grainfather_gf30_controller_online",
)

FORBIDDEN_TECHNICAL_SURFACES = (
    "controller_rssi",
    "mqtt_event_subscription",
    "hysteresis",
    "temperature_offset",
    "ota_status",
    "firmware",
    "coolant",
    "preflight",
)


def test_gf30_supervised_target_cards_use_only_operator_relevant_surface() -> None:
    for path in CARDS:
        source = path.read_text(encoding="utf-8")
        for entity_id in REQUIRED_ENTITIES:
            assert entity_id in source
        for forbidden in FORBIDDEN_TECHNICAL_SURFACES:
            assert forbidden not in source


def test_gf30_supervised_target_cards_keep_two_step_confirmation() -> None:
    for path in CARDS:
        source = path.read_text(encoding="utf-8")
        assert 'state: "proposed"' in source
        assert 'state: "awaiting_confirmation"' in source
        assert "button.brewassistant_gf30_prepare_target" in source
        assert "button.brewassistant_confirm_supervised_apply" in source
        assert "button.brewassistant_cancel_supervised_apply" in source
