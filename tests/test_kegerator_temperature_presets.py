"""Regression checks for persistent kegerator temperature presets."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PRESET_PATH = ROOT / "custom_components/brewassistant/kegerator/temperature_preset.py"
SELECT_PATH = ROOT / "custom_components/brewassistant/select.py"
SUPERVISOR_PATH = ROOT / "custom_components/brewassistant/climate_backend/climate_supervisor.py"
CARD_PATH = ROOT / "dashboard/cards/kegerator_temperature_presets.yaml"
CARD_SV_PATH = ROOT / "dashboard/cards/kegerator_temperature_presets_sv.yaml"


def test_preset_targets_are_locked() -> None:
    source = PRESET_PATH.read_text(encoding="utf-8")
    assert 'PRESET_COLD_CRASH = "Cold Crash"' in source
    assert 'PRESET_STORAGE = "Storage"' in source
    assert 'PRESET_SERVING = "Serving"' in source
    assert "PRESET_COLD_CRASH: 2.0" in source
    assert "PRESET_STORAGE: 3.0" in source
    assert "PRESET_SERVING: 4.0" in source
    assert "DEFAULT_PRESET = PRESET_SERVING" in source


def test_preset_select_restores_and_reapplies_target() -> None:
    source = SELECT_PATH.read_text(encoding="utf-8")
    assert "class BrewAssistantKegeratorTemperaturePresetSelect" in source
    assert "RestoreEntity" in source
    assert "await self.async_get_last_state()" in source
    assert "await async_apply_temperature_preset(" in source
    assert '"target_temperature": target_for_preset(self._current_option)' in source
    assert '"persistent": True' in source


def test_climate_supervisor_uses_selected_preset_as_base() -> None:
    source = SUPERVISOR_PATH.read_text(encoding="utf-8")
    assert "selected_target as selected_kegerator_target" in source
    assert "selected_kegerator_target(hass)" in source
    assert "MIN_EFFECTIVE_TARGET = 1.0" in source
    assert "MAX_EFFECTIVE_TARGET = 12.0" in source


def test_dashboard_quick_selects_have_language_parity() -> None:
    canonical = CARD_PATH.read_text(encoding="utf-8")
    swedish = CARD_SV_PATH.read_text(encoding="utf-8")
    entity = "select.brewassistant_kegerator_temperature_preset"
    for source in (canonical, swedish):
        assert entity in source
        assert "option: Cold Crash" in source
        assert "option: Storage" in source
        assert "option: Serving" in source
        assert "2.0 °C" in source
        assert "3.0 °C" in source
        assert "4.0 °C" in source
