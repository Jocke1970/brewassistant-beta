"""Beta.14 acceptance gates missing from the previously green suite.

The tests intentionally fail until #220's two remaining requirements are
implemented. Tests run on the release branch only; never dev.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SWITCHES = ROOT / "custom_components/brewassistant/switch.py"
MANUAL_UI = (
    ROOT / "dashboard/cards/brewassistant_manual_brewday.yaml",
    ROOT / "dashboard/cards/brewassistant_manual_brewday_sv.yaml",
)
READ_ONLY = "switch.brewassistant_brewzilla_observe_only"
DIRECT = {
    "number.brewzilla_target_temperature",
    "number.brewzilla_heat_utilization",
    "number.brewzilla_pump_utilization",
    "switch.brewzilla_heater",
    "switch.brewzilla_pump",
}


def _observer_panels(text: str) -> list[str]:
    """Extract observer-only conditional blocks by indentation, no YAML dependency."""
    lines = text.splitlines()
    sections = []
    for i, line in enumerate(lines):
        if line.strip() != f"- entity: {READ_ONLY}":
            continue
        indent = len(line) - len(line.lstrip())
        if i + 1 >= len(lines) or lines[i + 1].strip() not in {'state: "on"', "state: 'on'", "state: on"}:
            continue
        parent = i - 1
        while parent >= 0:
            candidate = lines[parent]
            if candidate.strip() == "- type: conditional" and len(candidate) - len(candidate.lstrip()) < indent:
                break
            parent -= 1
        if parent < 0:
            continue
        parent_indent = len(lines[parent]) - len(lines[parent].lstrip())
        end = parent + 1
        while end < len(lines):
            other = lines[end]
            other_indent = len(other) - len(other.lstrip())
            if end > parent and other.strip() and other_indent <= parent_indent:
                break
            end += 1
        sections.append("\n".join(lines[parent:end]))
    return sections


def test_deprecated_orchestration_switch_is_not_registered():
    """A nonfunctional look-alike must not remain exposed as a control."""
    tree = ast.parse(SWITCHES.read_text(encoding="utf-8"))
    declared = next(
        node for node in tree.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == "ORCHESTRATION_SWITCHES"
    )
    entries = ast.literal_eval(declared.value)
    assert "brewzilla_orchestration_enabled" not in entries, (
        "Deprecated orchestration_enabled remains registered but cannot stop BA writes"
    )


def test_manual_brewday_direct_operator_controls_exist_in_read_only():
    """Operators need direct entity controls, not BA-transported setpoints."""
    for path in MANUAL_UI:
        panels = _observer_panels(path.read_text(encoding="utf-8"))
        assert panels, f"{path.name}: no Manual Brewday read-only operator panel"
        block = "\n".join(panels)
        reachable = {
            line.split("- entity: ", 1)[1].strip()
            for line in block.splitlines()
            if line.strip().startswith("- entity: ")
        }
        assert DIRECT <= reachable, (
            f"{path.name}: missing direct controls {sorted(DIRECT - reachable)}"
        )
        assert not any(
            entity.startswith("number.brewassistant_brewzilla_manual_")
            for entity in reachable
        ), f"{path.name}: BA-transported setpoints should not be in read-only controls"
