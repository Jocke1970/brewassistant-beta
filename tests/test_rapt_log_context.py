"""Verify additive source logging with fake HA and no physical control.

The HLT fixture loads the actual runtime/trace/recorder modules. The Audit
extension is executed against a stub to test tuple preservation and identity
coalescing without importing a full Home Assistant installation.
"""

from __future__ import annotations

import ast
import asyncio
import json
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

from test_hlt_runtime import rig  # noqa: F401 - shared fake-HA fixture

ROOT = Path(__file__).resolve().parents[1]
AUDIT_EXTENSION = ROOT / "custom_components/brewassistant/brewday/brewday_rapt_audit_context.py"
IDENTITY_INSTALLER = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_rapt_identity_guard.py"
HLT_RUNTIME = ROOT / "custom_components/brewassistant/hlt/runtime.py"
HLT_TRACE = ROOT / "custom_components/brewassistant/hlt/trace.py"
HLT_RECORDER = ROOT / "custom_components/brewassistant/hlt/flight_recorder.py"


def _rows(rig):
    trace = next((rig.root / "brewassistant/logs").glob("hlt-sim-*.jsonl"))
    return [json.loads(line) for line in trace.read_text(encoding="utf-8").splitlines()]


def test_hlt_trace_uses_the_selected_rapt_snapshot_and_preserves_bt(rig):
    at = rig.started + timedelta(minutes=1)
    rig.brewday.update(
        source="RAPT BrewZilla Profile", runtime_state="running",
        source_status="active", stage="Mash", step="Ramp to 71.8°C",
        target_temperature=71.8, target_temperature_source="rapt_profile_step",
        profile_session_id="rapt-session-A", profile_step_id="mash-A",
        profile_step_number=2, profile_source_available=True,
        profile_stop_guard_active=False, operator_abort_active=False,
    )
    rig.sample(at, bz_power=440, bz_util=20, current=71.8, device_target=71.8)
    rig.hass.values["sensor.brewfather_brew_tracker_status"] = SimpleNamespace(
        state="brewing", last_updated=at,
        attributes={"step_target_temperature": 40},
    )
    first = asyncio.run(rig.runtime.async_hlt_simulation_tick(rig.hass, rig.entry, now=at))
    assert first["bz_ramp_requested"] is True
    row = _rows(rig)[-1]
    assert row["schema_version"] == 2
    assert row["brewday_source"] == "RAPT BrewZilla Profile"
    assert row["brewday_target_c"] == 71.8
    assert row["brewday_target_source"] == "rapt_profile_step"
    assert row["rapt_profile_session_id"] == "rapt-session-A"
    assert row["rapt_profile_step_id"] == "mash-A"
    assert row["rapt_profile_step_number"] == 2
    assert row["rapt_profile_source_available"] is True
    assert row["physical_writes"] is False
    assert row["bz_power_cap_w"] is None

    # Raw BT changes cannot alter RAPT; a selected step transition must create
    # a new row even within the pre-existing 30-second sample interval.
    at += timedelta(seconds=2)
    rig.sample(at, bz_power=440, bz_util=20, current=71.8, device_target=71.8)
    rig.hass.values["sensor.brewfather_brew_tracker_status"].attributes["step_target_temperature"] = 99
    rig.brewday.update(step="Ramp to 71.8°C", profile_step_id="mash-B", profile_step_number=3)
    second = asyncio.run(rig.runtime.async_hlt_simulation_tick(rig.hass, rig.entry, now=at))
    assert second["bz_ramp_requested"] is True
    rows = _rows(rig)
    assert len(rows) >= 2
    assert rows[-1]["record_type"] == "transition"
    assert rows[-1]["rapt_profile_step_id"] == "mash-B"
    assert rows[-1]["brewday_source"] == "RAPT BrewZilla Profile"
    assert rows[-1]["brewday_target_c"] == 71.8
    assert rows[-1]["physical_writes"] is False
    assert rig.hass.values["sensor.brewfather_brew_tracker_status"].attributes["step_target_temperature"] == 99


