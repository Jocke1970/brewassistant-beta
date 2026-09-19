"""HA-published trace diagnostics must never imply permission or fake missing data."""
from __future__ import annotations

import ast
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace


SOURCE = Path(__file__).resolve().parents[1] / "custom_components/brewassistant/hlt/trace.py"


def diagnostics():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name in {"_number", "_ha_diagnostics"}]
    namespace = {"Any": object, "datetime": datetime, "isfinite": __import__("math").isfinite}
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(SOURCE), "exec"), namespace)
    return namespace["_ha_diagnostics"]


def test_ha_diagnostics_preserve_published_values_and_ages():
    now = datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc)
    sample = now.timestamp()
    states = {
        "sensor.brewzilla_temperature": SimpleNamespace(state="65.5", last_updated=now - timedelta(seconds=3)),
        "number.brewzilla_target_temperature": SimpleNamespace(state="71.8", last_updated=now - timedelta(hours=1)),
        "sensor.brewassistant_brewday_target_temperature": SimpleNamespace(state="66", last_updated=now - timedelta(seconds=30)),
        "sensor.brewassistant_hlt_virtual_energy_recipient": SimpleNamespace(state="none", last_updated=now - timedelta(seconds=10)),
    }
    hass = SimpleNamespace(states=SimpleNamespace(get=states.get))
    fields = diagnostics()(hass, sample)
    assert fields["bz_temperature_ha_c"] == 65.5
    assert fields["bz_temperature_ha_age_s"] == 3
    assert fields["bz_device_target_ha_c"] == 71.8
    assert fields["bz_device_target_ha_age_s"] == 3600  # held setting, not discarded
    assert fields["bz_brewday_target_ha_c"] == 66
    assert fields["bz_brewday_target_ha_age_s"] == 30
    assert fields["hlt_virtual_recipient_ha_state"] == "none"
    assert fields["hlt_virtual_recipient_ha_age_s"] == 10


def test_missing_and_unavailable_are_not_interpreted_as_zero():
    now = datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc)
    hass = SimpleNamespace(states=SimpleNamespace(get=lambda name: SimpleNamespace(
        state="unavailable", last_updated=now) if name == "sensor.brewzilla_temperature" else None))
    fields = diagnostics()(hass, now.timestamp())
    assert fields["bz_temperature_ha_c"] is None
    assert fields["bz_temperature_ha_age_s"] == 0
    assert fields["bz_device_target_ha_c"] is None
    assert fields["bz_brewday_target_ha_c"] is None
    assert fields["hlt_virtual_recipient_ha_state"] is None
    assert diagnostics()(SimpleNamespace(), now.timestamp())["hlt_virtual_recipient_ha_state"] is None
