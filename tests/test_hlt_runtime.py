"""Exercise the REAL HLT runner, simulator and trace writer without Home Assistant."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1] / "custom_components/brewassistant/hlt"
BASE = "hlt_runtime_contract.brewassistant"


def _package(monkeypatch, name):
    obj = ModuleType(name)
    obj.__path__ = []
    monkeypatch.setitem(sys.modules, name, obj)
    return obj


def _module(monkeypatch, name, **attrs):
    obj = ModuleType(name)
    obj.__dict__.update(attrs)
    monkeypatch.setitem(sys.modules, name, obj)
    return obj


def _load(monkeypatch, filename):
    name = f"{BASE}.hlt.{filename}"
    spec = spec_from_file_location(name, ROOT / f"{filename}.py")
    module = module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def rig(monkeypatch, tmp_path):
    _package(monkeypatch, "homeassistant")
    _module(monkeypatch, "homeassistant.core", callback=lambda func: func)
    _package(monkeypatch, "homeassistant.helpers")
    callbacks = []
    _module(monkeypatch, "homeassistant.helpers.event",
            async_track_time_interval=lambda hass, cb, interval: callbacks.append((cb, interval)) or (lambda: None))
    _package(monkeypatch, "hlt_runtime_contract")
    _package(monkeypatch, BASE)
    _package(monkeypatch, BASE + ".hlt")
    _package(monkeypatch, BASE + ".brewday")
    _package(monkeypatch, BASE + ".brewzilla")

    started = datetime(2026, 9, 16, 10, tzinfo=timezone.utc)
    audit = SimpleNamespace(active=True, started_at=started, events=[])
    async def save(_hass):
        return None
    _module(monkeypatch, BASE + ".brewday.brewday_audit",
            get_brewday_audit_log=lambda hass: audit,
            _event_base=lambda hass, event_type, note=None: {"event_type": event_type, "note": note},
            _append_event=lambda log, event: log.events.append(event),
            async_save_brewday_audit_log=save)
    brewday = {"runtime_state": "running", "stage": "Mash", "step": "Saccharification"}
    batch = {"sparge_water_l": 10.0}
    _module(monkeypatch, BASE + ".brewday.brewday_runtime",
            build_brewday_runtime_snapshot=lambda hass: brewday)
    _module(monkeypatch, BASE + ".brewzilla.brewzilla_learning",
            build_brewzilla_learning_snapshot=lambda hass: batch)

    _load(monkeypatch, "simulation")
    _load(monkeypatch, "trace")
    _load(monkeypatch, "ha_adapter")
    _load(monkeypatch, "flight_recorder")
    runtime = _load(monkeypatch, "runtime")

    class State:
        def __init__(self, value, when):
            self.state = str(value)
            self.last_updated = when

    class Hass:
        def __init__(self):
            self.data = {}
            self.values = {}
            self.states = SimpleNamespace(get=lambda key: self.values.get(key))
            self.config = SimpleNamespace(path=lambda: str(tmp_path))
            self.tasks = []
        async def async_add_executor_job(self, func, *args):
            return func(*args)
        def async_create_task(self, awaitable):
            self.tasks.append(awaitable)
            return asyncio.create_task(awaitable)

    hass = Hass()
    entry = SimpleNamespace(options={"hlt_sim_usable_budget_w": 2750,
                                     "hlt_sim_heater_w": 1500}, data={})
    def samples(when, bz_power=440, bz_util=20):
        hass.values["sensor.brewzilla_power"] = State(bz_power, when)
        hass.values["number.brewzilla_heat_utilization"] = State(bz_util, when)
    return SimpleNamespace(runtime=runtime, hass=hass, entry=entry,
                           batch=batch, brewday=brewday, audit=audit,
                           sample=samples, started=started, root=tmp_path,
                           callbacks=callbacks)


def test_real_runner_records_reclaim_and_never_calls_hardware(rig):
    at = rig.started + timedelta(minutes=1)
    rig.sample(at)
    first = asyncio.run(rig.runtime.async_hlt_simulation_tick(rig.hass, rig.entry, now=at))
    assert first["last_result"].virtual_heater_on is True
    assert first["scenario_only"] is True
    assert rig.audit.events[-1]["event_type"] == "hlt_sim_heater_on"
    files = list((rig.root / "brewassistant/logs").glob("hlt-sim-*.jsonl"))
    assert len(files) == 1
    records = [json.loads(row) for row in files[0].read_text().splitlines()]
    assert records[0]["physical_writes"] is False
    assert records[0]["bz_power_observed_w"] == 440
    assert records[0]["hlt_virtual_heater_on"] is True

    at += timedelta(seconds=30)
    rig.sample(at, bz_power=2200, bz_util=100)
    reclaim = asyncio.run(rig.runtime.async_hlt_simulation_tick(rig.hass, rig.entry, now=at))
    assert reclaim["last_result"].state == "YIELDING"
    assert not reclaim["last_result"].virtual_heater_on
    assert rig.audit.events[-1]["event_type"] == "hlt_sim_yield"
    at += timedelta(seconds=4)
    rig.sample(at, bz_power=2200, bz_util=100)
    released = asyncio.run(rig.runtime.async_hlt_simulation_tick(rig.hass, rig.entry, now=at))
    assert released["last_result"].hlt_reservation_w == 0
    assert released["last_result"].brewzilla_would_grant_w == 2200
    assert len(files[0].read_text().splitlines()) >= 3


def test_missing_volume_or_inactive_session_writes_nothing(rig):
    at = rig.started + timedelta(minutes=1)
    rig.sample(at)
    rig.batch["sparge_water_l"] = None
    missing = asyncio.run(rig.runtime.async_hlt_simulation_tick(rig.hass, rig.entry, now=at))
    assert missing["status"] == "waiting_for_sparge_volume"
    assert not (rig.root / "brewassistant/logs").exists()
    rig.audit.active = False
    stopped = asyncio.run(rig.runtime.async_hlt_simulation_tick(rig.hass, rig.entry, now=at))
    assert stopped["status"] == "waiting_for_brewday_recorder"


def test_no_sparge_remains_idle_and_logs_explicit_zero_volume(rig):
    rig.batch["sparge_water_l"] = 0
    at = rig.started + timedelta(minutes=1)
    rig.sample(at)
    out = asyncio.run(rig.runtime.async_hlt_simulation_tick(rig.hass, rig.entry, now=at))
    assert out["last_result"].state == "IDLE"
    assert not out["last_result"].virtual_heater_on
    file = next((rig.root / "brewassistant/logs").glob("*.jsonl"))
    record = json.loads(file.read_text().splitlines()[0])
    assert record["hlt_volume_l"] == 0
    assert record["hlt_sparge_required"] is False


def test_setup_registers_unloadable_30_second_timer(rig):
    unsubscribe = rig.runtime.async_setup_hlt_simulation(rig.hass, rig.entry)
    assert callable(unsubscribe)
    assert len(rig.callbacks) == 1
    assert rig.callbacks[0][1] == timedelta(seconds=30)
