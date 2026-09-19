"""Test source isolation with simulated HA states, not real equipment.

BT is allowed for informational views, never as a fallback when an RAPT
profile is ON, even if its BA contract is partially published or restored.
"""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_rapt_brewing_read_isolation.py"
SOURCE = PATH.read_text(encoding="utf-8")


def _functions(*names):
    tree = ast.parse(SOURCE)
    selected = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names]
    assert set(names) == {node.name for node in selected}
    env = {}
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(PATH), "exec"), env)
    return env


FN = _functions("_bt_entity", "_unverified_rapt_profile_on", "rapt_owns_brewing",
                "_rapt_runtime_snapshot", "_runtime_core_source", "_runtime_core_snapshot",
                "_learning_tracker_data", "_audit_session_active", "_audit_bt_status",
                "_audit_bt_available", "_audit_state_available", "_audit_entity_state",
                "_audit_state_subscription", "_batch_guard_bt_active")


class FakeStates:
    def __init__(self, hass):
        self.hass = hass
        self.calls = []

    def get(self, entity):
        self.calls.append(entity)
        if entity == "binary_sensor.brewzilla_profile_active":
            if not self.hass.active:
                return None
            return SimpleNamespace(
                state="on", entity_id=entity,
                attributes={
                    "ba_source": None if self.hass.unverified else "rapt_cloud_link_brewzilla_profile_runtime",
                    "profile_contract_complete": not self.hass.incomplete,
                    "restored": self.hass.restored,
                },
            )
        if FN["_bt_entity"](entity):
            return SimpleNamespace(state=self.hass.bt_status)
        if entity == "sensor.brewfather_fermentation_target":
            return SimpleNamespace(state="18.0")
        return None


class FakeHass:
    def __init__(self, *, active=True, lost=False, stopped=False, abort=False,
                 bt_status="brewing", unverified=False, incomplete=False, restored=False):
        self.active = active
        self.lost = lost
        self.stopped = stopped
        self.abort = abort
        self.bt_status = bt_status
        self.unverified = unverified
        self.incomplete = incomplete
        self.restored = restored
        self.states = FakeStates(self)
        self.data = {}


def _configure():
    env = FN["rapt_owns_brewing"].__globals__
    env["_BT_PREFIXES"] = ("sensor.brewfather_brew_tracker_", "sensor.brewfather_brewtracker_")
    env["rapt"] = SimpleNamespace(
        RAPT_PROFILE_SOURCE="RAPT BrewZilla Profile",
        RAPT_PROFILE_ENTITY="binary_sensor.brewzilla_profile_active",
        RAPT_PROFILE_BA_SOURCE="rapt_cloud_link_brewzilla_profile_runtime",
        _profile_state=lambda hass: hass.states.get("binary_sensor.brewzilla_profile_active"),
        _store=lambda hass: {"was_active": hass.lost, "stop_guard_active": hass.stopped},
        _active_contract=lambda state: bool(
            state is not None and state.state == "on"
            and state.attributes.get("ba_source") == "rapt_cloud_link_brewzilla_profile_runtime"
            and not state.attributes.get("restored")
        ),
    )
    env["brewday_operator_abort_snapshot"] = lambda hass: {
        "active": hass.abort, "source": "RAPT BrewZilla Profile" if hass.abort else "None"}
    env["_ORIGINALS"] = {}
    env["_bt_entity"] = FN["_bt_entity"]
    env["_unverified_rapt_profile_on"] = FN["_unverified_rapt_profile_on"]
    env["rapt_owns_brewing"] = FN["rapt_owns_brewing"]
    env["core"] = SimpleNamespace(inactive_snapshot=lambda: {
        "source": "None", "status": "inactive", "runtime_state": "idle", "target_temperature": None})
    env["_ORIGINALS"].update({
        "rapt.build_rapt_profile_runtime_snapshot": lambda hass: (
            {"source": "RAPT BrewZilla Profile", "target_temperature": 40.0}
            if hass.active and not hass.unverified and not hass.restored else None
        ),
        "core.source": lambda hass: "Brewfather Brew Tracker" if hass.states.get("sensor.brewfather_brew_tracker_status") else "None",
        "core.build_core_snapshot": lambda hass: {"source": "Brewfather Brew Tracker", "step": hass.states.get("sensor.brewfather_brew_tracker_status").state},
        "learning._brewfather_tracker_data": lambda hass: ({"step": hass.states.get("sensor.brewfather_brew_tracker_status").state}, {}),
        "audit.brewfather_session_active": lambda hass: bool(hass.states.get("sensor.brewfather_brew_tracker_status")),
        "audit._brewfather_status": lambda hass: hass.states.get("sensor.brewfather_brew_tracker_status").state,
        "audit._brewfather_backend_available": lambda hass: bool(hass.states.get("sensor.brewfather_brew_tracker_status")),
        "audit._state_available": lambda hass, entity: bool(hass.states.get(entity)),
        "audit._entity_state": lambda hass, entity: hass.states.get(entity),
        "batch_guard._brewfather_tracker_is_active": lambda hass: bool(hass.states.get("sensor.brewfather_brew_tracker_status")),
    })
    return env


