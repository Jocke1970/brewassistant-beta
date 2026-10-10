"""0b6 safety contract: read-only computes dry-run intent, ABORT owns safety.

These are Python-source/AST behavior tests. They cannot prove physical outputs.
"""

from __future__ import annotations

import ast
import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_source_authority_runtime.py"
EMERGENCY = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_emergency_abort.py"
BUTTON = ROOT / "custom_components/brewassistant/button.py"


class Authority:
    def __init__(self):
        self.mode = "blocked"
        self.reason = "operator_observe_only"
        self.write_scope = "none"


def test_readonly_preserves_computed_source_intent_without_actuation():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    func = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_observer_snapshot")
    namespace = {"HotSideAuthority": Authority, "Any": Any}
    exec(compile(ast.Module(body=[func], type_ignores=[]), str(SOURCE), "exec"), namespace)
    original = {
        "runtime_source": "RAPT BrewZilla Profile",
        "requested_target": 65.0,
        "desired_heat_utilization": 75.0,
        "desired_pump_utilization": 90.0,
        "desired_heater_on": True,
        "desired_pump_on": True,
        "can_apply_target": True,
        "heat_utilization_action_needed": True,
        "control_reason": "Mash Rest regulation",
    }
    result = namespace["_observer_snapshot"](original, Authority())
    proposal = result["read_only_decision_preview"]
    assert proposal["target_c"] == 65
    assert proposal["heat_utilization_pct"] == 75
    assert proposal["pump_utilization_pct"] == 90
    assert proposal["executed"] is False
    assert result["read_only_actuation_blocked"] is True
    assert result["can_apply_target"] is False
    assert result["heat_utilization_action_needed"] is False
    assert original["can_apply_target"] is True


def test_abort_never_switches_off_controller_main_power():
    code = EMERGENCY.read_text(encoding="utf-8")
    assert "preserve_current_state_for_telemetry" in code
    assert '("main_power_off", "switch"' not in code
    assert 'readbacks["main_power"].state == "off"' not in code
    assert "output_off_requests_sent" in code
    assert "rapt_stop_confirmed" in code
    assert "physical_safe_state_certified" in code
    first = code.index("for key, domain, service, payload in output_commands:")
    stop = code.index('await _command(hass, result, "rapt_profile_end"')
    repeat = code.index('f"reassert_{key}"')
    assert first < stop < repeat


def test_rearm_requires_readonly_before_clearing_abort():
    code = BUTTON.read_text(encoding="utf-8")
    section = code.split("class BrewAssistantRearmBrewdayControlButton", 1)[1].split(
        "class BrewAssistantCounterflowChillerReadyButton", 1
    )[0]
    assert "observation_required(hass)" in section
    assert section.index("if not observation_required(hass)") < section.index(
        "await async_clear_brewday_operator_abort(hass)"
    )
    assert "start_brewzilla_profile" not in section
