"""Execute the real Sparge plan ID wrapper without HA or hardware."""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_sparge_plan_identity.py"
INIT = ROOT / "custom_components/brewassistant/brewzilla/__init__.py"


def _plan_id():
    source = ast.parse(MODULE.read_text(encoding="utf-8"))
    function = next(node for node in source.body if isinstance(node, ast.FunctionDef) and node.name == "_plan_id")
    scope = {"hashlib": hashlib, "_PREVIOUS_PLAN_ID": lambda snapshot, actions: "baseline-plan"}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(MODULE), "exec"), scope)
    return scope["_plan_id"]


def test_ordinary_runtime_plans_preserve_existing_ids():
    assert _plan_id()({"rapt_sparge_active": False}, []) == "baseline-plan"


def test_sparge_confirmation_scoped_to_session_and_step():
    plan = _plan_id()
    first = {"rapt_sparge_active": True, "rapt_sparge_session_id": "session-a",
             "rapt_sparge_step_id": "step-5", "rapt_sparge_step_number": 5}
    old = plan(first, [])
    assert old.startswith("baseline-plan:rapt-")
    assert plan(dict(first), []) == old
    assert plan({**first, "rapt_sparge_session_id": "session-b"}, []) != old
    assert plan({**first, "rapt_sparge_step_id": "step-6"}, []) != old
    assert plan({**first, "rapt_sparge_step_number": 6}, []) != old
    assert plan({**first, "rapt_sparge_session_id": None}, []) != old
    assert plan({**first, "rapt_sparge_step_id": None,
                 "rapt_sparge_step_number": None}, []) != old


def test_session_plan_guard_installed_before_final_source_guard():
    source = INIT.read_text(encoding="utf-8")
    assert source.index("_rapt_sparge_controller.install_rapt_sparge_controller()") < source.index(
        "_sparge_plan_identity.install_sparge_plan_identity()") < source.index(
        "_source_authority_runtime.install_source_authority_runtime()")
