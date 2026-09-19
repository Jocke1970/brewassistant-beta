"""Exercise production RAPT/BT read-isolation functions with forbidden BT reads.

No Home Assistant installation or physical controller is involved. The fake
state registry raises immediately on any BrewTracker state access.
"""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

PATH = (Path(__file__).resolve().parents[1] /
        "custom_components/brewassistant/brewzilla/brewzilla_rapt_brewing_read_isolation.py")
SOURCE = PATH.read_text(encoding="utf-8")


def _functions(*names):
    tree = ast.parse(SOURCE)
    selected = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names]
    assert set(names) == {node.name for node in selected}
    env = {}
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(PATH), "exec"), env)
    return env


FN = _functions("_bt_entity", "rapt_owns_brewing", "_read_wrapper",
                "_learning_tracker_data", "_audit_bt_status", "_audit_bt_available",
                "_audit_state_available", "_audit_entity_state", "_audit_state_subscription",
                "_batch_guard_bt_active")


class ForbiddenStates:
    def __init__(self):
        self.calls = []

    def get(self, entity):
        if FN["_bt_entity"](entity):
            raise AssertionError(f"BrewTracker read under RAPT: {entity}")
        self.calls.append(entity)
        if entity == "binary_sensor.brewzilla_profile_active":
            return SimpleNamespace(state="on")
        return SimpleNamespace(state="fermenting")


class FakeHass:
    def __init__(self, *, active=True, lost=False, stopped=False, abort=False):
        self.states = ForbiddenStates()
        self.data = {}
        self.active = active
        self.lost = lost
        self.stopped = stopped
        self.abort = abort


def _configure():
    env = FN["rapt_owns_brewing"].__globals__
    env["_BT_PREFIXES"] = ("sensor.brewfather_brew_tracker_", "sensor.brewfather_brewtracker_")
    env["rapt"] = SimpleNamespace(
        RAPT_PROFILE_SOURCE="RAPT BrewZilla Profile",
        _profile_state=lambda hass: hass.states.get("binary_sensor.brewzilla_profile_active") if hass.active else None,
        _store=lambda hass: {"was_active": hass.lost, "stop_guard_active": hass.stopped},
        _active_contract=lambda state: state is not None and state.state == "on",
    )
    env["brewday_operator_abort_snapshot"] = lambda hass: {
        "active": hass.abort, "source": "RAPT BrewZilla Profile" if hass.abort else "None"}
    env["_ORIGINALS"] = {}
    env["_bt_entity"] = FN["_bt_entity"]
    env["rapt_owns_brewing"] = FN["rapt_owns_brewing"]
    return env


def test_active_lost_stopped_and_rapt_abort_keep_bt_unread():
    _configure()
    assert FN["_bt_entity"](("sensor.brewfather_brew_tracker_status", "sensor.brewfather_brewtracker_status"))
    assert not FN["_bt_entity"]("sensor.brewfather_fermentation_target")
    for flags in ({"active": True}, {"active": False, "lost": True},
                  {"active": False, "stopped": True}, {"active": False, "abort": True}):
        assert FN["rapt_owns_brewing"](FakeHass(**flags))
    assert not FN["rapt_owns_brewing"](FakeHass(active=False))


def test_core_brewtracker_accessors_do_not_access_registry_under_rapt():
    env = _configure()
    def get(hass, ref, *args, **kwargs):
        entity = ref[0] if isinstance(ref, tuple) else ref
        return hass.states.get(entity).state
    env["core"] = SimpleNamespace(
        state=get, state_obj=get, attr=get, resolved_entity_id=get,
        entity_candidates=lambda ref: ref if isinstance(ref, tuple) else (ref,))
    aliases = ("sensor.brewfather_brew_tracker_status", "sensor.brewfather_brewtracker_status")
    for name in ("state", "state_obj", "attr", "resolved_entity_id"):
        guarded = FN["_read_wrapper"](name, None)
        rapt_hass = FakeHass()
        result = guarded(rapt_hass, aliases, "inactive") if name == "state" else guarded(rapt_hass, aliases)
        if name == "state":
            assert result == "inactive"
        elif name == "resolved_entity_id":
            assert result == aliases[0]
        else:
            assert result is None
        assert rapt_hass.states.calls == ["binary_sensor.brewzilla_profile_active"]
    assert FN["_read_wrapper"]("state", None)(FakeHass(active=False), aliases) == "fermenting"


def test_learning_and_audit_readers_do_not_consume_bt_under_rapt():
    env = _configure()
    def forbidden(hass, *args):
        raise AssertionError("Legacy BT reader executed")
    env["_ORIGINALS"].update({
        "learning._brewfather_tracker_data": forbidden,
        "audit._brewfather_status": forbidden,
        "audit._brewfather_backend_available": forbidden,
        "audit._state_available": forbidden,
        "audit._entity_state": forbidden,
        "batch_guard._brewfather_tracker_is_active": forbidden,
    })
    hass = FakeHass()
    assert FN["_learning_tracker_data"](hass) == (None, None)
    assert FN["_audit_bt_status"](hass) is None
    assert FN["_audit_bt_available"](hass) is False
    assert FN["_audit_state_available"](hass, "sensor.brewfather_brew_tracker_status") is False
    assert FN["_audit_entity_state"](hass, "sensor.brewfather_brew_tracker_status") is None
    assert FN["_batch_guard_bt_active"](hass) is False


def test_bt_audit_events_are_filtered_before_callback_reads_state():
    env = _configure()
    installed = []
    def subscribe(hass, entities, callback):
        installed.append(callback)
        return lambda: None
    env["_ORIGINALS"]["audit.async_track_state_change_event"] = subscribe
    received = []
    hass = FakeHass()
    FN["_audit_state_subscription"](hass, ("sensor.brewfather_brew_tracker_status",), received.append)
    bt = SimpleNamespace(data={"entity_id": "sensor.brewfather_brew_tracker_status", "new_state": object()})
    rapt = SimpleNamespace(data={"entity_id": "binary_sensor.brewzilla_profile_active"})
    installed[0](bt)
    assert received == []
    installed[0](rapt)
    assert received == [rapt]
    hass.active = False
    installed[0](bt)
    assert received == [rapt, bt]


def test_isolation_installed_after_existing_write_guards():
    identity = (PATH.parent / "brewzilla_rapt_identity_guard.py").read_text(encoding="utf-8")
    assert "brewzilla_rapt_brewing_read_isolation.install_rapt_brewing_read_isolation()" in identity
    assert "brewzilla_sparge_execution_guard.install_sparge_execution_guard()" in identity
    assert identity.index("brewzilla_sparge_execution_guard.install_sparge_execution_guard()") < identity.index(
        "brewzilla_rapt_brewing_read_isolation.install_rapt_brewing_read_isolation()")
