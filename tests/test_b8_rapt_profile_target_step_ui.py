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
              contract=True, ba_age=0.1, source_available=True,
              step_name="Mash Rest", step_id="step-3", telemetry_step_id=None,
              measured_temp=30.8):
    updated = datetime.now(timezone.utc) - timedelta(seconds=source_age)
    stamp = updated.isoformat()
    profile = {
        "entity_id": "binary_sensor.brewzilla_profile_active",
        "state": "on" if source_available else "unavailable",
        "last_reported": stamp,
        "attributes": {
            "ba_source": "rapt_cloud_link_brewzilla_profile_runtime",
            "raw_device_id": "bz-1",
            "profile_contract_complete": contract,
            "profile_name": "BrewZilla profile",
            "step_id": step_id,
            "step_name": step_name,
            "step_number": step_no,
            "step_count": step_count,
            "step_target_temperature": target,
            "next_step_name": "Mash Out",
            "next_step_target_temperature": 77,
            "step_length": 3600,
            "step_end_type": "duration",
        },
    }
    bag = {
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
            "state": str(measured_temp), "last_reported": stamp
        },
        "sensor.brewassistant_brewzilla_control_reason": {"attributes": {}},
    }
    if telemetry_step_id is not None:
        bag["sensor.rapt_cloud_link_brewzilla_debug"] = {
            "state": "1",
            "attributes": {
                "ba_source": "rapt_cloud_link_brewzilla_debug",
                "devices": [{
                    "id": "bz-1",
                    "profile_runtime": {
                        "active_profile_step_id": step_id,
                        "telemetry_profile_step_id": telemetry_step_id,
                    },
                }],
            },
        }
    return bag

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

    assert "stepIdentityMismatch" in label
    assert "telemetry_profile_step_id" in label
    assert "valueTile" in label
    assert "stepDetail" in label

    # 0°C hot-side target and 0/0 position never appear as valid measurements.
    zero = _render(label, _scenario())
    assert "Mash Rest" in zero
    assert "0/0" not in zero
    assert "0.0 °C" not in zero
    assert "31.0 °C" in zero  # reported as red diagnostic, never trusted
    assert 'font-size:14px;">31.0 °C</b>' not in zero
    assert "RAPT-DATA" in zero or "RAPT DATA" in zero
    assert "EJ VERIFIERAT" in zero or "UNVERIFIED" in zero

    valid = _render(label, _scenario(target=66, step_no=3, step_count=7,
                                     telemetry_step_id="step-3"))
    assert "66.0 °C" in valid and "3/7" in valid
    assert "Mash Rest" in valid
    assert "RAPT-DATA" not in valid and "RAPT DATA" not in valid
    assert "RCL active step ID differs" not in valid
    assert "RCL aktivt steg-ID skiljer" not in valid

    # Temperature changes alone are not a profile-step transition.
    warmer = _render(label, _scenario(target=66, step_no=3, step_count=7,
                                      telemetry_step_id="step-3", measured_temp=38.1))
    assert "38.1 °C" in warmer
    assert "3/7" in warmer and "Mash Rest" in warmer

    # An actual RAPT step transition is reflected without BA changing its own
    # independent runtime-step sensor. RCL step identity is authoritative.
    new_step = _render(label, _scenario(target=78, step_no=4, step_count=7,
                                        step_name="Mash Out", step_id="step-4",
                                        telemetry_step_id="step-4"))
    assert "4/7" in new_step and "Mash Out" in new_step
    assert "78.0 °C" in new_step

    # Stale values are highlighted in RED as unverified diagnostics but must
    # NEVER masquerade as the big trusted target/step number.
    stale = _render(label, _scenario(target=66, step_no=3, step_count=7,
                                    source_age=155, ba_age=2.5))
    assert "STALE RCL DATA" in stale or "RCL-DATA FÖR GAMMAL" in stale
    assert 'font-size:14px;">66.0 °C</b>' not in stale
    assert 'font-size:14px;">3/7</b>' not in stale
    assert "66.0 °C" in stale and "3/7" in stale  # Red, reported only
    assert "#b71c1c" in stale
    assert "EJ VERIFIERAT" in stale or "UNVERIFIED" in stale
    assert "Mash Rest" in stale

    incomplete = _render(label, _scenario(target=66, step_no=3,
                                          step_count=7, contract=False))
    assert 'font-size:14px;">66.0 °C</b>' not in incomplete
    assert 'font-size:14px;">3/7</b>' not in incomplete
    assert "RAPT-DATA" in incomplete or "RAPT DATA" in incomplete

    # RCL's root profile step and telemetry step disagree: do not trust
    # either as a verified active target, and instruct operator to check RAPT.
    mismatch = _render(label, _scenario(
        target=66, step_no=3, step_count=7,
        step_id="step-3", telemetry_step_id="step-4"))
    assert "RCL aktivt steg-ID skiljer" in mismatch or "RCL active step ID differs" in mismatch
    assert 'font-size:14px;">66.0 °C</b>' not in mismatch
    assert 'font-size:14px;">3/7</b>' not in mismatch
    assert "#b71c1c" in mismatch

    # BA reference can become stale independently of the still-fresh RCL
    # profile; the source's correct RAPT target and step remain verified.
    older_ba = _render(label, _scenario(target=66, step_no=3, step_count=7,
                                        ba_age=2.5, telemetry_step_id="step-3"))
    assert 'font-size:14px;">66.0 °C</b>' in older_ba
    assert 'font-size:14px;">3/7</b>' in older_ba
    assert 'font-size:14px;">31.0 °C</b>' not in older_ba
