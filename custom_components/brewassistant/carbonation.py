"""Read-only carbonation calculations for BrewAssistant."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

CARBONATION_ACTIVE_ENTITY = "input_boolean.brewassistant_carbonation_active"
CARBONATION_STARTED_AT_ENTITY = "input_datetime.brewassistant_carbonation_started_at"
CARBONATION_METHOD_ENTITY = "input_select.brewassistant_carbonation_method"
CARBONATION_TARGET_VOLUMES_ENTITY = "input_number.brewassistant_carbonation_target_volumes"
CARBONATION_PRESSURE_BAR_ENTITY = "input_number.brewassistant_carbonation_pressure_bar"
CARBONATION_TEMPERATURE_ENTITY = "sensor.brewassistant_liquid_temperature"

DEFAULT_METHOD = "Set-and-forget"
DEFAULT_TARGET_VOLUMES = 2.4
DEFAULT_START_VOLUMES = 0.85

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
    """Estimate equilibrium carbonation pressure in PSI."""
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


def _volumes_for_pressure_psi(pressure_psi: float, temp_c: float) -> float:
    """Approximate equilibrium CO2 volumes from pressure + temp."""
    best_volumes = 0.0
    best_diff = 9999.0

    for i in range(50, 401):
        volumes = i / 100
        estimated_psi = _pressure_psi_for_volumes(volumes, temp_c)
        diff = abs(estimated_psi - pressure_psi)
        if diff < best_diff:
            best_diff = diff
            best_volumes = volumes

    return round(best_volumes, 2)


def _method_days_to_full(method: str) -> float:
    method_days = {
        "Burst carbonation": 2.0,
        "Set-and-forget": 14.0,
        "Natural carbonation": 21.0,
        "Conditioning": 14.0,
    }
    return method_days.get(method, 14.0)


def build_carbonation_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    """Build a read-only carbonation snapshot."""
    active = _state_value(hass, CARBONATION_ACTIVE_ENTITY) == "on"
    method = _state_value(hass, CARBONATION_METHOD_ENTITY) or DEFAULT_METHOD

    target_volumes = _float_state(
        hass,
        CARBONATION_TARGET_VOLUMES_ENTITY,
        DEFAULT_TARGET_VOLUMES,
    )

    actual_pressure_bar = _float_state(
        hass,
        CARBONATION_PRESSURE_BAR_ENTITY,
    )

    temperature = _float_state(hass, CARBONATION_TEMPERATURE_ENTITY)

    raw_started_at = _state_value(hass, CARBONATION_STARTED_AT_ENTITY)
    started_at = _parse_started_at(raw_started_at)

    age_days = None
    if started_at is not None:
        age_seconds = max(0.0, (dt_util.utcnow() - started_at).total_seconds())
        age_days = round(age_seconds / 86400, 2)

    recommended_pressure_psi = None
    recommended_pressure_bar = None

    if target_volumes is not None and temperature is not None:
        recommended_pressure_psi = round(
            _pressure_psi_for_volumes(target_volumes, temperature),
            1,
        )
        recommended_pressure_bar = round(
            recommended_pressure_psi * 0.0689476,
            2,
        )

    actual_pressure_psi = None
    equilibrium_volumes = None

    if actual_pressure_bar is not None:
        actual_pressure_psi = round(actual_pressure_bar / 0.0689476, 1)

    if actual_pressure_psi is not None and temperature is not None:
        equilibrium_volumes = _volumes_for_pressure_psi(
            actual_pressure_psi,
            temperature,
        )

    estimated_volumes = None
    progress_percent = None

    if equilibrium_volumes is not None:
        progress = 0.0
        if age_days is not None:
            progress = min(1.0, age_days / _method_days_to_full(method))

        estimated_volumes = round(
            DEFAULT_START_VOLUMES
            + ((equilibrium_volumes - DEFAULT_START_VOLUMES) * progress),
            2,
        )

        if target_volumes is not None and target_volumes > 0:
            progress_percent = round(
                min(100.0, (estimated_volumes / target_volumes) * 100),
                1,
            )

    status = "Inactive"
    ready = False

    if active:
        status = "Carbonating"
        if progress_percent is not None and progress_percent >= 75:
            status = "Conditioning"
        if progress_percent is not None and progress_percent >= 95:
            status = "Ready to serve"
            ready = True

    summary = (
        f"{method} · {actual_pressure_bar:.2f} bar · "
        f"{temperature:.1f} °C · "
        f"Estimated {estimated_volumes:.2f} / {target_volumes:.2f} vol · "
        f"{progress_percent:.0f}%"
        if active
        and actual_pressure_bar is not None
        and temperature is not None
        and estimated_volumes is not None
        and target_volumes is not None
        and progress_percent is not None
        else f"Inactive · {method}"
    )

    return {
        "active": active,
        "ready": ready,
        "status": status,
        "method": method,
        "target_volumes": round(target_volumes, 2) if target_volumes is not None else None,
        "temperature": round(temperature, 1) if temperature is not None else None,
        "recommended_pressure_bar": recommended_pressure_bar,
        "recommended_pressure_psi": recommended_pressure_psi,
        "actual_pressure_bar": actual_pressure_bar,
        "actual_pressure_psi": actual_pressure_psi,
        "equilibrium_volumes": equilibrium_volumes,
        "estimated_volumes": estimated_volumes,
        "progress_percent": progress_percent,
        "started_at": started_at.isoformat() if started_at is not None else None,
        "age_days": age_days,
        "summary": summary,
        "helper_pressure_entity": CARBONATION_PRESSURE_BAR_ENTITY,
        "mode": "read_only",
    }
