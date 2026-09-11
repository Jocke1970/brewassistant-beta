"""Regression checks for the dormant Grainfather/GF30 fermenter backend."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "custom_components/brewassistant/grainfather_fermenter/adapter.py"
README = ROOT / "custom_components/brewassistant/grainfather_fermenter/README.md"
REGISTRY = ROOT / "custom_components/brewassistant/modules/registry.py"


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
    assert '"control_mode": "read_only"' in source
    assert "hass.services.async_call" not in source
    assert "async_call(" not in source
    assert '"model_verified": False' in source


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
