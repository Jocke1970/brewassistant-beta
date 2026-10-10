"""BrewAssistant 0b6 Lovelace safety and stale-warning contract checks.

Pure source checks: browser behavior is separately smoke-tested with mocked
Lovelace states before merging. UI is not an authority boundary.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARDS = ROOT / "dashboard/cards"


def test_brewday_premium_cards_have_parity_and_real_guarded_controls():
    for name in ("brewday_control_status_sv.yaml", "brewday_control_status.yaml"):
        source = (CARDS / name).read_text(encoding="utf-8")
        assert source.startswith("# BrewAssistant premium Brewday")
        assert source.count("type: custom:button-card") >= 6
        assert "type: custom:expander-card" in source
        assert "sensor.brewassistant_brewday_runtime_summary" in source
        assert "a.resync_required === true" in source
        assert "a.fallback_active" in source
        assert "a.operator_abort_active" in source
        assert "brewassistant.brewday_reconnect_ack" in source
        assert "expected_session_id" in source and "expected_step" in source
        assert "a.profile_source_available === true" in source
        assert "a.profile_active === true" in source
        assert "snapshot_age_seconds" in source
        assert "states['switch.brewassistant_brewzilla_observe_only']?.state === 'on'" in source
        assert "service: switch.turn_on" in source
        assert "service: switch.turn_off" not in source\n        assert "brewassistant.brewday_start_verified" in source
        assert "service: button.press" in source
        assert "entity_id: button.brewassistant_abort_brewday" in source
        assert "entity_id: button.brewassistant_rearm_brewday_control" in source
        # ABORT is unconditional, independent of visible card-source state.
        assert "type: conditional" not in source
        assert "type: vertical-stack" in source
        assert "button.press" in source
        assert "number.set_value" not in source
        assert "switch.brewzilla_heater" not in source
        assert "switch.brewzilla_pump" not in source
        assert "__TRANSLATIONS__" not in source


def test_fermentation_cards_restore_red_stale_icons_and_age_decay():
    for name in (
        "fermentation_sv.yaml", "fermentation.yaml",
        "fermentation_cockpit_v2_sv.yaml", "fermentation_cockpit_v2.yaml",
    ):
        source = (CARDS / name).read_text(encoding="utf-8")
        assert "update_timer: 1m" in source, name
        assert "mdi:alert-circle" in source, name
        assert "#b3261e" in source, name
        assert ">= 20" in source, name
        assert ">= 15" in source, name
        assert "Date.now()" in source, name
        assert "last_reported" not in source, name
        assert "brewassistant.abort" not in source, name

    for name in ("fermentation_sv.yaml", "fermentation.yaml"):
        source = (CARDS / name).read_text(encoding="utf-8")
        # Upstream source, not a freshly recomputed aggregate.
        assert "last_updated" in source
        assert "source_entity" in source
        assert "pillAlert" in source

    for name in ("fermentation_cockpit_v2_sv.yaml", "fermentation_cockpit_v2.yaml"):
        source = (CARDS / name).read_text(encoding="utf-8")
        assert "temperature_observed_at" in source
        assert "gravity_observed_at" in source
        assert "freshnessWarning" in source
        assert "const danger = missing || unverified || stale" in source
