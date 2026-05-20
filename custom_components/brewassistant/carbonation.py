"""Read-only carbonation calculations for BrewAssistant."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

CARBONATION_ACTIVE_ENTITY = "input_boolean.brewassistant_carbonation_active"
CARBONATION_STARTED_AT_ENTITY = "input_datetime.brewassistant_carbonation_started_at"
CARBONATION_METHOD_ENTITY = "input_select.brewassistant_carbonation_method"
CARBONATION_TARGET_VOLUMES_ENTITY = "input_number.brewassistant_carbonation_target_volumes"
CARBONATION_TEMPERATURE_ENTITY = "sensor.brewassistant_liquid_temperature"

DEFAULT_METHOD = "Set-and-forget"
DEFAULT_TARGET_VOLUMES = 2.4

INVALID_STATES = {"unknown", "unavailable", "none", ""}


def _state_value(hass: HomeAssistant, entity_id: str) -> str | None:
    """Return a valid state string or None."""
    state = hass.states.get(entity_id)
    if state is None or state.state in INVALID_STATES:
        return None
    return state.state


def _float_state(hass: HomeAssistant, entity_id: str, fallback: float | None = None) -> float | None:
    """Return a float state with fallback."""
    value = _state_value(hass, entity_id)
    if value is None:
        return fallback
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _parse_started_at(raw_state: str | None) -> Any | None:
    """Parse a HA datetime/date state."""
    if raw_state is None:
        return None

    parsed = dt_util.parse_datetime(raw_state)
    if parsed is not None:
        return dt_util.as_utc(parsed)

    parsed_date = dt_util.parse_date(raw_state)
    if parsed_date is not None:
        return dt_util.as_utc(dt_util.start_of_local_day(parsed_date))

    return None


def _pressure_psi_for_volumes(target_volumes: float, temp_c: float) -> float:
    """Estimate equilibrium carbonation pressure in PSI.

    Formula is a common homebrew keg carbonation approximation using beer
    temperature in Fahrenheit and target CO2 volumes.
    """
    temp_f = (temp_c * 9 / 5) + 32
    volumes = target_volumes
    psi = (
        -16.6999
        - (0.0101059 * temp_f)
        + (0.00116512 * temp_f * temp_f)
        + (0.173354 * temp_f * volumes)
        + (4.24267 * volumes)
        - (0.0684226 * volumes * volumes)
    )
    return max(0.0, psi)


def build_carbonation_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    """Build a read-only carbonation snapshot.

    The first implementation is helper-aware but safe if helpers do not exist.
    Missing helpers simply produce an inactive/default snapshot.
    """
    active = _state_value(hass, CARBONATION_ACTIVE_ENTITY) == "on"
    method = _state_value(hass, CARBONATION_METHOD_ENTITY) or DEFAULT_METHOD
    target_volumes = _float_state(
        hass,
        CARBONATION_TARGET_VOLUMES_ENTITY,
        DEFAULT_TARGET_VOLUMES,
    )
    temperature = _float_state(hass, CARBONATION_TEMPERATURE_ENTITY)

    raw_started_at = _state_value(hass, CARBONATION_STARTED_AT_ENTITY)
    started_at = _parse_started_at(raw_started_at)
    age_days = None
    if started_at is not None:
        age_seconds = max(0.0, (dt_util.utcnow() - started_at).total_seconds())
        age_days = round(age_seconds / 86400, 2)

    pressure_psi = None
    pressure_bar = None
    if target_volumes is not None and temperature is not None:
        pressure_psi = round(_pressure_psi_for_volumes(target_volumes, temperature), 1)
        pressure_bar = round(pressure_psi * 0.0689476, 2)

    status = "Inactive"
    ready = False
    if active:
        status = "Carbonating"
        if age_days is not None and age_days >= 7:
            status = "Conditioning"
        if age_days is not None and age_days >= 14:
            status = "Ready to serve"
            ready = True

    temp_text = f"{temperature:.1f} °C" if temperature is not None else "temp unknown"
    volumes_text = f"{target_volumes:.1f} vol" if target_volumes is not None else "vol unknown"
    pressure_text = (
        f"{pressure_bar:.2f} bar / {pressure_psi:.1f} psi"
        if pressure_bar is not None and pressure_psi is not None
        else "pressure unknown"
    )
    age_text = f"day {age_days:.1f}" if age_days is not None else "not started"

    summary = (
        f"{method} · {volumes_text} · {temp_text} · {pressure_text} · {age_text}"
        if active
        else f"Inactive · {method} · {volumes_text} · {temp_text} · {pressure_text}"
    )

    return {
        "active": active,
        "ready": ready,
        "status": status,
        "method": method,
        "target_volumes": round(target_volumes, 2) if target_volumes is not None else None,
        "temperature": round(temperature, 1) if temperature is not None else None,
        "pressure_bar": pressure_bar,
        "pressure_psi": pressure_psi,
        "started_at": started_at.isoformat() if started_at is not None else None,
        "age_days": age_days,
        "summary": summary,
        "helper_active_entity": CARBONATION_ACTIVE_ENTITY,
        "helper_started_at_entity": CARBONATION_STARTED_AT_ENTITY,
        "helper_method_entity": CARBONATION_METHOD_ENTITY,
        "helper_target_volumes_entity": CARBONATION_TARGET_VOLUMES_ENTITY,
        "temperature_entity": CARBONATION_TEMPERATURE_ENTITY,
        "mode": "read_only",
    }
