"""Field regression: reconnect freshness must belong to the external source.

Source screenshots showed a green SNAPSHOT 0s on a synthetic idle Manual state
while RCL session/step were unknown. These tests execute UI JavaScript (Node)
against actual YAML without contacting HA or hardware.
"""

import json
from pathlib import Path
import shutil
import subprocess

import pytest
import yaml

CARDS = Path(__file__).resolve().parents[1] / "dashboard" / "cards"


@pytest.mark.parametrize("name", ["brewday_control_status_sv.yaml", "brewday_control_status.yaml"])
def test_reconnect_snapshot_provenance_and_ack_are_fail_closed(name):
    card = yaml.safe_load((CARDS / name).read_text(encoding="utf-8"))["cards"][0]
    assert card["type"] == "custom:button-card"
    for property_name in ("name", "label"):
        assert "origin.startsWith('binary_sensor.')" in card[property_name]
        assert "origin.startsWith('sensor.brewfather_')" in card[property_name]
    assert "origin.startsWith('binary_sensor.')" in card["tap_action"]["action"]
    assert "origin.startsWith('sensor.brewfather_')" in card["tap_action"]["action"]

    if not shutil.which("node"):
        pytest.skip("Node runtime unavailable")

    def evaluate(template, attributes, runtime="resync_required", bf_status="inactive"):
        snippet = template.strip().removeprefix("[[[").removesuffix("]]]").strip()
        states = {
            "sensor.brewassistant_brewday_runtime_summary": {"attributes": attributes},
            "sensor.brewassistant_brewday_runtime_state": {"state": runtime},
            "sensor.brewassistant_brewday_operator_control_state": {"state": "armed"},
            "switch.brewassistant_brewzilla_observe_only": {"state": "on"},
            "sensor.brewfather_brew_tracker_status": {"state": bf_status},
        }
        script = ("const states = " + json.dumps(states) + ";\n"
                  + "function evaluate() {\n" + snippet + "\n}\n"
                  + "process.stdout.write(String(evaluate()));\n")
        return subprocess.run(["node", "-e", script], check=True,
                              capture_output=True, text=True).stdout

    base = {
        "resync_required": True,
        "resync_from_mode": "RCL Brewing",
        "resync_reason": "ha_restart_requires_external_reconciliation",
        "snapshot_age_seconds": 0,
        "snapshot_entity": "python_manual_runtime",
        "step": "Idle",
        "profile_active": None,
        "profile_source_available": False,
    }
    red = evaluate(card["label"], base)
    assert "✕ SNAPSHOT" in red
    assert "✕ KÄLLA" in red
    assert "0 s" not in red
    assert evaluate(card["tap_action"]["action"], base) == "none"

    attested = {**base,
        "snapshot_entity": "binary_sensor.brewzilla_profile_active",
        "profile_active": True,
        "profile_source_available": True,
        "profile_session_id": "session1",
        "raw_step_name": "Mash",
        "snapshot_age_seconds": 5,
    }
    green = evaluate(card["label"], attested)
    assert "✓ SNAPSHOT" in green
    assert "✓ KÄLLA" in green
    assert evaluate(card["tap_action"]["action"], attested) == "call-service"

    forged_age = {**attested, "snapshot_entity": "python_manual_runtime",
                  "snapshot_age_seconds": 0}
    assert "✕ SNAPSHOT" in evaluate(card["label"], forged_age)
    assert evaluate(card["tap_action"]["action"], forged_age) == "none"

    stale = {**attested, "snapshot_age_seconds": 600}
    assert "✕ SNAPSHOT" in evaluate(card["label"], stale)
    assert evaluate(card["tap_action"]["action"], stale) == "none"

    bf = {**base, "resync_from_mode": "Brewfather Brewing",
          "snapshot_entity": "sensor.brewfather_brew_tracker_status",
          "snapshot_age_seconds": 8, "raw_step_name": "Mash"}
    assert "✓ SNAPSHOT" in evaluate(card["label"], bf, bf_status="active")
    assert "✕ SNAPSHOT" in evaluate(card["label"], bf, bf_status="inactive")
    assert evaluate(card["tap_action"]["action"], bf, bf_status="inactive") == "none"