def test_bt_is_brewing_data_bf_fermentation_is_not_bt():
    _configure()
    assert FN["_bt_entity"](("sensor.brewfather_brew_tracker_status", "sensor.brewfather_brewtracker_status"))
    assert not FN["_bt_entity"]("sensor.brewfather_fermentation_target")
    assert not FN["_bt_entity"]("sensor.brewfather_recipe_name")


def test_rapt_source_latch_includes_loss_stop_abort_and_unverified_on_without_bt():
    _configure()
    for flags in ({"active": True}, {"active": True, "unverified": True},
                  {"active": True, "restored": True}, {"active": False, "lost": True},
                  {"active": False, "stopped": True}, {"active": False, "abort": True}):
        hass = FakeHass(**flags)
        assert FN["rapt_owns_brewing"](hass)
        assert not any(FN["_bt_entity"](entity) for entity in hass.states.calls)
    assert not FN["rapt_owns_brewing"](FakeHass(active=False))


def test_initial_unverified_on_profile_holds_rapt_without_bt_fallback():
    _configure()
    for flags in ({"unverified": True}, {"restored": True}):
        hass = FakeHass(**flags)
        assert FN["_unverified_rapt_profile_on"](hass.states.get("binary_sensor.brewzilla_profile_active"))
        for bt_status in ("planning", "brewing", "paused", "unknown"):
            hass.bt_status = bt_status
            snap = FN["_rapt_runtime_snapshot"](hass)
            assert snap["source"] == "RAPT BrewZilla Profile"
            assert snap["runtime_state"] == "source_unverified"
            assert snap["target_temperature"] is None
            assert snap["direct_brewzilla_control_allowed"] is False
            assert snap["profile_contract_complete"] is False
            assert FN["_runtime_core_source"](hass) == "None"
            assert FN["_learning_tracker_data"](hass) == (None, None)
            assert FN["_audit_session_active"](hass) is False
        assert not any(FN["_bt_entity"](entity) for entity in hass.states.calls)
    # A verified profile must pass through the original adapter unchanged.
    assert FN["_rapt_runtime_snapshot"](FakeHass()) == {
        "source": "RAPT BrewZilla Profile", "target_temperature": 40.0}
    # A genuinely absent profile leaves explicitly selected BT available.
    assert FN["_rapt_runtime_snapshot"](FakeHass(active=False)) is None
    # An ON profile with a complete BA source marker but incomplete step still
    # belongs to RAPT; source authority independently rejects positive writes.
    incomplete = FakeHass(incomplete=True)
    assert FN["rapt_owns_brewing"](incomplete)
    assert FN["_runtime_core_source"](incomplete) == "None"
    assert not FN["_unverified_rapt_profile_on"](SimpleNamespace(
        state="on", entity_id="binary_sensor.other", attributes={}))


def test_bt_updates_cannot_change_rapt_process_source_snapshot_or_learning():
    _configure()
    for flags in ({"active": True}, {"active": True, "unverified": True},
                  {"active": False, "lost": True}, {"active": False, "stopped": True},
                  {"active": False, "abort": True}):
        hass = FakeHass(**flags)
        for bt_status in ("planning", "brewing", "paused", "fermenting", "unknown"):
            hass.bt_status = bt_status
            assert FN["_runtime_core_source"](hass) == "None"
            assert FN["_runtime_core_snapshot"](hass) == {
                "source": "None", "status": "inactive", "runtime_state": "idle", "target_temperature": None}
            assert FN["_learning_tracker_data"](hass) == (None, None)
        assert not any(FN["_bt_entity"](entity) for entity in hass.states.calls)


