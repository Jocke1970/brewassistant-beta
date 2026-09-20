"""Release gates for one read-only switch and the separate Manual Brewday UI.

Cards are standalone components by dashboard/README.md policy: the read-only
operator card is mounted alongside Manual Brewday, not nested in its source file.
Neither an ordinary BA write nor a generic override may bypass read-only.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SWITCHES = ROOT / "custom_components/brewassistant/switch.py"
OBSERVER_UI = (
    ROOT / "dashboard/cards/brewzilla_observe_only.yaml",
    ROOT / "dashboard/cards/brewzilla_observe_only_sv.yaml",
)
MANUAL_UI = (
    ROOT / "dashboard/cards/brewassistant_manual_brewday.yaml",
    ROOT / "dashboard/cards/brewassistant_manual_brewday_sv.yaml",
)
DOCS = ROOT / "dashboard/README.md"
READ_ONLY = "switch.brewassistant_brewzilla_observe_only"
RAPT_ACTIVE = "binary_sensor.brewzilla_profile_active"
DIRECT = {
    "number.brewzilla_target_temperature",
    "number.brewzilla_heat_utilization",
    "number.brewzilla_pump_utilization",
    "switch.brewzilla_heater",
    "switch.brewzilla_pump",
}


def _observer_panels(text: str) -> list[str]:
    """Extract observer-only conditional blocks by indentation; no YAML dependency."""
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
    """Only the working one-switch control can be installed by the switch platform."""
    tree = ast.parse(SWITCHES.read_text(encoding="utf-8"))
    declared = next(
        node for node in tree.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == "ORCHESTRATION_SWITCHES"
    )
    entries = ast.literal_eval(declared.value)
    assert "brewzilla_orchestration_enabled" not in entries
    source = SWITCHES.read_text(encoding="utf-8")
    assert 'deprecated_unique_id = f"{DOMAIN}_switch_brewzilla_orchestration_enabled"' in source
    assert 'registry.async_get_entity_id("switch", DOMAIN, deprecated_unique_id)' in source
    assert "registry.async_remove(deprecated_entity)" in source
    assert "BrewAssistantBrewZillaObserveOnlySwitch(coordinator)" in source


def test_manual_brewday_direct_operator_controls_exist_in_read_only():
    """Read-only controls exist as standalone cards, never BA-owned auto setpoints."""
    docs = DOCS.read_text(encoding="utf-8")
    assert "standalone reusable cards" in docs
    for path in MANUAL_UI:
        source = path.read_text(encoding="utf-8")
        assert "switch.brewassistant_brewzilla_manual_target_override" in source
    for path in OBSERVER_UI:
        source = path.read_text(encoding="utf-8")
        assert "service: brewassistant.abort_brewzilla" in source
        panels = _observer_panels(source)
        assert panels, f"{path.name}: no standalone Manual Brewday read-only panel"
        block = "\n".join(panels)
        assert '- entity: sensor.brewassistant_brewday_runtime_source\n        state: "Manual Brewday"' in block
        assert f'- entity: {RAPT_ACTIVE}\n        state: "off"' in block, (
            f"{path.name}: fail-closed manual UI must require RAPT profile OFF"
        )
        assert '- entity: sensor.brewassistant_brewday_operator_control_state\n        state_not: "aborted"' in block
        # Entities rows use '- entity:', custom:button-card uses 'entity:'.
        # Both are real, operator-clickable RCL controls in this conditional.
        reachable = {
            line.strip().split("entity: ", 1)[1].strip()
            for line in block.splitlines()
            if line.strip().startswith(("- entity: ", "entity: "))
        }
        assert DIRECT <= reachable, f"{path.name}: missing direct controls {sorted(DIRECT - reachable)}"
        assert not any(entity.startswith("number.brewassistant_brewzilla_manual_") for entity in reachable)
        assert "action: toggle" in block
        assert "confirmation:" in block
