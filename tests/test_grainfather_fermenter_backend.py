"""Regression checks for the parked Grainfather fermenter scaffold."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "custom_components/brewassistant/grainfather_fermenter/adapter.py"
README = ROOT / "custom_components/brewassistant/grainfather_fermenter/README.md"
REGISTRY = ROOT / "custom_components/brewassistant/modules/registry.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_grainfather_fermenter_is_separate_from_hot_side_reservation() -> None:
    registry = _read(REGISTRY)
    readme = _read(README)

    assert '"grainfather": ModuleManifest' in registry
    assert 'description="Future hot-side adapter for Grainfather hardware."' in registry
    assert "separate from BrewAssistant's reserved `grainfather` hot-side adapter" in readme


def test_discovery_uses_upstream_attributes_not_guessed_entity_ids() -> None:
    adapter = _read(ADAPTER)

    assert 'ENTITY_TYPE_ATTRIBUTE = "grainfather_entity_type"' in adapter
    assert 'FERMENTATION_DEVICE_TYPE = "fermentation_device"' in adapter
    assert 'BREW_SESSION_TYPE = "brew_session"' in adapter
    assert "sensor.grainfather_gf30_temperature" not in adapter


def test_phase_one_is_read_only_and_fail_passive() -> None:
    adapter = _read(ADAPTER)

    assert '"control_mode": "read_only"' in adapter
    assert '"model_verified": False' in adapter
    assert "hass.services.async_call" not in adapter
    assert ".async_call(" not in adapter


def test_future_target_readiness_requires_verified_controller_and_session() -> None:
    adapter = _read(ADAPTER)

    assert "controller_verified" in adapter
    assert 'session_status == "fermenting"' in adapter
    assert "profile_target_service_available" in adapter
    assert "future_supervised_target_ready" in adapter


def test_multiple_controller_devices_fail_closed() -> None:
    adapter = _read(ADAPTER)

    assert '"multiple_controller_linked_devices"' in adapter
    assert 'status = "ambiguous_device"' in adapter
