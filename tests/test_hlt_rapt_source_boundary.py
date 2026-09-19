"""HLT SIM-1 is a reader of selected Brewday input, never a second controller.

These tests reuse the real HLT runtime with a stubbed normalized Brewday
snapshot and fake HA states. They test this consumer seam, not a full HA/RAPT
integration or proof of physical electrical safety.
"""

from __future__ import annotations

import asyncio
import json
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

from test_hlt_runtime import rig  # noqa: F401 - shared fake-HA fixture


ROOT = Path(__file__).resolve().parents[1]
HLT_RUNTIME = ROOT / "custom_components/brewassistant/hlt/runtime.py"
HLT_TRACE = ROOT / "custom_components/brewassistant/hlt/trace.py"


def _bt_update(rig, at, *, status, target):
    # BT sensors remain readable and may change independently of RAPT.
    rig.hass.values["sensor.brewfather_brew_tracker_status"] = SimpleNamespace(
        state=status, last_updated=at, attributes={"step_target_temperature": target}
    )
    rig.hass.values["sensor.brewfather_brew_tracker_target_temperature"] = SimpleNamespace(
        state=str(target), last_updated=at
    )


def test_bt_updates_do_not_change_rapt_ramp_veto_or_hlt_trace(rig):
    at = rig.started + timedelta(minutes=1)
    rig.brewday.update(source="RAPT BrewZilla Profile", runtime_state="running",
                       stage="Mash", step="Ramp to 71.8°C", target_temperature=71.8)
    rig.sample(at, bz_power=440, bz_util=20, current=71.8, device_target=71.8)
    rig.hass.values["sensor.brewassistant_brewday_target_temperature"] = SimpleNamespace(
        state="71.8", last_updated=at
    )
    _bt_update(rig, at, status="brewing", target=40)
    first = asyncio.run(rig.runtime.async_hlt_simulation_tick(rig.hass, rig.entry, now=at))
    assert first["bz_ramp_requested"] is True
    assert first["bz_cruising_observed"] is False
    assert first["last_result"].state == "WAITING_FOR_POWER"
    assert first["last_result"].virtual_heater_on is False

    at += timedelta(seconds=30)
    rig.sample(at, bz_power=440, bz_util=20, current=71.8, device_target=71.8)
    _bt_update(rig, at, status="finished", target=99)
    second = asyncio.run(rig.runtime.async_hlt_simulation_tick(rig.hass, rig.entry, now=at))
    assert second["bz_ramp_requested"] is True
    assert second["bz_cruising_observed"] is False
    assert second["last_result"].state == "WAITING_FOR_POWER"
    assert second["last_result"].virtual_heater_on is False
    assert rig.hass.values["sensor.brewfather_brew_tracker_target_temperature"].state == "99"

    path = next((rig.root / "brewassistant/logs").glob("hlt-sim-*.jsonl"))
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) >= 2
    for row in rows:
        assert row["stage"] == "Mash"
        assert row["step"] == "Ramp to 71.8°C"
        assert row["physical_writes"] is False
        assert row["bz_brewday_target_ha_c"] == 71.8
        assert row["bz_power_cap_w"] is None
        assert row["bz_power_cap_pct"] is None


def test_rapt_cruise_remains_virtual_only_despite_competing_bt_ramp(rig):
    at = rig.started + timedelta(minutes=1)
    rig.brewday.update(source="RAPT BrewZilla Profile", runtime_state="running",
                       stage="Sparge", step="Sparge", target_temperature=65.0)
    rig.sample(at, bz_power=440, bz_util=20, current=65, device_target=65)
    _bt_update(rig, at, status="brewing", target=95)
    result = asyncio.run(rig.runtime.async_hlt_simulation_tick(rig.hass, rig.entry, now=at))
    assert result["bz_cruising_observed"] is True
    assert result["bz_ramp_requested"] is False
    assert result["last_result"].virtual_heater_on is True
    assert result["last_result"].brewzilla_would_cap_utilization is None
    assert result["scenario_only"] is True
    path = next((rig.root / "brewassistant/logs").glob("hlt-sim-*.jsonl"))
    row = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert row["physical_writes"] is False
    assert row["brewzilla_priority"] == "absolute_unthrottled"


def test_hlt_consumer_uses_normalized_brewday_not_raw_bt_or_actuators():
    runtime = HLT_RUNTIME.read_text(encoding="utf-8")
    trace = HLT_TRACE.read_text(encoding="utf-8")
    assert "build_brewday_runtime_snapshot(hass)" in runtime
    assert "brewfather_brew_tracker" not in runtime
    assert "brewfather_brewtracker" not in runtime
    assert "hass.services" not in runtime
    assert "hass.services" not in trace
    assert '"physical_writes": False' in trace
    assert '"bz_power_cap_w": None' in trace
    assert '"bz_power_cap_pct": None' in trace
    assert "_ha_diagnostics(hass, inputs.timestamp_s)" in trace
