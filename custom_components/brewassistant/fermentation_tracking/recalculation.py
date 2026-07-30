"""Recalculate persisted derived fermentation observation values."""

from __future__ import annotations

from .calculations import corrected_refractometer_sg, sg_to_brix
from .models import (
    INSTRUMENT_REFRACTOMETER,
    METRIC_GRAVITY,
    UNIT_BRIX,
    UNIT_SG,
    FermentationRuntime,
)


def recalculate_refractometer_observations(runtime: FermentationRuntime) -> None:
    """Recalculate stored refractometer observations after OG or WCF changes."""
    observations = [
        item
        for item in runtime.observations
        if item.metric == METRIC_GRAVITY
        and item.measurement_method.startswith(f"{INSTRUMENT_REFRACTOMETER}_")
    ]
    if not observations:
        return
    if runtime.original_gravity is None:
        raise ValueError(
            "original_gravity cannot be cleared while refractometer observations exist"
        )

    for observation in observations:
        if observation.raw_unit == UNIT_BRIX:
            brix = observation.raw_value
        elif observation.raw_unit == UNIT_SG:
            brix = sg_to_brix(observation.raw_value)
        else:
            raise ValueError(
                f"unsupported stored refractometer unit: {observation.raw_unit}"
            )
        observation.calculation_input_brix = round(brix, 4)
        observation.wort_correction_factor = runtime.wort_correction_factor
        observation.normalized_value = corrected_refractometer_sg(
            runtime.original_gravity,
            brix,
            runtime.wort_correction_factor,
        )
