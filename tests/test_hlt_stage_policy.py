"""Isolated policy checks without importing Home Assistant during collection."""
from __future__ import annotations

import ast
from datetime import datetime, timezone
from math import isfinite
from pathlib import Path
from typing import Any


SOURCE = Path(__file__).resolve().parents[1] / "custom_components/brewassistant/hlt/runtime.py"
POLICY_CONSTANTS = {"_HLT_ELIGIBLE_STAGES", "_RAMP_STEP_PREFIXES", "_RAMP_STEP_NAMES"}
POLICY_FUNCTIONS = {
    "_numeric", "_observed", "_allowed_stage", "_ramp_step_requested", "_bz_cruise_observation",
}


def policy():
    """Extract the real pure runtime policy rather than reimplementing it."""
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    selected = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id in POLICY_CONSTANTS
            for target in node.targets
        ):
            selected.append(node)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in POLICY_FUNCTIONS:
            selected.append(node)
    namespace = {"Any": Any, "datetime": datetime, "isfinite": isfinite, "frozenset": frozenset}
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(SOURCE), "exec"), namespace)
    return namespace


def test_only_explicit_mash_sparge_stages_are_eligible():
    allowed = policy()["_allowed_stage"]
    assert allowed("Mash")
    assert allowed("Sparge")
    assert allowed("Heat strike")
    for stage in (None, "", "New unexpected stage", "Boil", "Pre-boil", "Mash / Boil", "Chill / Transfer"):
        assert not allowed(stage), stage


def test_field_observed_ramp_wording_vetoes_virtual_cruise():
    helpers = policy()
    ramp_step = helpers["_ramp_step_requested"]
    assert ramp_step("Ramp to 72°C")
    assert ramp_step("Mash out")
    assert not ramp_step("Saccharification")
    # Field trace had an explicit 'Ramp to 72°C' step but matched temperature
    # targets at one sampled instant. That must never grant virtual HLT power.
    cruise, ramp = helpers["_bz_cruise_observation"](
        None, {"step": "Ramp to 72°C", "target_temperature": 72},
        datetime(2026, 9, 19, tzinfo=timezone.utc), 180,
    )
    assert (cruise, ramp) == (False, True)
