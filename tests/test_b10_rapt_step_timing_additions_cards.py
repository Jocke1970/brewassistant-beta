"""Test real RAPT UI JavaScript with source-owned step timers and additions."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import shutil
import subprocess
import pytest
import yaml

CARDS = Path(__file__).resolve().parents[1] / "dashboard" / "cards"


def scenario(*, duration=1800, transition_seconds_ago=10, end="Duration",
             start="Start", fresh=True, alerts=True):
    stamp = (datetime.now(timezone.utc) -
             timedelta(seconds=10 if fresh else 155)).isoformat()
    transition = None if transition_seconds_ago is None else (
        datetime.now(timezone.utc) -
        timedelta(seconds=transition_seconds_ago)).isoformat()
    profile = {
        "entity_id": "binary_sensor.brewzilla_profile_active",
        "state": "on",
        "attributes": {
            "ba_source": "rapt_cloud_link_brewzilla_profile_runtime",
            "raw_device_id": "bz-1",
            "profile_observed_at": stamp,
            "profile_contract_complete": True,
            "profile_name": "Test brew",
            "step_name": "Boil",
            "step_id": "s4",
            "step_number": 4,
            "step_count": 6,
            "step_end_type": end,
            "step_duration_type": start,
            "step_length": duration,
            "step_target_temperature": 100,
            "profile_step_transition_observed_at": transition,
            "step_alerts": [
                {"text": "<b>Humle Magnum</b>", "trigger": "Duration", "length_raw": 600},
                {"text": "Kylare", "trigger": "StepEnd", "length_raw": None},
            ] if alerts else [],
        },
    }
    return {
        profile["entity_id"]: profile,
        "sensor.brewassistant_brewday_runtime_summary": {
            "attributes": {"source_entity": profile["entity_id"], "resync_required": False}},
        "sensor.brewassistant_brewday_runtime_state": {"state": "running"},
        "sensor.brewassistant_brewday_runtime_stage": {"state": "Boil"},
        "sensor.brewassistant_brewday_runtime_step": {"state": "Boil"},
        "sensor.brewassistant_brewday_runtime_next_step": {"state": "Chill Out"},
        "sensor.brewassistant_brewday_target_temperature": {"state": "100"},
        "sensor.brewassistant_brewday_snapshot_age_minutes": {"state": "0.1"},
        "sensor.brewzilla_temperature": {"state": "98", "last_updated": stamp},
        "sensor.brewassistant_brewzilla_control_reason": {"attributes": {}},
    }


def render(label, states):
    js = label.strip().removeprefix("[[[").removesuffix("]]]").strip()
    # Freeze JS Date.now relative to the fixture's observed step transition;
    # CI process startup time is not a RAPT timer signal.
    transition = states["binary_sensor.brewzilla_profile_active"]["attributes"].get(
        "profile_step_transition_observed_at"
    )
    observed = datetime.fromisoformat(transition) + timedelta(seconds=10) if transition else datetime.now(timezone.utc)
    frozen_ms = int(observed.timestamp() * 1000)
    script = ("const states = " + json.dumps(states, ensure_ascii=False) + ";\n"
              + "Date.now = () => " + str(frozen_ms) + ";\n"
              + "function render(){\n" + js + "\n}\n"
              + "process.stdout.write(String(render()));\n")
    return subprocess.run(["node", "-e", script], check=True,
                          capture_output=True, text=True).stdout


@pytest.mark.parametrize("filename", [
    "rapt_profile_runtime_sv.yaml", "rapt_profile_runtime.yaml",
])
def test_timelength_and_additions_do_not_fabricate_exact_rapt_time(filename):
    data = yaml.safe_load((CARDS / filename).read_text(encoding="utf-8"))
    label = data["card"]["label"]
    assert "profile_step_transition_observed_at" in label
    assert "step_alerts" in label
    assert "stepDataReadable" in label
    assert "durationType).toLowerCase() === 'start'" in label
    assert "alert.length_raw" in label
    assert "units unverified" in label or "enhet ej verifierad" in label
    assert "time_remaining_seconds" not in label  # no BA fake 0-min timer
    if not shutil.which("node"):
        pytest.skip("Node unavailable")

    html = render(label, scenario())
    assert "30:00" in html
    # The test controls JS time, so this is deterministic regardless of CI load.
    assert "≈ 29:50" in html
    assert "&lt;b&gt;Humle Magnum&lt;/b&gt;" in html
    assert "Kylare" in html
    assert "600" in html and ("råvärde" in html or "raw value" in html)
    assert "≈ 10:" not in html  # alert 600 is NOT a verified countdown

    no_anchor = render(label, scenario(transition_seconds_ago=None))
    assert "30:00" in no_anchor
    assert "≈ 29:" not in no_anchor
    assert "Humle Magnum" in no_anchor

    manual = render(label, scenario(end="Manual"))
    assert "30:00" not in manual
    assert "≈ 29:" not in manual
    assert "Manual" in manual or "Manuell" in manual

    target = render(label, scenario(start="Temperature"))
    assert "30:00" in target  # planned duration can remain useful
    assert "≈ 29:" not in target  # no proof timer started

    stale = render(label, scenario(fresh=False))
    assert "≈ 29:" not in stale
    assert "&lt;b&gt;Humle Magnum&lt;/b&gt;" not in stale
    assert "Källan ej verifierad" in stale or "Source unverified" in stale

    no_alerts = render(label, scenario(alerts=False))
    assert "Inga tillsatsaviseringar" in no_alerts or "No additions" in no_alerts
