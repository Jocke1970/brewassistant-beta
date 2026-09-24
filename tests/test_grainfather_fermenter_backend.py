"""Regression checks for the Grainfather/GF30 fermenter backend."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "custom_components/brewassistant/grainfather_fermenter/adapter.py"
THERMAL = ROOT / "custom_components/brewassistant/grainfather_fermenter/thermal.py"
README = ROOT / "custom_components/brewassistant/grainfather_fermenter/README.md"
REGISTRY = ROOT / "custom_components/brewassistant/modules/registry.py"


def _load_thermal_module():
    spec = importlib.util.spec_from_file_location("brewassistant_gf30_thermal_test", THERMAL)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_gf30_backend_is_separate_from_reserved_grainfather_hot_side_module() -> None:
    registry = REGISTRY.read_text(encoding="utf-8")
    docs = README.read_text(encoding="utf-8")
    assert '"grainfather": ModuleManifest(' in registry
    assert 'description="Future hot-side adapter for Grainfather hardware."' in registry
    assert "separate from BrewAssistant's reserved `grainfather` hot-side adapter" in docs


def test_gf30_backend_discovers_upstream_by_attributes_not_guessed_entity_ids() -> None:
    source = BACKEND.read_text(encoding="utf-8")
    assert 'ENTITY_TYPE_ATTRIBUTE = "grainfather_entity_type"' in source
    assert 'FERMENTATION_DEVICE_TYPE = "fermentation_device"' in source
    assert 'BREW_SESSION_TYPE = "brew_session"' in source
    assert "sensor.grainfather_gf30" not in source


def test_phase_1_backend_is_read_only_and_fail_passive() -> None:
    source = BACKEND.read_text(encoding="utf-8")
    thermal = THERMAL.read_text(encoding="utf-8")
    assert '"control_mode": "read_only"' in source
    assert '"control_mode": "read_only"' in thermal
    assert "hass.services.async_call" not in source
    assert "async_call(" not in source
    assert "async_call(" not in thermal
    assert '"model_verified": False' in source
    assert '"control_allowed": False' in thermal


def test_future_profile_target_bridge_requires_controller_session_and_service() -> None:
    source = BACKEND.read_text(encoding="utf-8")
    assert 'PROFILE_TARGET_SERVICE = "adjust_current_step_temperature"' in source
    assert "controller_verified" in source
    assert 'linked_session.get("status") == "fermenting"' in source
    assert "profile_target_service_available" in source
    assert "future_supervised_target_ready" in source


def test_ambiguous_multiple_controller_devices_fail_closed() -> None:
    source = BACKEND.read_text(encoding="utf-8")
    assert 'return None, "multiple_controller_linked_devices"' in source
    assert 'status = "ambiguous_device"' in source


def test_manual_preflight_accepts_fresh_pill_and_manual_pair() -> None:
    module = _load_thermal_module()
    now = datetime(2026, 9, 24, 20, 0, tzinfo=timezone.utc)

    snapshot = module.build_manual_preflight_snapshot(
        pill_temperature_c=20.2,
        manual_temperature_c=20.0,
        pill_observed_at=now - timedelta(minutes=2),
        manual_observed_at=now - timedelta(minutes=1),
        now=now,
    )

    assert snapshot["status"] == "pair_agrees"
    assert snapshot["dual_measurement_available"] is True
    assert snapshot["learning_sample_eligible"] is True
    assert snapshot["control_allowed"] is False
    assert snapshot["temperature_delta_c"] == 0.2
    assert snapshot["source_selection"] == "no_automatic_winner"


def test_manual_preflight_surfaces_disagreement_without_choosing_winner() -> None:
    module = _load_thermal_module()
    now = datetime(2026, 9, 24, 20, 0, tzinfo=timezone.utc)

    snapshot = module.build_manual_preflight_snapshot(
        pill_temperature_c=21.0,
        manual_temperature_c=20.0,
        pill_observed_at=now,
        manual_observed_at=now,
        now=now,
        agreement_tolerance_c=0.5,
    )

    assert snapshot["status"] == "pair_disagrees"
    assert snapshot["within_tolerance"] is False
    assert snapshot["temperature_delta_c"] == 1.0
    assert snapshot["source_selection"] == "no_automatic_winner"
    assert snapshot["control_allowed"] is False


def test_manual_preflight_rejects_stale_pill_from_learning_sample() -> None:
    module = _load_thermal_module()
    now = datetime(2026, 9, 24, 20, 0, tzinfo=timezone.utc)

    snapshot = module.build_manual_preflight_snapshot(
        pill_temperature_c=20.0,
        manual_temperature_c=20.0,
        pill_observed_at=now - timedelta(minutes=16),
        manual_observed_at=now,
        now=now,
    )

    assert snapshot["status"] == "awaiting_pill"
    assert snapshot["pill"]["state"] == "stale"
    assert snapshot["learning_sample_eligible"] is False


def test_manual_preflight_rejects_implausible_manual_value() -> None:
    module = _load_thermal_module()
    now = datetime(2026, 9, 24, 20, 0, tzinfo=timezone.utc)

    snapshot = module.build_manual_preflight_snapshot(
        pill_temperature_c=20.0,
        manual_temperature_c=99.0,
        pill_observed_at=now,
        manual_observed_at=now,
        now=now,
    )

    assert snapshot["status"] == "awaiting_manual_reference"
    assert snapshot["manual_reference"]["state"] == "invalid_or_missing"
    assert snapshot["learning_sample_eligible"] is False
