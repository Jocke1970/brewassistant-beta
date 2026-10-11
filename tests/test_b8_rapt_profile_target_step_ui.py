"""RAPT profile UI truthfulness with fresh, missing and stale RCL observations.

Exercise the real JS card templates using a fake HA state bag. This is display
testing only, with no RCL calls, brewday mutation or physical actuation.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import shutil
import subprocess

import pytest
import yaml


CARDS = Path(__file__).resolve().parents[1] / "dashboard" / "cards"


def _render(template: str, bag: dict) -> str:
    js = template.strip().removeprefix("[[[").removesuffix("]]]").strip()
    script = (
        "const states = " + json.dumps(bag) + ";\n"
        "function render() {\n" + js + "\n}\n"
        "process.stdout.write(String(render()));\n"
    )
    return subprocess.run(
        ["node", "-e", script], check=True, text=True, capture_output=True,
    ).stdout


def _scenario(*, target=0, step_no=0, step_count=0, source_age=3,
              contract=True, ba_age=0.1, source_available=True):
    updated = datetime.now(timezone.utc) - timedelta(seconds=source_age)
    stamp = updated.isoformat()
    profile = {
        "entity_id": "binary_sensor.brewzilla_profile_active",
        "state": "on" if source_available else "unavailable",
        "last_reported": stamp,
        "attributes": {
            "ba_source": "rapt_cloud_link_brewzilla_profile_runtime",
            "profile_contract_complete": contract,
            "profile_name": "BrewZilla profile",
            "step_name": "Mash Rest",
            "step_number": step_no,
            "step_count": step_count,
            "step_target_temperature": target,
            "next_step_name": "Mash Out",
            "next_step_target_temperature": 77,
            "step_length": 3600,
            "step_end_type": "duration",
        },
    }
    return {
        "binary_sensor.brewzilla_profile_active": profile,
        "sensor.brewassistant_brewday_runtime_summary": {
            "attributes": {
                "source_entity": profile["entity_id"],
                "resync_required": False,
            }
        },
        "sensor.brewassistant_brewday_runtime_state": {"state": "running"},
        "sensor.brewassistant_brewday_runtime_stage": {"state": "Mash"},
        "sensor.brewassistant_brewday_runtime_step": {"state": "Mash Rest"},
        "sensor.brewassistant_brewday_runtime_next_step": {"state": "Mash Out"},
        "sensor.brewassistant_brewday_target_temperature": {"state": "31"},
        "sensor.brewassistant_brewday_snapshot_age_minutes": {"state": str(ba_age)},
        "sensor.brewzilla_temperature": {
            "state": "30.8", "last_reported": stamp
        },
        "sensor.brewassistant_brewzilla_control_reason": {"attributes": {}},
    }


@pytest.mark.parametrize("name", ["rapt_profile_runtime_sv.yaml", "rapt_profile_runtime.yaml"])
def test_rapt_target_steps_and_freshness_not_invented(name):
    data = yaml.safe_load((CARDS / name).read_text(encoding="utf-8"))
    assert data["type"] == "conditional"
    assert data["card"]["type"] == "custom:button-card"
    assert data["card"]["tap_action"]["action"] == "more-info"
    label = data["card"]["label"]
    assert "profileReadable" in label
    assert "sourceAgeSeconds" in label or "stale" in label
    assert "stepNo > 0" in label
    assert "stepCount > 0" in label
    assert "rawTarget === 0 && !cooling" in label
    assert "BA-mål (referens)" in label or "BA target (reference)" in label
    assert "RAPT äger profil" in label or "RAPT owns profile" in label
    if not shutil.which("node"):
        pytest.skip("Node not installed")

    # 0°C on a hot-side Mash Rest and 0/0 are missing data, not valid measurements.
    zero = _render(label, _scenario())
    assert "Mash Rest" in zero
    assert "0/0" not in zero
    assert "0.0 °C" not in zero
    assert "31.0 °C" in zero  # Explicit BA-reference only, not RAPT target
    assert "—" in zero
    assert "RAPT-DATA" in zero or "RAPT DATA" in zero

    valid = _render(label, _scenario(target=66, step_no=3, step_count=7))
    assert "66.0 °C" in valid
    assert "3/7" in valid
    assert "Mash Rest" in valid
    assert "RAPT-DATA" not in valid and "RAPT DATA" not in valid

    stale = _render(label, _scenario(target=66, step_no=3, step_count=7, source_age=155, ba_age=2.5))
    assert "STALE RCL DATA" in stale or "RCL-DATA FÖR GAMMAL" in stale
    assert "66.0 °C" not in stale
    assert "31.0 °C" not in stale
    assert "3/7" not in stale
    assert "Mash Rest" in stale  # Last-known description is labelled uncertain

    incomplete = _render(label, _scenario(target=66, step_no=3, step_count=7, contract=False))
    assert "66.0 °C" not in incomplete
    assert "3/7" not in incomplete
    assert "RAPT-DATA" in incomplete or "RAPT DATA" in incomplete