def test_bt_specific_information_and_bf_fermentation_remain_readable():
    env = _configure()
    hass = FakeHass(active=True, unverified=True)
    env["core"].state = lambda hass, entity: hass.states.get(entity).state
    assert env["core"].state(hass, "sensor.brewfather_brew_tracker_status") == "brewing"
    hass.bt_status = "paused"
    assert env["core"].state(hass, "sensor.brewfather_brew_tracker_status") == "paused"
    assert hass.states.get("sensor.brewfather_fermentation_target").state == "18.0"
    assert FN["_runtime_core_source"](hass) == "None"
    assert FN["_runtime_core_snapshot"](hass)["target_temperature"] is None
    other = FakeHass(active=False)
    assert FN["_runtime_core_source"](other) == "Brewfather Brew Tracker"
    assert FN["_runtime_core_snapshot"](other)["step"] == "brewing"
    assert FN["_learning_tracker_data"](other)[0]["step"] == "brewing"


def test_audit_bt_events_cannot_start_or_rotate_rapt_session():
    env = _configure()
    subscribed = []
    env["_ORIGINALS"]["audit.async_track_state_change_event"] = lambda hass, entities, callback: (subscribed.append(callback) or (lambda: None))
    received = []
    hass = FakeHass()
    assert FN["_audit_session_active"](hass) is False
    assert FN["_audit_bt_status"](hass) is None
    assert FN["_audit_bt_available"](hass) is False
    assert FN["_audit_state_available"](hass, "sensor.brewfather_brew_tracker_status") is False
    assert FN["_audit_entity_state"](hass, "sensor.brewfather_brew_tracker_status") is None
    assert FN["_batch_guard_bt_active"](hass) is False
    assert FN["_audit_state_available"](hass, "sensor.brewfather_fermentation_target") is True
    FN["_audit_state_subscription"](hass, ("sensor.brewfather_brew_tracker_status",), received.append)
    bt_event = SimpleNamespace(data={"entity_id": "sensor.brewfather_brew_tracker_status"})
    rapt_event = SimpleNamespace(data={"entity_id": "binary_sensor.brewzilla_profile_active"})
    subscribed[0](bt_event)
    assert received == []
    subscribed[0](rapt_event)
    assert received == [rapt_event]
    hass.active = False
    subscribed[0](bt_event)
    assert received == [rapt_event, bt_event]
    assert FN["_audit_session_active"](hass) is True
    assert FN["_audit_bt_status"](hass) == "brewing"
    assert FN["_batch_guard_bt_active"](hass) is True


def test_installer_gates_process_consumers_not_global_bt_or_fermentation():
    identity = (PATH.parent / "brewzilla_rapt_identity_guard.py").read_text(encoding="utf-8")
    assert "brewzilla_rapt_brewing_read_isolation.install_rapt_brewing_read_isolation()" in identity
    assert "brewzilla_sparge_execution_guard.install_sparge_execution_guard()" in identity
    assert identity.index("brewzilla_sparge_execution_guard.install_sparge_execution_guard()") < identity.index(
        "brewzilla_rapt_brewing_read_isolation.install_rapt_brewing_read_isolation()")
    assert "rapt.build_rapt_profile_runtime_snapshot = _rapt_runtime_snapshot" in SOURCE
    assert "core.source = _runtime_core_source" in SOURCE
    assert "core.build_core_snapshot = _runtime_core_snapshot" in SOURCE
    assert "audit.brewfather_session_active = _audit_session_active" in SOURCE
    assert "learning._brewfather_tracker_data = _learning_tracker_data" in SOURCE
    assert "batch_guard._brewfather_tracker_is_active = _batch_guard_bt_active" in SOURCE
    assert "setattr(core, name" not in SOURCE
    assert "ownership.brewfather_batch_phase =" not in SOURCE
    assert "fermentation" not in SOURCE.split("def install_rapt_brewing_read_isolation", 1)[1]


def test_normalized_brewday_checks_rapt_before_legacy_core_and_abort_is_gated():
    runtime = (ROOT / "custom_components/brewassistant/brewday/brewday_runtime.py").read_text(encoding="utf-8")
    ramp = (ROOT / "custom_components/brewassistant/brewday/brewday_ramp_target_gate.py").read_text(encoding="utf-8")
    sensor = (ROOT / "custom_components/brewassistant/brewday/brewday_runtime_sensor.py").read_text(encoding="utf-8")
    assert runtime.index("rapt_snapshot = build_rapt_profile_runtime_snapshot(hass)") < runtime.index("runtime_source = core_source(hass)")
    assert "snapshot = build_core_snapshot(hass)" in runtime
    assert "snapshot = core.build_core_snapshot(hass)" in ramp
    assert "from .brewfather_ownership import brewfather_batch_phase" in sensor
    assert "return brewfather_batch_phase(self.coordinator.hass)" in sensor
