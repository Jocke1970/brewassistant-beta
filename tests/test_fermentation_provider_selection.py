"""Regression contract for fermentation provider selection and arbitration."""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "custom_components/brewassistant"
MODELS = BASE / "fermentation_tracking/models.py"
STORAGE = BASE / "fermentation_tracking/storage.py"
RUNTIME = BASE / "fermentation_tracking/runtime.py"
SNAPSHOT = BASE / "fermentation_tracking/snapshot.py"
TRACKING_SENSOR = BASE / "fermentation_tracking/sensor.py"
SELECT = BASE / "select.py"
CHAMBER = BASE / "fermentation_chamber/supervisor.py"
GF30 = BASE / "grainfather_fermenter/supervised_target.py"


def _load_models():
    spec = importlib.util.spec_from_file_location("brewassistant_provider_models", MODELS)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_provider_ids_and_default_are_stable() -> None:
    models = _load_models()

    assert models.PROVIDER_FERMENTATION_CHAMBER == "fermentation_chamber"
    assert models.PROVIDER_GRAINFATHER_GF30 == "grainfather_gf30"
    assert models.DEFAULT_FERMENTATION_PROVIDER == "fermentation_chamber"
    assert models.FERMENTATION_PROVIDERS == {
        "fermentation_chamber",
        "grainfather_gf30",
    }
    assert models.PROVIDER_LABELS["fermentation_chamber"] == "Temperaturkontrollerat jässkåp"
    assert models.PROVIDER_LABELS["grainfather_gf30"] == "Grainfather GF30"


def test_provider_fields_are_part_of_runtime_model() -> None:
    models = _load_models()
    runtime = models.FermentationRuntime()

    assert runtime.fermentation_provider == "fermentation_chamber"
    assert runtime.fermentation_provider_selected_at is None
    assert runtime.fermentation_provider_selected_by == "default"


def test_provider_storage_persists_and_migrates_to_chamber() -> None:
    source = STORAGE.read_text(encoding="utf-8")

    assert '"fermentation_provider": runtime.fermentation_provider' in source
    assert '"fermentation_provider_selected_at"' in source
    assert '"fermentation_provider_selected_by"' in source
    assert '"migration_default" if "fermentation_provider" not in data' in source
    assert "DEFAULT_FERMENTATION_PROVIDER" in source
    assert "FERMENTATION_PROVIDERS" in source


def test_provider_switch_invalidates_old_pending_action() -> None:
    source = RUNTIME.read_text(encoding="utf-8")

    assert "def set_fermentation_provider(" in source
    assert "_clear_provider_pending_action(hass, previous)" in source
    assert "fermentation_provider_selected_at = datetime.now(timezone.utc)" in source
    assert 'selected_by: str = "operator_ui"' in source
    assert "CHAMBER_SUPERVISOR_SOURCE" in source
    assert "GF30_SUPERVISOR_SOURCE" in source


def test_start_and_reset_clear_stale_provider_pending_actions() -> None:
    source = RUNTIME.read_text(encoding="utf-8")

    assert source.count("_clear_all_provider_pending_actions(hass)") >= 2
    assert "def start_fermentation_runtime" in source
    assert "def reset_fermentation_runtime" in source


def test_snapshot_exposes_stable_provider_identity() -> None:
    source = SNAPSHOT.read_text(encoding="utf-8")

    assert '"fermentation_provider": runtime.fermentation_provider' in source
    assert '"fermentation_provider_label"' in source
    assert '"fermentation_provider_valid"' in source
    assert '"fermentation_provider_selected_at"' in source
    assert '"fermentation_provider_selected_by"' in source


def test_provider_selector_uses_human_labels_but_persists_machine_id() -> None:
    source = SELECT.read_text(encoding="utf-8")

    assert "class BrewAssistantFermentationProviderSelect" in source
    assert 'self._attr_suggested_object_id = f"{DOMAIN}_fermentation_provider"' in source
    assert "FERMENTATION_PROVIDER_BY_LABEL" in source
    assert "set_fermentation_provider(" in source
    assert 'selected_by="operator_ui"' in source
    assert "await async_save_fermentation_runtime" in source


def test_tracking_sensor_exposes_machine_readable_provider() -> None:
    source = TRACKING_SENSOR.read_text(encoding="utf-8")

    assert 'key="fermentation_provider"' in source
    assert 'snapshot_key="fermentation_provider"' in source


def test_chamber_supervisor_is_control_ineligible_when_not_selected() -> None:
    source = CHAMBER.read_text(encoding="utf-8")

    assert "selected_provider = get_runtime(hass).fermentation_provider" in source
    assert "provider_selected = selected_provider == PROVIDER_FERMENTATION_CHAMBER" in source
    assert 'status = "provider_inactive"' in source
    assert "clear_pending_action_from_source(hass, SOURCE)" in source
    assert "provider_selected" in source
    assert "and supervised_enabled" in source


def test_gf30_blocks_proposal_and_confirmed_execution_when_not_selected() -> None:
    source = GF30.read_text(encoding="utf-8")

    assert "selected_provider = get_runtime(hass).fermentation_provider" in source
    assert "provider_selected = selected_provider == PROVIDER_GRAINFATHER_GF30" in source
    assert '"request_result": "provider_not_selected"' in source
    assert '"apply_result": "provider_not_selected"' in source
    assert '"provider_control_allowed": provider_selected' in source


def test_provider_changes_are_syntax_valid() -> None:
    for path in (
        MODELS,
        STORAGE,
        RUNTIME,
        SNAPSHOT,
        TRACKING_SENSOR,
        SELECT,
        CHAMBER,
        GF30,
    ):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
