"""Regression contract for prominent operator ACK and always-visible Manual portal.

These view-only Lovelace cards may never bypass protected backend ownership
and must keep ABORT/READ-ONLY strictly separate from reconnect ACK.
"""

from pathlib import Path

import yaml

CARDS = Path(__file__).resolve().parents[1] / "dashboard" / "cards"


def test_operator_reconnect_hero_precedes_status_and_remains_ack_only():
    for name in ("brewday_control_status_sv.yaml", "brewday_control_status.yaml"):
        text = (CARDS / name).read_text(encoding="utf-8")
        cards = yaml.safe_load(text)["cards"]
        hero, status = cards[0], cards[1]
        assert hero["type"] == "conditional"
        assert hero["conditions"] == [
            {
                "condition": "or",
                "conditions": [
                    {
                        "condition": "state",
                        "entity": "sensor.brewassistant_brewday_runtime_state",
                        "state": "resync_required",
                    },
                    {
                        "condition": "state",
                        "entity": "sensor.brewassistant_brewday_runtime_summary",
                        "attribute": "resync_required",
                        "state": True,
                    },
                ],
            }
        ]
        # Field regression: HA may restore a sticky resync latch while the
        # process sensor still reports idle. Neither path may hide the hero.
        def visible(runtime_state, summary_latched):
            alternatives = hero["conditions"][0]["conditions"]
            return any(
                (item.get("attribute") == "resync_required" and
                 summary_latched is item["state"])
                or (item["entity"] == "sensor.brewassistant_brewday_runtime_state"
                    and runtime_state == item["state"])
                for item in alternatives
            )

        assert visible("resync_required", False)
        assert visible("idle", True)
        assert visible("paused", True)
        assert not visible("idle", False)
        assert not visible("running", False)
        assert hero["card"]["type"] == "custom:button-card"
        assert status["name"] == "Brewday Control / Status"
        assert hero["card"]["tap_action"]["service"] == "brewassistant.brewday_reconnect_ack"
        assert "expected_step" in hero["card"]["tap_action"]["data"]
        assert "expected_session_id" in hero["card"]["tap_action"]["data"]
        assert "confirmation" in hero["card"]["tap_action"]
        assert "resync_required === true" in hero["card"]["tap_action"]["action"]
        assert "snapshot_age_seconds" in hero["card"]["tap_action"]["action"]
        assert "a.profile_source_available === true" in hero["card"]["tap_action"]["action"]
        assert "switch.brewassistant_brewzilla_observe_only" in hero["card"]["tap_action"]["action"]
        assert "operator_abort_active" in hero["card"]["tap_action"]["action"]
        assert "ba-operator-reconnect-pulse" in hero["card"]["extra_styles"]
        assert "prefers-reduced-motion" in hero["card"]["extra_styles"]
        assert text.count("service: brewassistant.brewday_reconnect_ack") == 1
        # Outside the reconnect banner the emergency STOP stays unconditional.
        assert any(
            isinstance(card, dict) and card.get("type") == "horizontal-stack"
            and "button.brewassistant_abort_brewday" in str(card)
            for card in cards
        )
        assert "service: switch.turn_off" not in text
        assert "rapt_cloud_link.end_brewzilla_profile" not in text


def test_manual_entry_is_visible_even_in_ambiguous_source_states_but_not_enabled():
    for name in ("brewassistant_manual_brewday_sv.yaml", "brewassistant_manual_brewday.yaml"):
        text = (CARDS / name).read_text(encoding="utf-8")
        cards = yaml.safe_load(text)["cards"]
        assert len(cards) == 2
        portal, active = cards
        assert portal["type"] == "custom:button-card"  # no visibility conditional
        assert active["type"] == "conditional"
        assert "Manual Brewday" in str(active["conditions"])
        assert portal["tap_action"]["service"] == "brewassistant.manual_brewday_prepare"
        assert "return ready ? 'call-service' : 'more-info'" in portal["tap_action"]["action"]
        assert "['None','Manual Brewday'].includes(source)" in portal["tap_action"]["action"]
        assert "runtime === 'idle' && manual === 'idle'" in portal["tap_action"]["action"]
        assert "a.resync_required === true" in portal["tap_action"]["action"]
        assert "rapt_cloud_link_brewzilla_profile_runtime" in portal["tap_action"]["action"]
        assert "sensor.brewfather_brew_tracker_status" in portal["tap_action"]["action"]
        assert "sensor.brewassistant_brewday_operator_control_state" in portal["tap_action"]["action"]
        assert portal["triggers_update"] == "all"
        assert "confirmation" in portal["tap_action"]
        assert "service: switch.turn_off" not in text
        assert "rapt_cloud_link.start_brewzilla_profile" not in text
