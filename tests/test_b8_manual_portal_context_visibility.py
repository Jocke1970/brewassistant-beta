"""Manual Brewing entry must disappear when blocked, not display a grey placeholder.

Execute the actual button-card display and action templates with Node.
No Home Assistant service, RCL profile or BrewZilla hardware is invoked.
"""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest
import yaml


CARDS = Path(__file__).resolve().parents[1] / "dashboard" / "cards"


def _eval(template: str, states: dict) -> str:
    snippet = template.strip().removeprefix("[[[").removesuffix("]]]").strip()
    script = (
        "const states = " + json.dumps(states, ensure_ascii=False) + ";\n"
        "function evaluate() {\n" + snippet + "\n}\n"
        "process.stdout.write(String(evaluate()));\n"
    )
    return subprocess.run(["node", "-e", script], check=True,
                          capture_output=True, text=True).stdout


def _states(*, source="None", runtime="idle", manual="idle", enabled=True,
            resync=False, fallback=False, abort=False, rapt=False, bf=False,
            restored=False):
    states = {
        "sensor.brewassistant_brewday_runtime_summary": {
            "attributes": {
                "resync_required": resync,
                "fallback_active": fallback,
                "operator_abort_active": abort,
                "resync_from_mode": "RCL Brewing" if restored else None,
            }
        },
        "sensor.brewassistant_brewday_runtime_source": {"state": source},
        "sensor.brewassistant_brewday_runtime_state": {"state": runtime},
        "sensor.brewassistant_manual_brewday_status": {"state": manual},
        "switch.brewassistant_show_brewday": {"state": "on" if enabled else "off"},
        "sensor.brewassistant_brewday_operator_control_state": {
            "state": "aborted" if abort else "armed"
        },
        "sensor.brewfather_brew_tracker_status": {
            "state": "active" if bf else "inactive"
        },
    }
    if rapt:
        states["binary_sensor.brewzilla_profile_active"] = {
            "entity_id": "binary_sensor.brewzilla_profile_active",
            "state": "on",
            "attributes": {
                "ba_source": "rapt_cloud_link_brewzilla_profile_runtime",
                "profile_active": True,
            },
        }
    return states


@pytest.mark.parametrize("name", [
    "brewassistant_manual_brewday_sv.yaml",
    "brewassistant_manual_brewday.yaml",
])
def test_manual_portal_visible_only_when_operator_can_use_it(name):
    cards = yaml.safe_load((CARDS / name).read_text(encoding="utf-8"))["cards"]
    portal, operational = cards
    assert portal["type"] == "custom:button-card"
    assert portal["triggers_update"] == "all"
    assert operational["type"] == "conditional"
    for unsafe in ("resync_required", "aborted", "source_unavailable",
                   "source_unverified", "unavailable", "unknown"):
        assert {
            "entity": "sensor.brewassistant_brewday_runtime_state",
            "state_not": unsafe,
        } in operational["conditions"]
    assert portal["tap_action"]["service"] == "brewassistant.manual_brewday_prepare"
    assert "confirmation" in portal["tap_action"]
    visibility = next(s["display"] for s in portal["styles"]["card"] if "display" in s)
    action = portal["tap_action"]["action"]
    assert "a.resync_required === true" in visibility
    assert "a.fallback_active === true" in visibility
    assert "rapt_cloud_link_brewzilla_profile_runtime" in visibility
    assert "sensor.brewfather_brew_tracker_status" in visibility
    assert "operator_abort_active" in visibility
    assert "switch.brewassistant_show_brewday" in visibility

    if not shutil.which("node"):
        pytest.skip("Node not installed for executing button-card expressions")

    # All unsafe/irrelevant states must disappear entirely.
    cases = (
        (_states(), "grid", "call-service"),  # Legitimate Manual PREPARE
        (_states(source="Manual Brewday"), "grid", "call-service"),
        (_states(source="Manual Brewday", runtime="running", manual="running"),
         "grid", "more-info"),  # Existing Manual session remains visible
        (_states(resync=True), "none", "more-info"),
        (_states(restored=True), "none", "more-info"),
        (_states(fallback=True), "none", "more-info"),
        (_states(rapt=True), "none", "more-info"),
        (_states(bf=True), "none", "more-info"),
        (_states(source="RAPT BrewZilla Profile", runtime="running"),
         "none", "more-info"),
        (_states(source="Brewfather Brew Tracker", runtime="running"),
         "none", "more-info"),
        (_states(source="unavailable"), "none", "more-info"),
        (_states(runtime="unavailable"), "none", "more-info"),
        (_states(manual="unknown"), "none", "more-info"),
        (_states(abort=True), "none", "more-info"),
        (_states(enabled=False), "none", "more-info"),
    )
    for states, expected_display, expected_action in cases:
        assert _eval(visibility, states) == expected_display, states
        assert _eval(action, states) == expected_action, states
