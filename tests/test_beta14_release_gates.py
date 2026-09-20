"""Release blockers that the older green regression suite did not cover.

These tests intentionally fail while #220's two outstanding acceptance
requirements are not implemented. Run on release branches only, never dev.
"""

from __future__ import annotations

import ast
from pathlib import Path

import yaml

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


def _walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


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
        "Deprecated orchestration_enabled is still registered but does not stop BA writes"
    )


def test_manual_brewday_has_direct_operator_controls_in_read_only():
    """Manual UI must bypass BA's automatic transport only via explicit HA controls."""
    for path in MANUAL_UI:
        dashboard = yaml.safe_load(path.read_text(encoding="utf-8"))
        observer_cards = [
            item for item in _walk(dashboard)
            if item.get("type") == "conditional"
            and any(
                isinstance(c, dict)
                and c.get("entity") == READ_ONLY
                and c.get("state") == "on"
                for c in item.get("conditions", [])
            )
        ]
        assert observer_cards, f"{path.name}: no manual read-only operator panel"
        reachable_entities = {
            item["entity"]
            for panel in observer_cards
            for item in _walk(panel.get("card"))
            if isinstance(item.get("entity"), str)
        }
        assert DIRECT <= reachable_entities, (
            f"{path.name}: Manual read-only has no explicit direct operator "
            f"control for {sorted(DIRECT - reachable_entities)}"
        )
        assert not any(
            item.startswith("number.brewassistant_brewzilla_manual_")
            for item in reachable_entities
        ), f"{path.name}: BA-transported setpoints cannot be used in read-only"
