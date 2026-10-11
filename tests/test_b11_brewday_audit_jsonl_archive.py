"""Regression tests for 0b11 append-only Flight Recorder files (no HA hardware)."""
from __future__ import annotations

import ast
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "custom_components/brewassistant/brewday/brewday_audit.py"
FILE = ROOT / "custom_components/brewassistant/brewday/brewday_audit_file.py"
SENSOR = ROOT / "custom_components/brewassistant/brewday/brewday_audit_sensor.py"


def archive():
    tree = ast.parse(FILE.read_text(encoding="utf-8"))
    wanted = {"new_session_file", "_absolute_path", "_append_jsonl"}
    functions = [n for n in tree.body
                 if isinstance(n, ast.FunctionDef) and n.name in wanted]
    assert {n.name for n in functions} == wanted
    module = ast.Module(body=[
        ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
        *functions,
    ], type_ignores=[])
    ns = {"_LOG_DIR": ("brewassistant", "logs"),
          "_SAFE_NAME": re.compile(r"^brewday-\d{8}T\d{6}-\d{6}Z\.jsonl$"),
          "timezone": timezone, "Path": Path, "json": json}
    exec(compile(ast.fix_missing_locations(module), str(FILE), "exec"), ns)
    return ns


def test_file_append_keeps_complete_ordered_rows(tmp_path):
    funcs = archive()
    conf = SimpleNamespace(path=lambda *bits: str(tmp_path.joinpath(*bits)))
    hass = SimpleNamespace(config=conf)
    rel = funcs["new_session_file"](datetime(2026, 10, 11, 12, 30,
                                             tzinfo=timezone.utc))
    assert rel == "brewassistant/logs/brewday-20261011T123000-000000Z.jsonl"
    path = funcs["_absolute_path"](hass, rel)
    samples = [
        {"event_type": "brewzilla_action", "actions": ["set_pump_utilization:40"],
         "note": "Bryggning 🍺", "timestamp": "2026-10-11T12:30:00Z"},
        {"event_type": "brewday_abort", "timestamp": "2026-10-11T12:31:00Z"},
        {"event_type": "flight_recorder_transition", "timestamp": "2026-10-11T12:32:00Z"},
    ]
    for row in samples:
        funcs["_append_jsonl"](path, row)
    lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert lines == samples
    assert len(lines) == 3
    assert path.stat().st_size > 0


@pytest.mark.parametrize("bad_path", [
    "../../config/secrets.yaml",
    "brewassistant/logs/../../secrets.yaml",
    "brewassistant/logs/brewday.log",
    "brewassistant/logs/evil.jsonl",
    "/config/brewassistant/logs/brewday-20261011T123000-000000Z.jsonl",
])
def test_archive_path_is_generated_only_and_cannot_escape_config(tmp_path, bad_path):
    ns = archive()
    hass = SimpleNamespace(
        config=SimpleNamespace(path=lambda *parts: str(tmp_path.joinpath(*parts)))
    )
    with pytest.raises(ValueError):
        ns["_absolute_path"](hass, bad_path)


def test_pre_release_test_history_discarded_once_then_jsonl_state_resumes():
    """Both legacy and early JSONL tests are disposable; new baseline survives reboot."""
    source = SRC.read_text(encoding="utf-8")
    tree = ast.parse(source)
    node = next(
        n for n in tree.body if isinstance(n, ast.AsyncFunctionDef)
        and n.name == "async_load_brewday_audit_log"
    )
    code = ast.Module(body=[
        ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
        node,
    ], type_ignores=[])

    class FakeStore:
        def __init__(self):
            self.payload = {
                "active": True, "event_count_total": 250,
                "events": [{"event_type": "runtime_tick"} for _ in range(250)],
                "log_file": None,
            }

        async def async_load(self):
            return self.payload

    store = FakeStore()
    hass = SimpleNamespace(data={})
    def empty():
        return SimpleNamespace(
            active=False, events=[], total_events=0,
            file_path=None, file_error=None,
        )

    async def save(fake_hass):
        log = fake_hass.data["brewassistant"]["brewday_audit_log"]
        store.payload = {"active": log.active, "events": list(log.events),
                         "log_file": log.file_path, "event_count_total": log.total_events,
                         "archive_generation": 1}

    ns = {"_store": lambda _: store,
          "ARCHIVE_GENERATION": 1,
          "_from_store": lambda payload: SimpleNamespace(
              active=payload["active"], events=list(payload["events"]),
              file_path=payload["log_file"], total_events=payload["event_count_total"]
          ),
          "BrewdayAuditLog": empty,
          "_LOGGER": SimpleNamespace(info=lambda *a: None),
          "async_save_brewday_audit_log": save,
          "DATA_KEY": "brewday_audit_log"}
    exec(compile(ast.fix_missing_locations(code), str(SRC), "exec"), ns)
    loaded = asyncio.run(ns["async_load_brewday_audit_log"](hass))
    assert loaded.active is False
    assert loaded.events == [] and loaded.total_events == 0
    assert store.payload["events"] == [] and store.payload["log_file"] is None

    # An early developer JSONL session is also test history until generation 1.
    store.payload = {"active": True, "events": [{"event_type": "audit_started"}],
                     "log_file": "brewassistant/logs/brewday-20261011T123000-000000Z.jsonl",
                     "event_count_total": 85}
    reset = asyncio.run(ns["async_load_brewday_audit_log"](hass))
    assert reset.active is False and reset.total_events == 0
    assert store.payload["archive_generation"] == 1

    # New generation file state survives successive HA loads.
    store.payload = {"active": True, "events": [{"event_type": "audit_started"}],
                     "log_file": "brewassistant/logs/brewday-20261011T123000-000000Z.jsonl",
                     "event_count_total": 85, "archive_generation": 1}
    resumed = asyncio.run(ns["async_load_brewday_audit_log"](hass))
    assert resumed.active is True
    assert resumed.total_events == 85
    assert resumed.file_path.endswith(".jsonl")
    assert len(resumed.events) == 1


