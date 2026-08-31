"""Regression contract for realistic Mash-In readiness and operator override."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
READINESS = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_mash_in_readiness_contract.py"
INIT = ROOT / "custom_components/brewassistant/brewzilla/__init__.py"
BUTTONS = ROOT / "custom_components/brewassistant/button.py"
TRANSLATIONS = (
    ROOT / "custom_components/brewassistant/translations/en.json",
    ROOT / "custom_components/brewassistant/translations/sv.json",
)
RUNTIME_CARDS = (
    ROOT / "dashboard/cards/brewassistant_brewday_runtime_flow.yaml",
    ROOT / "dashboard/cards/brewassistant_brewday_runtime_flow_sv.yaml",
)
MASH_IN_CARDS = (
    ROOT / "dashboard/cards/brewzilla_mash_in_controls.yaml",
    ROOT / "dashboard/cards/brewzilla_mash_in_controls_sv.yaml",
)


def _function_body(source: str, name: str, next_name: str) -> str:
    return source.split(f"def {name}", 1)[1].split(f"def {next_name}", 1)[0]


def test_readiness_tolerances_match_physical_operator_contract() -> None:
    source = READINESS.read_text(encoding="utf-8")
    assert "AUTO_READY_TOLERANCE_C = 1.0" in source
    assert "MANUAL_OVERRIDE_TOLERANCE_C = 2.0" in source
    assert "LOCAL_TARGET_TOLERANCE_C = 0.5" in source
    assert "MAX_AUTO_PROCESS_AGE_SECONDS = 90" in source


def test_automatic_ready_uses_only_fresh_canonical_process_temperature() -> None:
    source = READINESS.read_text(encoding="utf-8")
    canonical = _function_body(source, "_canonical_process_temperature", "_automatic_ready")
    automatic = _function_body(source, "_automatic_ready", "_locked_external_candidate")

    assert 'for key in ("mash_temperature", "brewzilla_mash_temperature")' in canonical
    assert "current_temperature" not in canonical
    assert "brewzilla_current_temp" not in canonical
    assert 'if not snapshot.get("mash_in_process_temperature_fresh")' in automatic
    assert "abs(process - target) <= AUTO_READY_TOLERANCE_C" in automatic


def test_stale_external_value_is_diagnostics_only() -> None:
    source = READINESS.read_text(encoding="utf-8")
    locked = _function_body(source, "_locked_external_candidate", "_resolved_process")
    resolved = _function_body(source, "_resolved_process", "_manual_override_diagnostics")
    augment = _function_body(source, "_augment_snapshot", "build_mash_in_readiness_snapshot")

    assert "This is diagnostics only" in locked
    assert 'resolved.get("mash_temperature_source_lock_entity")' in locked
    assert 'locked.get("age_seconds")' in resolved
    assert 'process.get("value") if process.get("fresh") else None' in augment
    assert '"mash_in_confirmation_recommended": False' in augment
    assert '"mash_in_heat_strategy_active": False' in augment


def test_manual_override_has_separate_fresh_and_cloud_stale_paths() -> None:
    source = READINESS.read_text(encoding="utf-8")
    diagnostics = _function_body(source, "_manual_override_diagnostics", "_augment_snapshot")

    assert "fresh_process_near = bool(" in diagnostics
    assert "stale_local_near = bool(" in diagnostics
    assert "abs(process_delta) <= MANUAL_OVERRIDE_TOLERANCE_C" in diagnostics
    assert "not abs(process_delta) <= AUTO_READY_TOLERANCE_C" in diagnostics
    assert "abs(wort_delta) <= MANUAL_OVERRIDE_TOLERANCE_C" in diagnostics
    assert "abs(local_target_delta) <= LOCAL_TARGET_TOLERANCE_C" in diagnostics
    assert '"fresh_process_within_manual_strike_distance"' in diagnostics
    assert '"cloud_process_stale_local_brewzilla_near_strike"' in diagnostics
    assert '"mash_in_override_in_scope": in_scope' in diagnostics
    assert '"mash_in_override_warning_required": bool(available and stale_local_near)' in diagnostics


def test_operator_override_only_latches_ready_gate() -> None:
    source = READINESS.read_text(encoding="utf-8")
    override = source.split("async def async_override_mash_in_ready", 1)[1].split(
        "def install_mash_in_readiness_contract", 1
    )[0]

    assert 'if not diagnostics.get("mash_in_override_available")' in override
    assert "gate._ensure_gate_for_snapshot" in override
    assert 'store["last_trigger"] = "operator_override"' in override
    assert '"mash_in_gate_state": gate.READY_STATE' in override
    assert "set_heat_utilization" not in override
    assert "set_pump_utilization" not in override
    assert "set_target" not in override
    assert "async_apply_brewzilla_target_if_allowed" not in override


def test_readiness_contract_is_installed_after_base_mash_in_gate() -> None:
    source = INIT.read_text(encoding="utf-8")
    base_pos = source.index("_mash_in_gate.install_mash_in_gate()")
    readiness_pos = source.index("_mash_in_readiness_contract.install_mash_in_readiness_contract()")
    assert base_pos < readiness_pos


def test_override_button_is_exposed_as_operator_action() -> None:
    source = BUTTONS.read_text(encoding="utf-8")
    assert "BrewAssistantBrewZillaMashInOverrideButton(coordinator)" in source
    assert "class BrewAssistantBrewZillaMashInOverrideButton" in source
    assert '"brewzilla_mash_in_override"' in source
    assert "async_override_mash_in_ready" in source
    assert "build_mash_in_readiness_snapshot" in source


def test_runtime_ui_shows_stale_diagnostics_and_bounded_override() -> None:
    for path in RUNTIME_CARDS:
        source = path.read_text(encoding="utf-8")
        assert "button.brewassistant_mash_in_override" in source
        assert "mash_in_override_in_scope" in source
        assert "mash_in_override_process_temperature_age_seconds" in source
        assert "mash_in_override_process_temperature_fresh" in source
        assert "mash_in_override_available" in source
        assert "mash_in_auto_ready_tolerance_c" in source
        assert "mash_in_override_tolerance_c" in source
        assert "mdi:hand-okay" in source
        assert "button.brewassistant_mash_in_started" in source


def test_standalone_mash_in_cards_include_same_override_path() -> None:
    for path in MASH_IN_CARDS:
        source = path.read_text(encoding="utf-8")
        assert "button.brewassistant_mash_in_override" in source
        assert "mash_in_override_available" in source
        assert "mash_in_override_process_temperature_age_seconds" in source
        assert "button.brewassistant_mash_in_started" in source


def test_override_button_has_en_and_sv_names() -> None:
    for path in TRANSLATIONS:
        source = path.read_text(encoding="utf-8")
        assert '"brewzilla_mash_in_override"' in source
