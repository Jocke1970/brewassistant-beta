"""Exercise real RAPT identity predicate without Home Assistant or a brewer."""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_rapt_identity_guard.py"
INIT = ROOT / "custom_components/brewassistant/brewzilla/__init__.py"
SOURCE = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_source_authority_runtime.py"


def _functions(*names):
    tree = ast.parse(GUARD.read_text(encoding="utf-8"))
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    assert {node.name for node in nodes} == set(names)
    scope = {}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(GUARD), "exec"), scope)
    return scope


FUNCS = _functions("_identity_error", "_safe_off_allowed")


def _observation(attrs=None, runtime=None):
    profile_attrs = {"profile_session_id": "batch-9", "step_id": "sparge-5",
                     "step_number": 5, "step_name": "Sparge"}
    profile_attrs.update(attrs or {})
    process = {"source": "RAPT BrewZilla Profile", "profile_session_id": "batch-9",
               "profile_step_id": "sparge-5", "profile_step_number": 5,
               "raw_step_name": "Sparge"}
    process.update(runtime or {})
    return FUNCS["_identity_error"](process, SimpleNamespace(attributes=profile_attrs))


def test_exact_active_rapt_step_identity_is_accepted():
    assert _observation() is None
    assert _observation(attrs={"step_id": None}, runtime={"profile_step_id": None}) is None
    assert _observation(attrs={"step_number": None}, runtime={"profile_step_number": None}) is None


def test_missing_step_identity_cannot_fall_back_to_generic_heating():
    assert _observation(attrs={"step_id": None, "step_number": None},
                        runtime={"profile_step_id": None, "profile_step_number": None}) == "rapt_step_identity_missing"
    assert _observation(attrs={"step_id": "sparge-5"}, runtime={"profile_step_id": None}) == "rapt_step_id_missing_or_mismatched"
    assert _observation(attrs={"step_number": None}) == "rapt_step_number_missing_or_mismatched"
    assert _observation(attrs={"step_number": 0}, runtime={"profile_step_number": 0}) == "rapt_step_number_missing_or_mismatched"


def test_step_and_session_cannot_be_reused_after_transition():
    assert _observation(attrs={"profile_session_id": "batch-10"}) == "rapt_session_identity_mismatch"
    assert _observation(runtime={"profile_session_id": None}) == "rapt_session_identity_mismatch"
    assert _observation(attrs={"step_id": "boil-6"}) == "rapt_step_id_missing_or_mismatched"
    assert _observation(attrs={"step_number": 6}) == "rapt_step_number_missing_or_mismatched"
    assert _observation(attrs={"step_name": "Boil"}) == "rapt_step_name_missing_or_mismatched"
    assert _observation(attrs={"step_name": None}) == "rapt_step_name_missing_or_mismatched"


def test_missing_contract_and_brewfather_not_reinterpreted_as_rapt():
    assert FUNCS["_identity_error"]({"source": "RAPT BrewZilla Profile"}, None) == "rapt_profile_step_unavailable"
    assert FUNCS["_identity_error"]({"source": "Brewfather Brew Tracker"}, None) is None


def test_stale_rapt_abort_does_not_write_into_brewfather_observer():
    scope = FUNCS["_safe_off_allowed"].__globals__
    scope["_PREVIOUS_SAFE_OFF"] = lambda decision, context: True
    assert not FUNCS["_safe_off_allowed"](None, {"runtime": {"source": "Brewfather Brew Tracker"}})
    assert FUNCS["_safe_off_allowed"](None, {"runtime": {"source": "RAPT BrewZilla Profile"}})


def test_guard_installed_last_and_uses_actual_source_gate():
    init = INIT.read_text(encoding="utf-8")
    guard = GUARD.read_text(encoding="utf-8")
    source = SOURCE.read_text(encoding="utf-8")
    assert init.index("_source_authority_runtime.install_source_authority_runtime()") < init.index(
        "_rapt_identity_guard.install_rapt_identity_guard()")
    assert "authority_runtime._live_authority = _live_authority" in guard
    assert "authority_runtime._safe_off_allowed = _safe_off_allowed" in guard
    assert "authority, context = _live_authority(hass)" in source
    assert "return _sparge_write_allowed(hass" in source
