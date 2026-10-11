"""b11: healthy BA assist/rearm are contextual; emergency ABORT always present.

Execute JS from actual SV+EN button-card YAML in isolated Node. Pure UI
visibility must never substitute for protected backend service guards.
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
CARDS = ROOT / "dashboard" / "cards"


def cards(path: str):
    doc = yaml.safe_load((CARDS / path).read_text(encoding="utf-8"))
    assert doc["type"] == "vertical-stack"
    children = doc["cards"]
    start = next(c for c in children if c.get("entity") == "sensor.brewassistant_brewday_start_status")
    emergency = next(
        c for c in children
        if c.get("type") == "vertical-stack" and any(
            inner.get("entity") == "button.brewassistant_abort_brewday"
            for inner in c.get("cards", [])
        )
    )
    assert len(emergency["cards"]) == 2
    abort, rearm = emergency["cards"]
    assert abort["entity"] == "button.brewassistant_abort_brewday"
    assert rearm["entity"] == "button.brewassistant_rearm_brewday_control"
    return children, start, emergency, abort, rearm


def display(card):
    return next(s["display"] for s in card["styles"]["card"] if "display" in s)


def states(*, start="running", checks=("passed", "passed"), reasons=(),
           runtime="running", operator="running", observe="off",
           summary_abort=False, fallback=False, resync=False,
           profile_available=True):
    return {
        "sensor.brewassistant_brewday_start_status": {
            "state": start,
            "attributes": {
                "checks": [{"id": str(i), "status": s} for i, s in enumerate(checks)],
                "reasons": list(reasons),
            },
        },
        "sensor.brewassistant_brewday_runtime_summary": {
            "state": "running",
            "attributes": {
                "operator_abort_active": summary_abort,
                "fallback_active": fallback,
                "resync_required": resync,
                "profile_source_available": profile_available,
            },
        },
        "sensor.brewassistant_brewday_runtime_state": {"state": runtime},
        "sensor.brewassistant_brewday_operator_control_state": {"state": operator},
        "switch.brewassistant_brewzilla_observe_only": {"state": observe},
    }


def js_evaluate(snippet, data):
    if not shutil.which("node"):
        pytest.skip("Node required for JS execution")
    script = (
        "const states = " + json.dumps(data, ensure_ascii=False) + ";\n"
        + "function render() {\n" +
        snippet.strip().removeprefix("[[[").removesuffix("]]]").strip()
        + "\n}\n"
        + "process.stdout.write(String(render()));\n"
    )
    return subprocess.run(
        ["node", "-e", script],
        text=True, capture_output=True, check=True,
    ).stdout


@pytest.mark.parametrize("filename", [
    "brewday_control_status_sv.yaml", "brewday_control_status.yaml"
])
def test_assist_only_hidden_when_running_and_every_check_truly_green(filename):
    children, start, emergency, abort, rearm = cards(filename)
    assert start["tap_action"]["service"] == "brewassistant.brewday_start_verified"
    assert "switch.turn_off" not in str(start)
    assert start["update_timer"] == "5s"
    assert "allGreen" in display(start)
    assert "sensor.brewassistant_brewday_runtime_summary" in display(start)

    # Healthy, all green with no attention needed -> collapse red BA hero.
    assert js_evaluate(display(start), states()) == "none"

    # The separately displayed blue READ-ONLY panel remains authoritative:
    # no need to repeat a completely green BA START preflight just because
    # READ-ONLY has its own card and may be toggled during normal operation.
    assert js_evaluate(display(start), states(observe="on")) == "none"

    # No instant hiding on missing/incomplete diagnostics, failed check,
    # pending verification, source issue, source loss or ABORT.
    variants = (
        states(start="ready"),
        states(start="starting"),
        states(start="waiting"),
        states(start="blocked"),
        states(start="aborted"),
        states(checks=()),
        states(checks=("passed", "warning")),
        states(checks=("passed", "pending")),
        states(checks=("passed", "failed")),
        states(reasons=("Operator confirmation required",)),
        states(runtime="unavailable"),
        states(runtime="resync_required"),
        states(runtime="source_unavailable"),
        states(operator="aborted"),
        states(summary_abort=True),
        states(resync=True),
        states(fallback=True),
        states(profile_available=False),
    )
    for data in variants:
        assert js_evaluate(display(start), data) == "grid", data


@pytest.mark.parametrize("filename", [
    "brewday_control_status_sv.yaml", "brewday_control_status.yaml"
])
def test_rearm_only_when_abort_is_active_and_emergency_always_present(filename):
    children, start, emergency, abort, rearm = cards(filename)
    assert abort["tap_action"]["action"] == "call-service"
    assert abort["tap_action"]["service"] == "button.press"
    assert abort["tap_action"]["target"]["entity_id"] == "button.brewassistant_abort_brewday"
    assert "display" not in str(abort["styles"])
    assert "conditions" not in emergency
    assert "confirmation" in rearm["tap_action"]
    assert rearm["tap_action"]["target"]["entity_id"] == "button.brewassistant_rearm_brewday_control"

    assert js_evaluate(display(rearm), states()) == "none"
    assert js_evaluate(display(rearm), states(start="blocked", runtime="resync_required")) == "none"
    assert js_evaluate(display(rearm), states(operator="aborted")) == "grid"
    assert js_evaluate(display(rearm), states(runtime="aborted")) == "grid"
    assert js_evaluate(display(rearm), states(summary_abort=True)) == "grid"

    # The backend-guarded rearm service may only be invoked when its
    # operator control state is aborted, even if a separate ABORT marker
    # has gone out of sync.
    tap = rearm["tap_action"]["action"]
    assert js_evaluate(tap, states(summary_abort=True)) == "none"
    assert js_evaluate(tap, states(operator="aborted")) == "call-service"


@pytest.mark.parametrize("filename", [
    "brewday_operator_actions_sv.yaml", "brewday_operator_actions.yaml",
])
def test_separate_operator_actions_keeps_existing_aborted_conditional(filename):
    doc = yaml.safe_load((CARDS / filename).read_text(encoding="utf-8"))
    assert doc["type"] == "conditional"
    stack = doc["card"]["cards"]
    assert stack[0]["entity"] == "button.brewassistant_abort_brewday"
    rearms = [c for c in stack if c.get("type") == "conditional"
              and "button.brewassistant_rearm_brewday_control" in str(c)]
    assert len(rearms) == 1
    assert rearms[0]["conditions"] == [{
        "entity": "sensor.brewassistant_brewday_operator_control_state",
        "state": "aborted",
    }]
