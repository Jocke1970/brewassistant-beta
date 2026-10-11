"""Regression tests for 0b11 append-only Flight Recorder files (no HA hardware)."""
from __future__ import annotations

import ast
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
    wanted = {"new_session_file", "_absolute_path", "_append_jsonl", "_migrate_legacy_window"}
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


def test_legacy_import_once_never_truncates_or_duplicates(tmp_path):
    ns = archive()
    p = tmp_path / "audit.jsonl"
    old = [{"event_type": "brewzilla_action", "actions": ["set_heat_utilization:40"]},
           {"event_type": "brewday_abort", "source": "RAPT BrewZilla Profile"}]
    assert ns["_migrate_legacy_window"](p, old) is True
    original = p.read_bytes()
    assert ns["_migrate_legacy_window"](p, old) is False
    assert p.read_bytes() == original
    events = [json.loads(line) for line in original.splitlines()]
    assert events[0]["legacy_window_only"] is True
    assert events[0]["legacy_events_retained"] == 2
    assert events[1:] == old


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
    assert 'await archive.async_migrate_legacy(hass, new_path, log.events)' in src
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
    assert "path.open(\"x\", encoding=\"utf-8\")" in fs
    assert 'def async_clear_brewday_audit_log' in src
    assert "unlink(" not in src and "unlink(" not in fs