def test_no_legacy_import_code_or_unsafe_archive_deletion():
    src = SRC.read_text(encoding="utf-8")
    fs = FILE.read_text(encoding="utf-8")
    assert "async_migrate_legacy" not in src + fs
    assert "_migrate_legacy_window" not in fs
    assert "unlink(" not in src + fs
    assert "path.open(\"a\", encoding=\"utf-8\")" in fs


def test_hlt_audit_producer_routes_enriched_rows_through_archive_lock():
    hlt = (ROOT / "custom_components/brewassistant/hlt/flight_recorder.py").read_text(
        encoding="utf-8"
    )
    audit_source = SRC.read_text(encoding="utf-8")
    assert "await audit.async_record_brewday_audit_prebuilt_event(hass, event)" in hlt
    assert "audit._append_event(log, event)" not in hlt
    tree = ast.parse(audit_source)
    func = next(
        node for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef)
        and node.name == "async_record_brewday_audit_prebuilt_event"
    )
    fragment = ast.get_source_segment(audit_source, func)
    assert "async with _write_lock(hass)" in fragment
    assert "_append_event(log, event)" in fragment
    assert "await _archive_record(hass, log, event)" in fragment
    assert "await async_save_brewday_audit_log(hass)" in fragment


def test_sensor_never_exposes_event_lists_and_keeps_existing_service_names():
    src = SRC.read_text(encoding="utf-8")
    sensor = SENSOR.read_text(encoding="utf-8")
    assert '"events": list(log.events' not in src
    assert '"recent_events": list(log.events' not in src
    assert 'archive_path' in src and 'archive_status' in src
    assert 'log.total_events' in src
    assert 'STORE_TAIL_EVENTS = 12' in src
    assert 'key not in {"note", "signature", "control_reason"}' in src
    assert 'await archive.async_append_event(hass, log.file_path, event)' in src
    assert '"archive_generation": ARCHIVE_GENERATION' in src
    for service in ("async_start_brewday_audit_log", "async_stop_brewday_audit_log",
                    "async_clear_brewday_audit_log", "async_record_brewday_audit_snapshot"):
        assert f"def {service}" in src
    assert '"include_events": True' in sensor  # old attribute contract tolerated
    assert 'build_brewday_audit_snapshot' in sensor


def test_async_event_serialization_and_off_loop_file_io_guards():
    src = SRC.read_text(encoding="utf-8")
    fs = FILE.read_text(encoding="utf-8")
    tree = ast.parse(src)
    ast.parse(fs)
    assert "async with _write_lock(hass):" in src
    assert "hass.async_add_executor_job(_append_jsonl" in fs
    assert "path.open(\"a\", encoding=\"utf-8\")" in fs
    assert 'def async_clear_brewday_audit_log' in src
    assert "unlink(" not in src and "unlink(" not in fs


def test_failed_archive_append_marks_sticky_incomplete_without_control_writes():
    tree = ast.parse(SRC.read_text(encoding="utf-8"))
    node = next(n for n in tree.body
                if isinstance(n, ast.AsyncFunctionDef) and n.name == "_archive_record")
    code = ast.Module(body=[
        ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
        node,
    ], type_ignores=[])
    ns = {"_LOGGER": SimpleNamespace(error=lambda *a, **kw: None)}
    filename = "brewassistant/logs/brewday-20261011T120000-000000Z.jsonl"
    log = SimpleNamespace(file_path=filename, file_error=None, archive_write_failures=0)
    async def broken(hass, path, event):
        raise OSError("disk full")
    ns["archive"] = SimpleNamespace(async_append_event=broken)
    exec(compile(ast.fix_missing_locations(code), str(SRC), "exec"), ns)
    asyncio.run(ns["_archive_record"](SimpleNamespace(), log, {"event_type": "brewday_abort"}))
    assert log.archive_write_failures == 1
    assert "disk full" in log.file_error

    async def recovered(hass, path, event):
        return None
    ns["archive"].async_append_event = recovered
    asyncio.run(ns["_archive_record"](SimpleNamespace(), log, {"event_type": "runtime_tick"}))
    assert log.file_error is None
    assert log.archive_write_failures == 1  # Historical gap must not turn green.

    source = SRC.read_text(encoding="utf-8")
    assert '"archive_status": "error" if log.file_error else "incomplete" if log.archive_write_failures' in source
    assert '"archive_write_failures": log.archive_write_failures' in source