def test_hlt_trace_does_not_convert_missing_rapt_identity_into_fiction(rig):
    at = rig.started + timedelta(minutes=1)
    rig.brewday.update(source="RAPT BrewZilla Profile", runtime_state="running",
                       source_status="unavailable", stage="Mash", step="Mash",
                       target_temperature=None, target_temperature_source=None,
                       profile_session_id=None, profile_step_id=None,
                       profile_step_number=None, profile_source_available=False)
    rig.sample(at, bz_power=440, bz_util=20, current=65, device_target=65)
    result = asyncio.run(rig.runtime.async_hlt_simulation_tick(rig.hass, rig.entry, now=at))
    row = _rows(rig)[-1]
    assert result["last_result"].virtual_heater_on is False
    assert row["brewday_source"] == "RAPT BrewZilla Profile"
    assert row["brewday_target_c"] is None
    assert row["rapt_profile_session_id"] is None
    assert row["rapt_profile_step_id"] is None
    assert row["rapt_profile_source_available"] is False
    assert row["bz_power_cap_pct"] is None


def test_audit_extension_preserves_legacy_fields_and_separates_rapt_step_signatures():
    tree = ast.parse(AUDIT_EXTENSION.read_text(encoding="utf-8"))
    env = {"json": json}
    declarations = [node for node in tree.body
                    if isinstance(node, ast.Assign) and any(
                        isinstance(target, ast.Name) and target.id in {
                            "_INSTALLED", "_PREVIOUS_SIGNATURE", "EXTRA_RUNTIME_FIELDS",
                            "EXTRA_RESULT_FIELDS", "IDENTITY_FIELDS"}
                        for target in node.targets)]
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name in {"_source_aware_signature", "install_rapt_audit_context"}]
    exec(compile(ast.Module(body=declarations + functions, type_ignores=[]),
                 str(AUDIT_EXTENSION), "exec"), env)
    audit = SimpleNamespace(
        RUNTIME_FIELDS=("source", "stage", "target_temperature"),
        BREWZILLA_RESULT_FIELDS=("requested_target", "control_reason"),
        _event_signature=lambda event: f"legacy:{event.get('source')}",
    )
    env["audit"] = audit
    install = env["install_rapt_audit_context"]
    install()
    install()
    assert audit.RUNTIME_FIELDS.count("source") == 1
    assert audit.RUNTIME_FIELDS.count("profile_session_id") == 1
    assert audit.RUNTIME_FIELDS.count("profile_step_id") == 1
    assert "requested_target" in audit.BREWZILLA_RESULT_FIELDS
    assert "rapt_sparge_local_target_agrees" in audit.BREWZILLA_RESULT_FIELDS
    base = {"source": "RAPT BrewZilla Profile", "profile_session_id": "A",
            "profile_step_id": "step-one"}
    changed = {**base, "profile_step_id": "step-two"}
    assert audit._event_signature(base) != audit._event_signature(changed)
    assert audit._event_signature(base).startswith("legacy:")
    assert "brewday_rapt_audit_context.install_rapt_audit_context()" in IDENTITY_INSTALLER.read_text(encoding="utf-8")


def test_log_additions_are_read_only_and_keep_existing_fields():
    runtime = HLT_RUNTIME.read_text(encoding="utf-8")
    trace = HLT_TRACE.read_text(encoding="utf-8")
    recorder = HLT_RECORDER.read_text(encoding="utf-8")
    assert "source_context=_brewday_trace_context(brewday)" in runtime
    assert "build_brewday_runtime_snapshot(hass)" in runtime
    assert "brewfather_brew_tracker" not in runtime
    assert "SOURCE_CONTEXT_FIELDS" in trace
    assert '"schema_version": SCHEMA_VERSION' in trace
    assert '"physical_writes": False' in trace
    assert '"bz_power_cap_w": None' in trace
    assert "hass.services" not in trace
    assert "hass.services" not in recorder
