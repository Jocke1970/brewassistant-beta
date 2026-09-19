"""No Home Assistant installation needed: uploadable HLT JSONL trace tests."""
import asyncio
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace as Obj

import pytest

spec = importlib.util.spec_from_file_location(
    "hlt_trace", Path(__file__).resolve().parents[1]
    / "custom_components/brewassistant/hlt/trace.py"
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def sample(t, state="HEATING", events=()):
    inp = Obj(timestamp_s=t, sparge_required=True, enable_hlt=True,
              measured_hlt_temperature_c=None, thermostat_heating=None,
              brewzilla_measured_w=800, brewzilla_requested_utilization=35,
              brewzilla_cruising=True, brewzilla_ramp_requested=False,
              brewzilla_unconstrained=True)
    result = Obj(events=events, state=state, reason="simulated", virtual_heater_on=True,
                 temperature_source="estimated", temperature_c=42.0,
                 temperature_uncertainty="model only", power_budget_verified=False,
                 thermostat_calibrated=False, brewzilla_request_w=770,
                 brewzilla_would_grant_w=None, brewzilla_would_cap_utilization=None,
                 hlt_reservation_w=1500, total_reserved_w=2300, available_w=450)
    return inp, result


class FakeHass:
    def __init__(self, root):
        self.data = {}
        self.config = Obj(path=lambda: str(root))

    async def async_add_executor_job(self, fn, *args):
        return await asyncio.to_thread(fn, *args)


def test_sample_rate_and_immediate_reclaim(tmp_path):
    async def run():
        hass = FakeHass(tmp_path)
        path = None
        for t, state, events in [(0, "HEATING", ()), (10, "HEATING", ()),
                                 (11, "YIELDING", ("virtual_hlt_off_requested",)),
                                 (14, "YIELDING", ("virtual_hlt_off_confirmed",)),
                                 (20, "YIELDING", ()), (44, "YIELDING", ())]:
            inp, result = sample(t, state, events)
            written = await mod.async_record_hlt_trace(
                hass, "brewday-42", inp, result,
                stage="mash", usable_budget_w=2750, hlt_target_c=78,
            )
            path = written or path
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        assert len(rows) == 4
        assert rows[1]["events"] == ["virtual_hlt_off_requested"]
        assert rows[2]["events"] == ["virtual_hlt_off_confirmed"]
        assert rows[0]["hlt_temp_measured_c"] is None
        assert rows[0]["hlt_temp_source"] == "estimated"
        assert rows[0]["bz_power_observed_w"] == 800
        assert rows[0]["bz_cruising_observed"] is True
        assert rows[0]["bz_ramp_requested"] is False
        assert rows[0]["brewzilla_priority"] == "absolute_unthrottled"
        assert rows[0]["bz_power_cap_w"] is None
        assert rows[0]["bz_power_cap_pct"] is None
        assert rows[0]["usable_budget_w"] == 2750
        assert rows[0]["physical_writes"] is False
    asyncio.run(run())


def test_session_rotation_and_safe_path(tmp_path):
    async def run():
        hass = FakeHass(tmp_path)
        a, b = sample(0)
        first = await mod.async_record_hlt_trace(hass, "../private", a, b)
        second = await mod.async_record_hlt_trace(hass, "new-session", a, b)
        assert first != second
        assert first.parent == second.parent == tmp_path / "brewassistant" / "logs"
        assert first.exists() and second.exists()
        assert "private" not in first.name
        assert len(first.read_text().splitlines()) == 1
    asyncio.run(run())


def test_invalid_timestamp_and_interval(tmp_path):
    with pytest.raises(ValueError):
        mod.HLTTraceRecorder(tmp_path, "batch", sample_interval_s=0)
    recorder = mod.HLTTraceRecorder(tmp_path, "batch")
    inputs, result = sample(float("nan"))
    with pytest.raises(ValueError):
        recorder.make_record(inputs, result)
