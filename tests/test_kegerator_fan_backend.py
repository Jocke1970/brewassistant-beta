"""Regression checks for the consolidated kegerator fan backend."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "custom_components/brewassistant/kegerator/fan_model.py"
CONTROL_PATH = ROOT / "custom_components/brewassistant/kegerator/fan_control.py"
COORDINATOR_PATH = ROOT / "custom_components/brewassistant/coordinator.py"
SELECT_PATH = ROOT / "custom_components/brewassistant/select.py"
WATCHDOG_PATH = ROOT / "custom_components/brewassistant/kegerator/fan_watchdog.py"


def _load_model():
    spec = importlib.util.spec_from_file_location("brewassistant_kegerator_fan_model_test", MODEL_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


MODEL = _load_model()


def _inputs(**overrides):
    values = {
        "compressor_active": False,
        "fan_running": False,
        "fan_switch_ok": True,
        "power_sensor_ok": True,
        "temperature_sensor_ok": True,
        "temperature_context_available": True,
        "climate_conflict": False,
        "hvac_action": "idle",
        "temperature_delta": 0.0,
        "trend_c_per_hour": 0.0,
    }
    values.update(overrides)
    return MODEL.FanInputs(**values)


def test_smart_auto_is_default_mode() -> None:
    assert MODEL.DEFAULT_FAN_MODE == "Smart auto"
    assert "Smart auto" in MODEL.FAN_MODE_OPTIONS


def test_disabled_controller_releases_physical_fan() -> None:
    decision = MODEL.decide(
        enabled=False,
        mode=MODEL.MODE_SMART_AUTO,
        inputs=_inputs(fan_running=True),
        afterrun_active=False,
    )
    assert decision.state == "disabled"
    assert decision.reason == "fan_auto_disabled"
    assert decision.desired_switch_state == "unmanaged"
    assert decision.action == "none"
    assert decision.command is None


def test_off_mode_keeps_fan_off_when_auto_owns_it() -> None:
    decision = MODEL.decide(
        enabled=True,
        mode=MODEL.MODE_OFF,
        inputs=_inputs(fan_running=True),
        afterrun_active=False,
    )
    assert decision.should_run is False
    assert decision.action == "turn_off_fan"
    assert decision.command == "kegerator_fan_off"


def test_cooling_only_ignores_afterrun_window() -> None:
    decision = MODEL.decide(
        enabled=True,
        mode=MODEL.MODE_COOLING_ONLY,
        inputs=_inputs(compressor_active=False, fan_running=True),
        afterrun_active=True,
    )
    assert decision.state == "standby"
    assert decision.reason == "compressor_idle"
    assert decision.should_run is False


def test_afterrun_mode_runs_during_afterrun() -> None:
    decision = MODEL.decide(
        enabled=True,
        mode=MODEL.MODE_AFTERRUN,
        inputs=_inputs(),
        afterrun_active=True,
    )
    assert decision.state == "afterrun"
    assert decision.should_run is True
    assert decision.command == "kegerator_fan_on"


def test_smart_auto_runs_when_air_is_too_warm() -> None:
    decision = MODEL.decide(
        enabled=True,
        mode=MODEL.MODE_SMART_AUTO,
        inputs=_inputs(temperature_delta=1.0),
        afterrun_active=False,
    )
    assert decision.state == "circulating"
    assert decision.reason == "smart_too_warm"
    assert decision.should_run is True


def test_smart_auto_hysteresis_keeps_running_until_stop_band() -> None:
    decision = MODEL.decide(
        enabled=True,
        mode=MODEL.MODE_SMART_AUTO,
        inputs=_inputs(fan_running=True, temperature_delta=0.4, trend_c_per_hour=0.08),
        afterrun_active=False,
    )
    assert decision.state == "circulating"
    assert decision.reason == "smart_hysteresis"
    assert decision.should_run is True

    stopped = MODEL.decide(
        enabled=True,
        mode=MODEL.MODE_SMART_AUTO,
        inputs=_inputs(fan_running=True, temperature_delta=0.1, trend_c_per_hour=0.0),
        afterrun_active=False,
    )
    assert stopped.state == "standby"
    assert stopped.reason == "smart_stable"
    assert stopped.should_run is False


def test_smart_auto_fails_passive_without_temperature_context() -> None:
    decision = MODEL.decide(
        enabled=True,
        mode=MODEL.MODE_SMART_AUTO,
        inputs=_inputs(
            temperature_context_available=False,
            temperature_sensor_ok=False,
            temperature_delta=None,
            trend_c_per_hour=None,
        ),
        afterrun_active=False,
    )
    assert decision.state == "standby"
    assert decision.reason == "smart_temperature_context_unavailable"
    assert decision.should_run is False
    assert decision.warning_level == "sensor_issue"


def test_compressor_has_priority_in_smart_auto() -> None:
    decision = MODEL.decide(
        enabled=True,
        mode=MODEL.MODE_SMART_AUTO,
        inputs=_inputs(compressor_active=True, temperature_delta=-1.5),
        afterrun_active=False,
    )
    assert decision.state == "compressor_follow"
    assert decision.reason == "compressor_active"
    assert decision.should_run is True


def test_single_scheduler_contract() -> None:
    coordinator = COORDINATOR_PATH.read_text(encoding="utf-8")
    control = CONTROL_PATH.read_text(encoding="utf-8")

    assert "async_apply_kegerator_fan_auto" not in coordinator
    assert 'SCHEDULER_OWNER = "fan_auto_switch_timer"' in control
    assert not WATCHDOG_PATH.exists()


def test_select_exposes_smart_auto_and_applies_mode_immediately() -> None:
    source = SELECT_PATH.read_text(encoding="utf-8")
    assert '"Smart auto"' in source
    assert 'self._current_option = "Smart auto"' in source
    assert "await async_apply_kegerator_fan_auto(self.coordinator.hass)" in source
