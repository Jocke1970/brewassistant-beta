"""Pure fermentation tracking calculations."""

from __future__ import annotations

from .models import DEFAULT_WCF


def valid_sg(value: float | None) -> bool:
    """Return whether value is a plausible specific gravity."""
    return value is not None and 0.900 <= value <= 1.200


def valid_brix(value: float | None) -> bool:
    """Return whether value is a plausible Brix reading."""
    return value is not None and 0.0 <= value <= 40.0


def valid_temperature(value: float | None) -> bool:
    """Return whether value is a plausible fermentation temperature."""
    return value is not None and -5.0 <= value <= 50.0


def sg_to_brix(sg: float) -> float:
    """Convert an SG scale reading to equivalent degrees Brix."""
    if not valid_sg(sg):
        raise ValueError("SG must be between 0.900 and 1.200")
    return 182.4601 * sg**3 - 775.6821 * sg**2 + 1262.7794 * sg - 669.5622


def corrected_refractometer_sg(
    original_gravity: float,
    brix: float,
    wort_correction_factor: float = DEFAULT_WCF,
) -> float:
    """Correct fermented-beer Brix to SG using Sean Terrill's cubic fit."""
    if not valid_sg(original_gravity):
        raise ValueError("original_gravity must be a valid SG value")
    if not valid_brix(brix):
        raise ValueError("Brix must be between 0 and 40")
    if not 0.5 <= wort_correction_factor <= 1.5:
        raise ValueError("wort_correction_factor must be between 0.5 and 1.5")

    original_brix = sg_to_brix(original_gravity)
    fermented_brix = brix / wort_correction_factor
    corrected = (
        1.0000
        - 0.0044993 * original_brix
        + 0.011774 * fermented_brix
        + 0.00027581 * original_brix**2
        - 0.0012717 * fermented_brix**2
        - 0.0000072800 * original_brix**3
        + 0.000063293 * fermented_brix**3
    )
    return round(corrected, 4)


def fermentation_progress(
    original_gravity: float | None,
    target_final_gravity: float | None,
    current_sg: float | None,
) -> float | None:
    """Return recipe progress from OG toward target FG."""
    if (
        not valid_sg(original_gravity)
        or not valid_sg(target_final_gravity)
        or not valid_sg(current_sg)
        or original_gravity <= target_final_gravity
    ):
        return None
    value = (original_gravity - current_sg) / (original_gravity - target_final_gravity)
    return round(max(0.0, min(100.0, value * 100.0)), 1)


def estimated_abv(original_gravity: float | None, current_sg: float | None) -> float | None:
    """Return a simple estimated ABV from OG and current SG."""
    if not valid_sg(original_gravity) or not valid_sg(current_sg):
        return None
    return round(max(0.0, (original_gravity - current_sg) * 131.25), 2)
