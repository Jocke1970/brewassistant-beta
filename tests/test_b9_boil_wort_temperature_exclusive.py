"""b9 BOIL temperature authority tests: wort/internal only, never BLE.

Execute production gate/resolver/learning/ramp/fail-passive function bodies
in isolated HA state stubs. No cloud calls, physical BrewZilla or RCL writes.
"""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
TEMP = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_temperature.py"
ROLES = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_temperature_roles.py"
LEARNING = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_learning.py"
RAMP = ROOT / "custom_components/brewassistant/brewday/brewday_ramp_target_gate.py"
FAIL = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_fail_passive_guard.py"

INTERNAL = "sensor.brewzilla_temperature"
BLE = "sensor.brewzilla_ble_thermometer_temperature"
CTL = "sensor.brewzilla_control_device_temperature"


def extract(path: Path, *names: str) -> dict:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    funcs = [node for node in tree.body if isinstance(node, ast.FunctionDef)
             and node.name in names]
    assert {fn.name for fn in funcs} == set(names)
    module = ast.Module(
        body=[ast.ImportFrom(module="__future__",
                             names=[ast.alias(name="annotations")], level=0), *funcs],
        type_ignores=[],
    )
    namespace = {}
    exec(compile(ast.fix_missing_locations(module), str(path), "exec"), namespace)
    return namespace


class States:
    def __init__(self, values=None, rcl=()):
        self.values = values or {}
        self.rcl = rcl

    def get(self, entity):
        return self.values.get(entity)

    def async_all(self, domain=None):
        assert domain == "binary_sensor"
        return list(self.rcl)


def state(value, **attrs):
    return SimpleNamespace(state=value, attributes=attrs)


def hass(states=None, rcl=()):
    return SimpleNamespace(states=States(states, rcl), data={})


@pytest.mark.parametrize(("name", "expected"), [
    ("Boil", True), ("Boiling", True), ("Kok", True),
    ("Kokning", True), ("Heating To Boil", True),
    ("Pre-Boil", False), ("Pre boil", False), ("Preboil", False),
    ("Mash Out", False), ("Mash Rest", False), ("Sparge", False),
    ("ChillOut", False), ("Hopstand", False),
])
def test_boil_labels_only_current_step(name, expected):
    ns = extract(TEMP, "_is_current_boil_label")
    ns["re"] = __import__("re")
    assert ns["_is_current_boil_label"](name) is expected


def gate():
    ns = extract(TEMP, "_is_current_boil_label", "_boil_stage_active")
    ns.update(
        re=__import__("re"),
        _state_value=lambda ha, entity: (
            ha.states.get(entity).state if ha.states.get(entity) else None),
        BREWDAY_RUNTIME_STATE_SENSOR="sensor.brewassistant_brewday_runtime_state",
        BREWDAY_RUNTIME_STAGE_SENSOR="sensor.brewassistant_brewday_runtime_stage",
        BREWDAY_RUNTIME_STEP_SENSOR="sensor.brewassistant_brewday_runtime_step",
        _ACTIVE_RUNTIME_STATES={"running", "live", "paused"},
    )
    return ns


def test_boil_active_from_brewday_or_current_rapt_step_never_next_step():
    ns = gate()
    values = {
        "sensor.brewassistant_brewday_runtime_state": state("running"),
        "sensor.brewassistant_brewday_runtime_stage": state("Mash"),
        "sensor.brewassistant_brewday_runtime_step": state("Mash Out"),
    }
    h = hass(values)
    assert not ns["_boil_stage_active"](h)
    values["sensor.brewassistant_brewday_runtime_step"] = state("Boil")
    assert ns["_boil_stage_active"](h)
    values["sensor.brewassistant_brewday_runtime_step"] = state("Pre-Boil")
    assert not ns["_boil_stage_active"](h)
    values["sensor.brewassistant_brewday_runtime_state"] = state("source_unavailable")
    values["sensor.brewassistant_brewday_runtime_step"] = state("Boil")
    assert ns["_boil_stage_active"](h)  # source loss is not STOP
    values["sensor.brewassistant_brewday_runtime_state"] = state("running")
    values["sensor.brewassistant_brewday_runtime_step"] = state("Mash Rest")
    rcl_boil = state(
        "on", ba_source="rapt_cloud_link_brewzilla_profile_runtime",
        profile_active=True, step_name="Boil",
    )
    h = hass(values, [rcl_boil])
    assert ns["_boil_stage_active"](h)
    rcl_boil.state = "off"
    assert not ns["_boil_stage_active"](h)
    rcl_boil.state = "on"
    rcl_boil.attributes["profile_active"] = None
    assert not ns["_boil_stage_active"](h)
    rcl_boil.attributes["profile_active"] = True
    rcl_boil.attributes["step_name"] = "Pre-Boil"
    assert not ns["_boil_stage_active"](h)


