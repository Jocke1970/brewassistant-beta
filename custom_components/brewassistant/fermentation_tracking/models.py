"""Data models and constants for fermentation tracking."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

SOURCE_MANUAL = "manual"
SOURCE_AUTOMATIC = "automatic"
SOURCE_TYPES = {SOURCE_MANUAL, SOURCE_AUTOMATIC}

SOURCE_MODE_MANUAL = "manual"
SOURCE_MODE_AUTOMATIC = "automatic"
SOURCE_MODE_HYBRID = "hybrid"
SOURCE_MODES = {SOURCE_MODE_MANUAL, SOURCE_MODE_AUTOMATIC, SOURCE_MODE_HYBRID}

METRIC_GRAVITY = "gravity"
METRIC_TEMPERATURE = "temperature"
METRICS = {METRIC_GRAVITY, METRIC_TEMPERATURE}

INSTRUMENT_REFRACTOMETER = "refractometer"
INSTRUMENT_HYDROMETER = "hydrometer"
INSTRUMENT_MANUAL = "manual"
INSTRUMENT_SENSOR = "sensor"
GRAVITY_INSTRUMENTS = {
    INSTRUMENT_REFRACTOMETER,
    INSTRUMENT_HYDROMETER,
    INSTRUMENT_MANUAL,
    INSTRUMENT_SENSOR,
}

UNIT_BRIX = "brix"
UNIT_SG = "sg"
GRAVITY_UNITS = {UNIT_BRIX, UNIT_SG}

DEFAULT_WCF = 1.04
DEFAULT_STABLE_HOURS = 48.0
DEFAULT_STABILITY_TOLERANCE = 0.001
DEFAULT_FG_TOLERANCE = 0.002
MAX_OBSERVATIONS = 1000


@dataclass(slots=True)
class FermentationObservation:
    """One normalized fermentation observation."""

    metric: str
    observed_at: datetime
    source_type: str
    source: str
    raw_value: float
    raw_unit: str
    normalized_value: float
    normalized_unit: str
    measurement_method: str
    source_entity: str | None = None
    note: str | None = None
    wort_correction_factor: float | None = None
    calculation_input_brix: float | None = None


@dataclass(slots=True)
class FermentationRuntime:
    """Mutable recipe-independent fermentation tracking state."""

    active: bool = False
    recipe_name: str = ""
    original_gravity: float | None = None
    target_final_gravity: float | None = None
    temp_rise_trigger_sg: float | None = None
    primary_temperature_c: float | None = None
    temp_rise_temperature_c: float | None = None
    stable_hours: float = DEFAULT_STABLE_HOURS
    stability_tolerance_sg: float = DEFAULT_STABILITY_TOLERANCE
    fg_tolerance_sg: float = DEFAULT_FG_TOLERANCE
    wort_correction_factor: float = DEFAULT_WCF
    gravity_source_mode: str = SOURCE_MODE_HYBRID
    temperature_source_mode: str = SOURCE_MODE_HYBRID
    started_at: datetime | None = None
    updated_at: datetime | None = None
    observations: list[FermentationObservation] = field(default_factory=list)
