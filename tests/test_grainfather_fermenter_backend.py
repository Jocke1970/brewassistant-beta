"""Regression checks for the Grainfather/GF30 fermenter backend."""

from __future__ import annotations

import ast
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "custom_components/brewassistant/grainfather_fermenter/adapter.py"
THERMAL = ROOT / "custom_components/brewassistant/grainfather_fermenter/thermal.py"
LEARNING = ROOT / "custom_components/brewassistant/grainfather_fermenter/learning.py"
COOLANT = ROOT / "custom_components/brewassistant/grainfather_fermenter/coolant.py"
PREFLIGHT_RUNTIME = ROOT / "custom_components/brewassistant/grainfather_fermenter/preflight_runtime.py"
GF30_SENSORS = ROOT / "custom_components/brewassistant/grainfather_fermenter/sensors.py"
TOP_SENSOR = ROOT / "custom_components/brewassistant/sensor.py"
TOP_INIT = ROOT / "custom_components/brewassistant/__init__.py"
CONST = ROOT / "custom_components/brewassistant/const.py"
CONFIG_FLOW = ROOT / "custom_components/brewassistant/config_flow.py"
COORDINATOR = ROOT / "custom_components/brewassistant/coordinator.py"
SERVICES = ROOT / "custom_components/brewassistant/services.yaml"
README = ROOT / "custom_components/brewassistant/grainfather_fermenter/README.md"
REGISTRY = ROOT / "custom_components/brewassistant/modules/registry.py"


def _load_thermal_module():
    spec = importlib.util.spec_from_file_location("brewassistant_gf30_thermal_test", THERMAL)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_learning_module():
    spec = importlib.util.spec_from_file_location("brewassistant_gf30_learning_test", LEARNING)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_coolant_module():
    spec = importlib.util.spec_from_file_location("brewassistant_gf30_coolant_test", COOLANT)
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



def test_gf30_new_backend_files_are_valid_python() -> None:
    for path in (THERMAL, LEARNING, COOLANT, PREFLIGHT_RUNTIME, GF30_SENSORS, TOP_SENSOR, TOP_INIT, CONST, CONFIG_FLOW, COORDINATOR):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def test_gf30_preflight_runtime_is_persistent_and_read_only() -> None:
    source = PREFLIGHT_RUNTIME.read_text(encoding="utf-8")
    assert 'STORAGE_KEY = "brewassistant_gf30_preflight_runtime"' in source
    assert "MAX_OBSERVATIONS = 200" in source
    assert "async_save_gf30_preflight_runtime" in source
    assert "record_gf30_manual_reference" in source
    assert "async_call(" not in source


def test_gf30_manual_services_are_registered_without_hardware_writes() -> None:
    init_source = TOP_INIT.read_text(encoding="utf-8")
    services_source = SERVICES.read_text(encoding="utf-8")
    assert 'SERVICE_GF30_RECORD_MANUAL_TEMPERATURE = "gf30_record_manual_temperature"' in init_source
    assert 'SERVICE_GF30_CLEAR_PREFLIGHT = "gf30_clear_preflight"' in init_source
    assert "record_gf30_manual_reference(" in init_source
    assert "async_save_gf30_preflight_runtime(hass)" in init_source
    assert "gf30_record_manual_temperature:" in services_source
    assert "gf30_clear_preflight:" in services_source


def test_gf30_read_only_sensors_are_registered_in_main_sensor_platform() -> None:
    source = TOP_SENSOR.read_text(encoding="utf-8")
    gf30_source = GF30_SENSORS.read_text(encoding="utf-8")
    assert "create_grainfather_fermenter_sensors" in source
    assert "+ create_grainfather_fermenter_sensors(coordinator)" in source
    assert 'key="gf30_backend_status"' in gf30_source
    assert 'key="gf30_preflight_status"' in gf30_source
    assert 'key="gf30_dual_sensor_status"' in gf30_source
    assert 'key="gf30_safe_point"' in gf30_source


def test_dual_sensor_safe_point_requires_fresh_agreeing_pair() -> None:
    module = _load_thermal_module()
    now = datetime(2026, 9, 24, 20, 0, tzinfo=timezone.utc)

    snapshot = module.build_dual_sensor_snapshot(
        pill_temperature_c=18.2,
        internal_temperature_c=18.0,
        pill_observed_at=now - timedelta(minutes=2),
        internal_observed_at=now - timedelta(minutes=4),
        now=now,
    )

    assert snapshot["status"] == "dual_sensor_agree"
    assert snapshot["redundancy_available"] is True
    assert snapshot["safe_point"] == "dual_fresh_agree"
    assert snapshot["source_selection"] == "no_automatic_winner"
    assert snapshot["control_allowed"] is False


def test_dual_sensor_disagreement_never_selects_a_winner() -> None:
    module = _load_thermal_module()
    now = datetime(2026, 9, 24, 20, 0, tzinfo=timezone.utc)

    snapshot = module.build_dual_sensor_snapshot(
        pill_temperature_c=19.0,
        internal_temperature_c=18.0,
        pill_observed_at=now,
        internal_observed_at=now,
        now=now,
    )

    assert snapshot["status"] == "dual_sensor_disagree"
    assert snapshot["safe_point"] == "degraded_or_review_required"
    assert snapshot["source_selection"] == "no_automatic_winner"


