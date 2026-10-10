"""Regressions for 0b6 profile UI: don't confuse missing RCL data with zero."""

from pathlib import Path

CARDS = Path(__file__).resolve().parents[1] / "dashboard" / "cards"


def test_rapt_profile_card_discovers_real_device_sensor_and_preserves_missing_values():
    for filename in ("rapt_profile_runtime_sv.yaml", "rapt_profile_runtime.yaml"):
        text = (CARDS / filename).read_text(encoding="utf-8")
        assert "states['binary_sensor.brewzilla_profile_active']" not in text
        assert "entity: sensor.brewassistant_brewday_runtime_source" in text
        assert "rapt_cloud_link_brewzilla_profile_runtime" in text
        assert "profileSensor?.attributes" in text
        assert "expectedId" in text
        assert "candidates.length === 1" in text
        assert "triggers_update: all" in text
        assert "update_timer: 30s" in text
        assert "v === null || v === undefined" in text
        assert "String(v).trim() === ''" in text
        assert "stepCount > 0" in text
        assert "profile_contract_complete === true" in text
        assert "90" in text
        assert "mdi:alert-circle" in text
        assert "0 °C" in text
        assert "service: number.set_value" not in text
        assert "service: switch.turn_on" not in text
