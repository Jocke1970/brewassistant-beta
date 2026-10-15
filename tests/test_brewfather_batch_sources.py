"""Regression checks for Brewfather batch versus BrewTracker ownership.

This repository's lightweight pytest matrix deliberately does not install
Home Assistant. Execute the PRODUCTION pure-function AST under minimal
namespaces, rather than importing the full custom integration at collection
time (which would pull Home Assistant into Python 3.11/3.12/3.13 CI).
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import math

ROOT = Path(__file__).resolve().parents[1]
COOLING = ROOT / "custom_components/brewassistant/cooling/cooling_runtime.py"
TRACKING = ROOT / "custom_components/brewassistant/fermentation_tracking/sensor.py"
SCHEDULE = ROOT / "custom_components/brewassistant/fermentation_tracking/recipe_schedule.py"
BATCH_ENTITY = "sensor.brewfather_all_batches_data"


def _production_functions(path: Path, *names: str, namespace: dict):
    """Extract actual production functions without any HA integration import."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    picked = [node for node in tree.body
              if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
              and node.name in names]
    assert {node.name for node in picked} == set(names)
    module = ast.Module(body=[
        ast.ImportFrom(module="__future__",
                       names=[ast.alias(name="annotations")], level=0),
        *picked,
    ], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), str(path), "exec"), namespace)
    return namespace


def _functions():
    base = dict(datetime=datetime, timedelta=timedelta, timezone=timezone,
                Mapping=Mapping, math=math)
    schedule_ns = _production_functions(
        SCHEDULE, "_epoch_ms_to_utc", "_number", "build_recipe_temperature_schedule",
        namespace=base.copy(),
    )
    cooling_ns = _production_functions(
        COOLING, "_brewfather_pitch_target",
        namespace={**base, "BF_BATCHES_ENTITY": BATCH_ENTITY},
    )
    tracking_ns = _production_functions(
        TRACKING, "_timestamp_from_value", "_brewfather_recipe_schedule",
        namespace={**base,
                   "BREWFATHER_BATCHES_ENTITY": BATCH_ENTITY,
                   "INVALID_STATES": {"unknown", "unavailable", "none", ""},
                   "build_recipe_temperature_schedule":
                       schedule_ns["build_recipe_temperature_schedule"]},
    )
    return cooling_ns["_brewfather_pitch_target"], tracking_ns["_brewfather_recipe_schedule"]


def _batch():
    start = datetime.now(timezone.utc) - timedelta(hours=12)
    return {
        "name": "Julöl 2026",
        "status": "Fermenting",
        "fermentingStart": start.isoformat(),
        "recipe": {
            "fermentation": {
                "steps": [
                    {"actualTime": int(start.timestamp() * 1000), "stepTemp": 18, "stepTime": 3},
                    {"actualTime": int((start + timedelta(days=3)).timestamp() * 1000),
                     "stepTemp": 19, "stepTime": 3},
                ]
            }
        },
    }


def _hass(batches):
    def state(entity_id):
        if entity_id == BATCH_ENTITY:
            return SimpleNamespace(state=str(len(batches)), attributes={"data": batches})
        if "brew_tracker" in entity_id or "brewtracker" in entity_id:
            return SimpleNamespace(state="1", attributes={"recipe": {
                "fermentation": {"steps": [{"actualTime": 0, "stepTemp": 30}]}
            }})
        return None
    return SimpleNamespace(states=SimpleNamespace(get=state))


def test_cooling_uses_first_batch_fermentation_step_not_brewtracker():
    pitch, _ = _functions()
    target, source = pitch(_hass([_batch()]))
    assert target == 18
    assert source == BATCH_ENTITY


def test_tracking_uses_batch_schedule_not_brewtracker():
    _, track = _functions()
    target, source, kind, schedule = track(SimpleNamespace(hass=_hass([_batch()])))
    assert target == 18
    assert source == BATCH_ENTITY
    assert kind == "brewfather_recipe_schedule"
    assert schedule is not None and schedule["target_temperature_c"] == 18


def test_multiple_batches_do_not_choose_arbitrary_recipe():
    pitch, track = _functions()
    hass = _hass([_batch(), _batch()])
    assert pitch(hass) == (None, None)
    assert track(SimpleNamespace(hass=hass)) == (None, None, None, None)


def test_no_batch_does_not_fall_back_to_old_brewtracker_recipe():
    pitch, track = _functions()
    hass = _hass([])
    assert pitch(hass) == (None, None)
    assert track(SimpleNamespace(hass=hass)) == (None, None, None, None)


def test_missing_current_batch_never_uses_stale_tracker_or_local_batch():
    pitch, track = _functions()
    hass = _hass([{"name": "incomplete", "recipe": {}}])
    assert pitch(hass) == (None, None)
    target, source, kind, schedule = track(SimpleNamespace(hass=hass))
    assert target is None and kind is None and schedule is None
    assert source in {None, BATCH_ENTITY}