def test_preflight_learning_calculates_passive_cooling_rate() -> None:
    module = _load_learning_module()
    base = datetime(2026, 9, 24, 18, 0, tzinfo=timezone.utc)

    records = [
        {
            "manual_temperature_c": 20.0,
            "manual_observed_at": base.isoformat(),
            "pill_temperature_c": 20.1,
            "pill_observed_at": base.isoformat(),
            "temperature_delta_c": 0.1,
            "absolute_temperature_delta_c": 0.1,
            "learning_sample_eligible": True,
            "phase": "cooling",
        },
        {
            "manual_temperature_c": 19.0,
            "manual_observed_at": (base + timedelta(minutes=30)).isoformat(),
            "pill_temperature_c": 19.1,
            "pill_observed_at": (base + timedelta(minutes=30)).isoformat(),
            "temperature_delta_c": 0.1,
            "absolute_temperature_delta_c": 0.1,
            "learning_sample_eligible": True,
            "phase": "cooling",
        },
        {
            "manual_temperature_c": 18.0,
            "manual_observed_at": (base + timedelta(hours=1)).isoformat(),
            "pill_temperature_c": 18.1,
            "pill_observed_at": (base + timedelta(hours=1)).isoformat(),
            "temperature_delta_c": 0.1,
            "absolute_temperature_delta_c": 0.1,
            "learning_sample_eligible": True,
            "phase": "cooling",
        },
    ]

    summary = module.summarize_preflight_records(records)

    assert summary["eligible_pair_count"] == 3
    assert summary["rate_sample_count"] == 2
    assert summary["latest_pill_rate_c_per_hour"] == -2.0
    assert summary["mean_cooling_rate_c_per_hour"] == -2.0
    assert summary["automatic_sensor_correction"] is False
    assert summary["automatic_control"] is False



def test_coolant_monitor_requires_fresh_coolant_before_learning() -> None:
    module = _load_coolant_module()
    now = datetime(2026, 9, 24, 20, 0, tzinfo=timezone.utc)

    snapshot = module.build_coolant_monitor_snapshot(
        coolant_temperature_c=5.0,
        coolant_observed_at=now - timedelta(minutes=6),
        freezer_air_temperature_c=-2.0,
        freezer_air_observed_at=now,
        thermostat_state="cool",
        thermostat_target_c=4.0,
        thermostat_hvac_action="cooling",
        now=now,
    )

    assert snapshot["status"] == "awaiting_fresh_coolant"
    assert snapshot["learning_ready"] is False
    assert snapshot["control_allowed"] is False
    assert snapshot["direct_freezer_switching"] is False


def test_coolant_monitor_keeps_generic_thermostat_as_freezer_owner() -> None:
    module = _load_coolant_module()
    now = datetime(2026, 9, 24, 20, 0, tzinfo=timezone.utc)

    snapshot = module.build_coolant_monitor_snapshot(
        coolant_temperature_c=4.5,
        coolant_observed_at=now,
        freezer_air_temperature_c=-1.0,
        freezer_air_observed_at=now,
        thermostat_state="cool",
        thermostat_target_c=4.0,
        thermostat_hvac_action="idle",
        now=now,
    )

    assert snapshot["status"] == "monitor_ready"
    assert snapshot["thermostat"]["expected_owner"] == "home_assistant_generic_thermostat"
    assert snapshot["safe_setpoint_known"] is False
    assert snapshot["automatic_setpoint_changes"] is False



def test_gf30_coolant_entities_are_optional_config_mappings() -> None:
    const_source = CONST.read_text(encoding="utf-8")
    config_source = CONFIG_FLOW.read_text(encoding="utf-8")
    coordinator_source = COORDINATOR.read_text(encoding="utf-8")
    sensor_source = GF30_SENSORS.read_text(encoding="utf-8")

    for name in (
        "CONF_GF30_COOLANT_TEMP_ENTITY",
        "CONF_GF30_FREEZER_AIR_TEMP_ENTITY",
        "CONF_GF30_COOLANT_THERMOSTAT_ENTITY",
    ):
        assert name in const_source
        assert name in config_source
        assert name in coordinator_source
        assert name in sensor_source

    assert 'DEFAULT_GF30_COOLANT_TEMP_ENTITY = ""' in const_source
    assert 'DEFAULT_GF30_FREEZER_AIR_TEMP_ENTITY = ""' in const_source
    assert 'DEFAULT_GF30_COOLANT_THERMOSTAT_ENTITY = ""' in const_source


def test_gf30_coolant_sensors_remain_read_only_and_thermostat_owned() -> None:
    sensor_source = GF30_SENSORS.read_text(encoding="utf-8")
    coolant_source = COOLANT.read_text(encoding="utf-8")

    assert 'key="gf30_coolant_status"' in sensor_source
    assert 'key="gf30_coolant_temperature"' in sensor_source
    assert 'key="gf30_freezer_air_temperature"' in sensor_source
    assert "build_coolant_monitor_snapshot" in sensor_source
    assert '"expected_owner": "home_assistant_generic_thermostat"' in coolant_source
    assert '"direct_freezer_switching": False' in coolant_source
    assert "async_call(" not in coolant_source


def test_gf30_dual_sensor_prefers_upstream_last_heard_for_freshness() -> None:
    sensor_source = GF30_SENSORS.read_text(encoding="utf-8")

    assert 'last_heard = selected_device.get("last_heard")' in sensor_source
    assert "dt_util.parse_datetime" in sensor_source
    assert "internal_observed_at=internal_observed_at" in sensor_source


def test_gf30_manual_service_refreshes_diagnostics_without_actuator_calls() -> None:
    init_source = TOP_INIT.read_text(encoding="utf-8")

    assert "async def _refresh_gf30_sensors()" in init_source
    assert "await _refresh_gf30_sensors()" in init_source
    assert "sensor.brewassistant_gf30_coolant_status" in init_source
    assert "sensor.brewassistant_gf30_safe_point" in init_source
