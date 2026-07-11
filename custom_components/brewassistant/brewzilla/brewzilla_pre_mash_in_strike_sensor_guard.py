"""Pre-mash-in strike-water sensor selection for BrewZilla.

When a dedicated mash/BLE probe is available during heat-strike, it is the best
operator-facing measurement for the water the grain will actually meet.  The
BrewZilla internal/kettle sensor is still useful as a readback and safety signal,
but it should not be the primary strike-target readiness sensor when a mash probe
is present.
"""

from __future__ import annotations

from typing import Any

from . import brewzilla_heat_strike_profile as heat_strike
from . import brewzilla_learning as learning

_INSTALLED = False
_BASE_TEMPERATURE_SOURCE_SNAPSHOT = None


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _select_strike_sensor(snapshot: dict[str, Any]) -> tuple[float | None, Any, Any, str]:
    """Prefer mash/BLE probe for strike readiness, fallback to wort/kettle."""
    mash_temperature = _num(snapshot.get("mash_temperature"))
    if mash_temperature is not None:
        return (
            mash_temperature,
            snapshot.get("mash_temperature_entity"),
            snapshot.get("mash_temperature_source"),
            "pre_mash_in_mash_or_wort_temperature",
        )

    wort_temperature = _num(snapshot.get("wort_temperature"))
    if wort_temperature is not None:
        return (
            wort_temperature,
            snapshot.get("wort_temperature_entity"),
            snapshot.get("wort_temperature_source"),
            "pre_mash_in_wort_fallback_temperature",
        )

    return None, None, None, "pre_mash_in_missing_temperature"


def _pre_mash_in_temperature_source_snapshot(hass, stage_kind: str) -> dict[str, Any]:
    """Use mash/BLE as strike sensor before mash-in when available."""
    if not heat_strike._pre_mash_in(hass) or (stage_kind != "ramp" and not heat_strike._latch_active(hass)):
        assert _BASE_TEMPERATURE_SOURCE_SNAPSHOT is not None
        return _BASE_TEMPERATURE_SOURCE_SNAPSHOT(hass, stage_kind)

    snapshot = learning.brewzilla_temperature_snapshot(hass)
    learning_temperature, learning_entity, learning_source, role = _select_strike_sensor(snapshot)

    return {
        "mash_temperature": snapshot.get("mash_temperature"),
        "mash_temperature_entity": snapshot.get("mash_temperature_entity"),
        "mash_temperature_source": snapshot.get("mash_temperature_source"),
        "wort_temperature": snapshot.get("wort_temperature"),
        "wort_temperature_entity": snapshot.get("wort_temperature_entity"),
        "wort_temperature_source": snapshot.get("wort_temperature_source"),
        "temperature_delta_mash_wort": snapshot.get("temperature_delta_mash_wort"),
        "learning_temperature": learning_temperature,
        "learning_temperature_entity": learning_entity,
        "learning_temperature_source": learning_source,
        "learning_temperature_role": role,
        "heat_strike_control_temperature": learning_temperature,
        "heat_strike_control_temperature_entity": learning_entity,
        "heat_strike_control_temperature_source": learning_source,
        "heat_strike_control_temperature_role": role,
        "use_internal_sensor": None,
        "control_device_type": None,
        "control_device_mac_address": None,
    }


def _strike_current_temperature(out: dict[str, Any]) -> float | None:
    """Return the temperature that should be compared to strike target."""
    for key in (
        "heat_strike_control_temperature",
        "advice_learning_temperature",
        "mash_temperature",
        "wort_temperature",
        "current_temperature",
    ):
        value = _num(out.get(key))
        if value is not None:
            return value
    return None


def install_pre_mash_in_strike_sensor_guard() -> None:
    """Install mash-first strike sensor selection after heat-strike profile."""
    global _BASE_TEMPERATURE_SOURCE_SNAPSHOT, _INSTALLED
    if _INSTALLED:
        return

    _BASE_TEMPERATURE_SOURCE_SNAPSHOT = learning._temperature_source_snapshot
    learning._temperature_source_snapshot = _pre_mash_in_temperature_source_snapshot
    heat_strike._pre_mash_in_temperature_source_snapshot = _pre_mash_in_temperature_source_snapshot
    heat_strike._strike_current_temperature = _strike_current_temperature

    _INSTALLED = True
