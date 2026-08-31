"""Architecture regression checks for shared kegerator/fermentation cooling."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONST = ROOT / "custom_components/brewassistant/const.py"
CONFIG_FLOW = ROOT / "custom_components/brewassistant/config_flow.py"
CONFIGURED = ROOT / "custom_components/brewassistant/configured_entities.py"
FAN_CONTROL = ROOT / "custom_components/brewassistant/kegerator/fan_control.py"


def test_shared_cooling_bridge_is_explicit_and_defaults_on_for_current_hardware() -> None:
    const = CONST.read_text(encoding="utf-8")
    config_flow = CONFIG_FLOW.read_text(encoding="utf-8")

    assert 'CONF_SHARED_KEGERATOR_FERMENTATION_COOLING = "shared_kegerator_fermentation_cooling"' in const
    assert "DEFAULT_SHARED_KEGERATOR_FERMENTATION_COOLING = True" in const
    assert "CONF_SHARED_KEGERATOR_FERMENTATION_COOLING" in config_flow
    assert "BOOLEAN_CONFIG_KEYS" in config_flow


def test_kegerator_backend_uses_typed_bridge_config() -> None:
    configured = CONFIGURED.read_text(encoding="utf-8")
    fan = FAN_CONTROL.read_text(encoding="utf-8")

    assert "def configured_bool(" in configured
    assert "def _shared_cooling_bridge_enabled(" in fan
    assert "configured_bool(" in fan
    assert 'ARCHITECTURE_SCOPE = "kegerator_fan_only"' in fan
    assert 'SHARED_COOLING_BRIDGE = "fermentation_uses_kegerator_cooling_hardware"' in fan


def test_fermentation_context_is_gated_by_shared_bridge() -> None:
    fan = FAN_CONTROL.read_text(encoding="utf-8")

    assert "fermentation_owner = bridge_enabled and fermentation_scope" in fan
    assert "if fermentation_owner and f_enabled:" in fan
    assert 'source = "fermentation_shared_cooling_bridge"' in fan
    assert "elif k_enabled:" in fan
    assert 'source = "kegerator"' in fan


def test_bridge_can_be_disabled_without_disabling_kegerator_fan_control() -> None:
    fan = FAN_CONTROL.read_text(encoding="utf-8")

    assert '"shared_cooling_bridge_enabled": inputs.shared_cooling_bridge_enabled' in fan
    assert '"shared_cooling_bridge_active": inputs.shared_cooling_bridge_active' in fan
    assert '"climate_context_source": inputs.climate_context_source' in fan
    assert "Disabling\n    the bridge makes this backend ignore the fermentation climate entirely." in fan