@pytest.mark.parametrize("selected", [
    "Auto", "RAPT BLE Thermometer", "BrewZilla Control Device",
    "BrewZilla Internal",
])
@pytest.mark.parametrize("wort_value", [98.6, None])
def test_boil_snapshot_excludes_external_even_when_operator_selected(
    selected, wort_value,
):
    ns = extract(TEMP, "_boil_internal_only_snapshot")
    called = []
    store = {
        "latched_auto_entity": BLE,
        "latched_auto_source": "RAPT BLE Thermometer",
        "verified_external_entities": {BLE: {"source": "RAPT BLE Thermometer"}},
    }
    def candidate(ha, entity, label):
        called.append(entity)
        assert entity == INTERNAL, "BLE/control-device must never be read in BOIL"
        return {
            "value": wort_value,
            "available": wort_value is not None,
            "age_seconds": 12 if wort_value is not None else None,
            "freshness_ok": True,
            "source": "BrewZilla Internal",
            "entity_id": entity,
        }
    ns.update(
        _candidate=candidate, _resolver_store=lambda ha: store,
        selected_mash_source=lambda ha: selected,
        BREWZILLA_INTERNAL_TEMP_SENSOR=INTERNAL,
        MASH_SOURCE_SELECT="select.brewassistant_brewzilla_mash_temperature_source",
    )
    out = ns["_boil_internal_only_snapshot"](object())
    assert called == [INTERNAL]
    assert out["boil_internal_only"] is True
    assert out["mash_source_selected"] == selected
    assert out["mash_temperature"] == wort_value
    assert out["wort_temperature"] == wort_value
    assert out["mash_temperature_entity"] == (INTERNAL if wort_value is not None else None)
    assert out["mash_temperature_source"] == (
        "BrewZilla Internal" if wort_value is not None else "Unavailable")
    assert out["external_temperature_available"] is False
    assert out["external_temperature_entity"] is None
    assert out["temperature_delta_mash_wort"] is None
    assert out["candidates"]["ble"]["eligible"] is False
    assert out["candidates"]["control_device"]["eligible"] is False
    assert store["latched_auto_entity"] is None
    assert store["latched_auto_source"] is None


@pytest.mark.parametrize(("path", "function"), [
    (TEMP, "brewzilla_temperature_snapshot"), (ROLES, "_snapshot")
])
def test_both_base_and_installed_role_resolvers_call_exclusive_gate_first(path, function):
    ns = extract(path, function)
    calls = []
    if path == TEMP:
        ns.update(
            selected_mash_source=lambda ha: "RAPT BLE Thermometer",
            _boil_stage_active=lambda ha: True,
            _boil_internal_only_snapshot=lambda ha, selected: calls.append(selected) or {"boil_internal_only": True},
            _candidate=lambda *args: pytest.fail("No external candidate may be read"),
        )
    else:
        ns.update(t=SimpleNamespace(
            selected_mash_source=lambda ha: "Auto",
            _boil_stage_active=lambda ha: True,
            _boil_internal_only_snapshot=lambda ha, selected: calls.append(selected) or {"boil_internal_only": True},
            _candidate=lambda *args: pytest.fail("No external candidate may be read"),
        ))
    out = ns[function](object())
    assert out["boil_internal_only"] is True
    assert calls


def test_equipment_learning_never_falls_back_to_ble_in_boil_or_when_runtime_lags():
    ns = extract(LEARNING, "_temperature_source_snapshot")
    mash_only = {
        "mash_temperature": 31.8, "mash_temperature_source": "RAPT BLE Thermometer",
        "mash_temperature_entity": BLE,
        "wort_temperature": None, "wort_temperature_entity": INTERNAL,
        "wort_temperature_source": "BrewZilla Internal",
        "boil_internal_only": True,
    }
    ns["brewzilla_temperature_snapshot"] = lambda ha: mash_only
    for phase in ("boil", "ramp"):
        result = ns["_temperature_source_snapshot"](object(), phase)
        assert result["learning_temperature"] is None
        assert result["learning_temperature_entity"] == INTERNAL
        assert result["learning_temperature_role"] == "wort_or_kettle_temperature"
    # While in mash, normal external temperature selection still applies.
    mash_only["boil_internal_only"] = False
    assert ns["_temperature_source_snapshot"](object(), "mash_hold")["learning_temperature"] == 31.8


def test_brewfather_ramp_boiling_uses_wort_only_with_no_ble_fallback():
    ns = extract(RAMP, "_runtime_temperature")
    looked_up = []
    ns.update(
        _temperature_module=lambda: SimpleNamespace(
            _boil_stage_active=lambda ha: False,
            BREWZILLA_INTERNAL_TEMP_SENSOR=INTERNAL,
        ),
        TEMP_ENTITY_CANDIDATES=(BLE, CTL, INTERNAL),
        _float_state=lambda ha, entity: looked_up.append(entity) or (
            94.0 if entity == INTERNAL else 65.0
        ),
    )
    # The lazy module helper must not import BrewZilla during package initialization.
    source = RAMP.read_text(encoding="utf-8")
    assert "from ..brewzilla import brewzilla_temperature" in source
    assert "from ..brewzilla import brewzilla_temperature as bz_temperature" not in source
    assert ns["_runtime_temperature"](object(), boil_step=True) == (94.0, INTERNAL)
    assert looked_up == [INTERNAL]
    looked_up.clear()
    assert ns["_runtime_temperature"](object(), boil_step=False) == (65.0, BLE)
    looked_up.clear()
    ns["_float_state"] = lambda ha, ent: looked_up.append(ent) or None
    assert ns["_runtime_temperature"](object(), boil_step=True) == (None, None)
    assert looked_up == [INTERNAL]


def test_fail_passive_no_new_writes_when_boil_internal_missing():
    ns = extract(FAIL, "_resolved_temperature_health")
    ns.update(
        temperature=SimpleNamespace(brewzilla_temperature_snapshot=lambda ha: {
            "boil_internal_only": True,
            "mash_temperature": None,
            "mash_temperature_source": "Unavailable",
            "mash_temperature_entity": None,
            "wort_temperature_age_seconds": None,
        }),
        _age_stale=lambda age: bool(age is not None and age > 90),
    )
    health = ns["_resolved_temperature_health"](object())
    assert health["fail_passive_temperature_reason"] == "boil_internal_wort_temperature_unavailable"
    assert health["fail_passive_process_entity"] is None
