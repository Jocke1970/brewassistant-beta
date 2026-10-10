"""Brewday 0b8 operator status/UI parity after field screenshots.

These YAML layout tests complement the isolated backend and HA/RCL tests.
Real browser rendering still requires field acceptance.
"""

from pathlib import Path

import yaml


CARDS = Path(__file__).resolve().parents[1] / "dashboard" / "cards"


def test_readonly_is_compact_without_writable_backdoor():
    for name in ("brewday_control_status_sv.yaml", "brewday_control_status.yaml"):
        doc = yaml.safe_load((CARDS / name).read_text(encoding="utf-8"))
        cards = doc["cards"]
        observe = next(card for card in cards if card.get("entity") ==
                       "switch.brewassistant_brewzilla_observe_only")
        assert observe["type"] == "custom:button-card"
        assert observe["show_icon"] is True
        assert observe["show_state"] is False
        assert observe["styles"]["grid"] == [
            {"grid-template-areas": '"i n" "l l"'},
            {"grid-template-columns": "32px minmax(0,1fr)"},
            {"grid-template-rows": "min-content min-content"},
            {"row-gap": "6px"},
        ]
        assert {"height": "auto"} in observe["styles"]["card"]
        assert {"min-height": "0px"} in observe["styles"]["card"]
        assert {"width": "26px"} in observe["styles"]["icon"]
        assert observe["tap_action"]["service"] == "switch.turn_on"
        assert observe["tap_action"]["target"]["entity_id"] == (
            "switch.brewassistant_brewzilla_observe_only"
        )
        assert "call-service' : 'none'" in observe["tap_action"]["action"]


def test_reconnect_cta_and_remaining_timer_have_consistent_blockers():
    for name in ("brewday_control_status_sv.yaml", "brewday_control_status.yaml"):
        text = (CARDS / name).read_text(encoding="utf-8")
        cards = yaml.safe_load(text)["cards"]
        reconnect, main = cards[0], cards[1]
        assert reconnect["type"] == "custom:button-card"
        name_js = reconnect["name"]
        label_js = reconnect["label"]
        tap_js = reconnect["tap_action"]["action"]
        for js in (name_js, label_js, tap_js):
            assert "a.resync_required === true" in js
            assert "resync_required" in js
            assert "['unknown','idle','none']" in js
            assert "snapshot_age_seconds" in js
            assert "a.profile_source_available === true" in js
            assert "a.profile_active === true" in js
            assert "switch.brewassistant_brewzilla_observe_only" in js
        assert reconnect["tap_action"]["service"] == "brewassistant.brewday_reconnect_ack"
        assert "expected_session_id" in reconnect["tap_action"]["data"]
        assert "expected_step" in reconnect["tap_action"]["data"]
        assert "confirmation" in reconnect["tap_action"]
        assert "const timeUnverified = resync || fallback || a.fallback_timer_uncertain === true;" in main["label"]
        assert "timeDisplay = timeUnverified ? '—'" in main["label"]
        assert "timeDetail = timeUnverified ? T.noTime" in main["label"]
        assert "service: switch.turn_off" not in text
        assert "rapt_cloud_link.end_brewzilla_profile" not in text
        assert any("button.brewassistant_abort_brewday" in str(c)
                   for c in cards)
