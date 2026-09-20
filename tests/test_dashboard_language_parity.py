"""Dashboard language parity and operator action contracts."""

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
CARDS_DIR = ROOT / "dashboard/cards"


def test_every_dashboard_card_has_swedish_mirror():
    english = {p.stem for p in CARDS_DIR.glob("*.yaml") if not p.stem.endswith("_sv")}
    for name in english:
        assert (CARDS_DIR / f"{name}_sv.yaml").exists(), name


def test_sanity_dashboard_has_swedish_mirror():
    for name in ("sanity_dashboard",):
        assert (CARDS_DIR / f"{name}_sv.yaml").exists()


def test_swedish_cards_do_not_introduce_new_entity_references():
    pattern = r"\b(?:sensor|binary_sensor|button|switch|number|select|input_boolean|input_number|climate)\.[a-zA-Z0-9_]+"
    for en in CARDS_DIR.glob("*.yaml"):
        if en.stem.endswith("_sv"):
            continue
        sv = CARDS_DIR / f"{en.stem}_sv.yaml"
        if not sv.exists():
            continue
        # An EN/SV pair must share the same entity references, regardless of translated copy.
        assert set(re.findall(pattern, sv.read_text(encoding="utf-8"))) <= set(re.findall(pattern, en.read_text(encoding="utf-8"))), en.name


def test_swedish_cards_keep_same_action_references():
    pattern = r"(?:service|entity_id):\s*([\w.]+)"
    for en in CARDS_DIR.glob("*.yaml"):
        if en.stem.endswith("_sv"):
            continue
        sv = CARDS_DIR / f"{en.stem}_sv.yaml"
        if not sv.exists():
            continue
        assert set(re.findall(pattern, sv.read_text(encoding="utf-8"))) <= set(re.findall(pattern, en.read_text(encoding="utf-8"))), en.name


def test_brewday_modular_cards_exist():
    for name in ("brewassistant_brewday", "brewday_operator_actions"):
        assert (CARDS_DIR / f"{name}.yaml").exists()
        assert (CARDS_DIR / f"{name}_sv.yaml").exists()


def test_brewday_overview_stays_action_free():
    forbidden = (
        "brewassistant.manual_brewday_prepare",
        "button.brewassistant_confirm_supervised_apply",
        "button.brewassistant_cancel_supervised_apply",
        "button.brewassistant_abort_brewday",
        "button.brewassistant_rearm_brewday_control",
        "button.brewassistant_mash_in_started",
        "button.brewassistant_mash_in_complete",
    )
    for filename in ("brewassistant_brewday.yaml", "brewassistant_brewday_sv.yaml"):
        source = (CARDS_DIR / filename).read_text(encoding="utf-8")
        assert "name: Brewday" in source
        for ref in forbidden:
            assert ref not in source


def test_brewday_confirm_attention_is_pending_driven_and_reduced_motion_safe():
    for filename in ("brewday_operator_actions.yaml", "brewday_operator_actions_sv.yaml"):
        source = (CARDS_DIR / filename).read_text(encoding="utf-8")
        assert "sensor.brewassistant_brewzilla_pending_action" in source
        assert "ba-confirm-pulse" in source
        assert "1.4s ease-in-out infinite" in source
        assert "prefers-reduced-motion: reduce" in source
        assert "animation: none !important" in source
        assert 'entity: switch.brewassistant_brewzilla_observe_only\n          state: "off"' in source


def test_brewday_supervised_action_row_is_only_rendered_for_real_pending_action():
    """All four inactive states must guard the same conditional before CONFIRM/REJECT."""
    for filename in ("brewday_operator_actions.yaml", "brewday_operator_actions_sv.yaml"):
        source = (CARDS_DIR / filename).read_text(encoding="utf-8")
        pending_start = source.index("          - type: conditional\n            conditions:\n              - entity: sensor.brewassistant_brewzilla_pending_action")
        confirm_start = source.index("button.brewassistant_confirm_supervised_apply", pending_start)
        section = source[pending_start:confirm_start]
        for inactive in ("unknown", "unavailable", "none", "idle"):
            assert f'state_not: "{inactive}"' in section
        assert "card:\n              type: horizontal-stack" in section
        assert "button.brewassistant_cancel_supervised_apply" in source
        assert "state_not: observe-only" in source


def test_legacy_mash_circulation_fallback_is_tightly_scoped():
    for filename in ("brewzilla_mash_in_confirm.yaml", "brewzilla_mash_in_confirm_sv.yaml"):
        source = (CARDS_DIR / filename).read_text(encoding="utf-8")
        assert "sensor.brewassistant_brewday_runtime_state" in source
        assert "sensor.brewassistant_brewday_runtime_stage" in source
        assert "runtimeStage.includes('mash')" in source
        assert "const pumpStopped = !pumpOn && !Number.isNaN(util) && util <= 0.1;" in source
        assert "(!pending && completed && activeMash && pumpStopped)" in source


def test_brewzilla_direct_service_controls_are_idle_only():
    idle_guard = '''        - condition: state
          entity: sensor.brewassistant_brewday_runtime_state
          state: "idle"
'''
    for filename in ("brewzilla.yaml", "brewzilla_sv.yaml"):
        source = (CARDS_DIR / filename).read_text(encoding="utf-8")
        assert source.count(idle_guard) >= 2
        assert "switch.brewzilla_heater" in source
        assert "switch.brewzilla_pump" in source
        assert "brewassistant.apply_brewzilla_target" in source
        assert "brewassistant.abort_brewzilla" in source
        assert "BZ SAFE-DOWN" in source


def test_hub_does_not_claim_unowned_power_sensor_is_brewzilla_watts():
    for filename in ("brewassistant_hub.yaml", "brewassistant_hub_sv.yaml"):
        source = (CARDS_DIR / filename).read_text(encoding="utf-8")
        assert "sensor.brewzilla_power" not in source or "sensor.brewassistant_brewzilla_power" in source
