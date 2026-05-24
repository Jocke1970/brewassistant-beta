"""Python-owned carbonation runtime and calculations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

DATA_KEY = "carbonation_runtime"
LOCAL_TEMPERATURE_ENTITY = "sensor.kyl_temperatur_4"
FALLBACK_TEMPERATURE_ENTITY = "sensor.brewassistant_liquid_temperature"

DEFAULT_METHOD = "Set-and-forget"
DEFAULT_TARGET_VOLUMES = 2.4
DEFAULT_START_VOLUMES = 0.85
INVALID_STATES = {"unknown", "unavailable", "none", ""}
BAR_TO_PSI = 14.5037738
PSI_TO_BAR = 0.0689476


@dataclass(slots=True)
class CarbonationRuntime:
    """Mutable carbonation runtime state."""

    active: bool = False
    method: str = DEFAULT_METHOD
    target_volumes: float = DEFAULT_TARGET_VOLUMES
    start_volumes: float = DEFAULT_START_VOLUMES
    pressure_bar: float | None = None
    temperature_c: float | None = None
    started_at: datetime | None = None
    updated_at: datetime | None = None


def get_carbonation_runtime(hass: HomeAssistant) -> CarbonationRuntime:
    """Return the Python-owned carbonation runtime."""
    data = hass.data.setdefault("brewassistant", {})
    runtime = data.get(DATA_KEY)
    if not isinstance(runtime, CarbonationRuntime):
        runtime = CarbonationRuntime()
        data[DATA_KEY] = runtime
    return runtime


def reset_carbonation_runtime(hass: HomeAssistant) -> CarbonationRuntime:
    """Reset carbonation runtime to inactive defaults."""
    runtime = CarbonationRuntime()
    hass.data.setdefault("brewassistant", {})[DATA_KEY] = runtime
    return runtime


def _as_float(value: Any, fallback: float | None = None) -> float | None:
    try:
        if value is None or str(value).lower() in INVALID_STATES:
            return fallback
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _as_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return dt_util.as_utc(value)
    if value is None or str(value).lower() in INVALID_STATES:
        return None
    parsed = dt_util.parse_datetime(str(value))
    if parsed is not None:
        return dt_util.as_utc(parsed)
    parsed_date = dt_util.parse_date(str(value))
    if parsed_date is not None:
        return dt_util.as_utc(dt_util.start_of_local_day(parsed_date))
    return None


def _state_value(hass: HomeAssistant, entity_id: str) -> str | None:
    state = hass.states.get(entity_id)
    if state is None or state.state in INVALID_STATES:
        return None
    return state.state


def _float_state(hass: HomeAssistant, entity_id: str) -> float | None:
    return _as_float(_state_value(hass, entity_id))


def _psi_for_volumes(target_volumes: float, temp_c: float) -> float:
    temp_f = (temp_c * 9 / 5) + 32
    v = target_volumes
    psi = -16.6999 - 0.0101059 * temp_f + 0.00116512 * temp_f * temp_f + 0.173354 * temp_f * v + 4.24267 * v - 0.0684226 * v * v
    return max(0.0, psi)


def _volumes_for_psi(pressure_psi: float, temp_c: float) -> float:
    best = 0.0
    best_diff = 9999.0
    for i in range(50, 401):
        candidate = i / 100
        diff = abs(_psi_for_volumes(candidate, temp_c) - pressure_psi)
        if diff < best_diff:
            best_diff = diff
            best = candidate
    return round(best, 2)


def _method_days_to_full(method: str) -> float:
    return {
        "Burst carbonation": 2.0,
        "Set-and-forget": 14.0,
        "Natural carbonation": 21.0,
        "Conditioning": 14.0,
    }.get(method, 14.0)


def update_carbonation_runtime(hass: HomeAssistant, data: dict[str, Any] | None = None) -> CarbonationRuntime:
    """Update carbonation runtime values."""
    runtime = get_carbonation_runtime(hass)
    payload = data or {}

    if payload.get("method"):
        runtime.method = str(payload["method"])

    target = _as_float(payload.get("target_volumes"))
    if target is not None and target > 0:
        runtime.target_volumes = round(target, 2)

    start = _as_float(payload.get("start_volumes"))
    if start is not None and start >= 0:
        runtime.start_volumes = round(start, 2)

    if "pressure_bar" in payload:
        runtime.pressure_bar = _as_float(payload.get("pressure_bar"), runtime.pressure_bar)

    if "temperature_c" in payload:
        runtime.temperature_c = _as_float(payload.get("temperature_c"), runtime.temperature_c)

    if "started_at" in payload:
        parsed = _as_datetime(payload.get("started_at"))
        if parsed is not None:
            runtime.started_at = parsed

    runtime.updated_at = datetime.now(timezone.utc)
    return runtime


def start_carbonation_runtime(hass: HomeAssistant, data: dict[str, Any] | None = None) -> CarbonationRuntime:
    """Start carbonation monitoring."""
    runtime = update_carbonation_runtime(hass, data)
    runtime.active = True
    if runtime.started_at is None:
        runtime.started_at = datetime.now(timezone.utc)
    runtime.updated_at = datetime.now(timezone.utc)
    return runtime


def pause_carbonation_runtime(hass: HomeAssistant) -> CarbonationRuntime:
    """Pause carbonation monitoring without clearing values."""
    runtime = get_carbonation_runtime(hass)
    runtime.active = False
    runtime.updated_at = datetime.now(timezone.utc)
    return runtime


def _resolved_pressure_bar(runtime: CarbonationRuntime) -> tuple[float | None, str | None]:
    if runtime.pressure_bar is not None:
        return runtime.pressure_bar, "python_runtime"
    return None, None


def _resolved_temperature_c(hass: HomeAssistant, runtime: CarbonationRuntime) -> tuple[float | None, str | None]:
    if runtime.temperature_c is not None:
        return runtime.temperature_c, "python_runtime"
    local = _float_state(hass, LOCAL_TEMPERATURE_ENTITY)
    if local is not None:
        return local, LOCAL_TEMPERATURE_ENTITY
    fallback = _float_state(hass, FALLBACK_TEMPERATURE_ENTITY)
    if fallback is not None:
        return fallback, FALLBACK_TEMPERATURE_ENTITY
    return None, None


def build_carbonation_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    """Build a read-only carbonation snapshot."""
    runtime = get_carbonation_runtime(hass)
    pressure_bar, pressure_source = _resolved_pressure_bar(runtime)
    temp_c, temp_source = _resolved_temperature_c(hass, runtime)

    age_days = None
    if runtime.started_at is not None:
        age_seconds = max(0.0, (dt_util.utcnow() - runtime.started_at).total_seconds())
        age_days = round(age_seconds / 86400, 2)

    rec_psi = round(_psi_for_volumes(runtime.target_volumes, temp_c), 1) if temp_c is not None else None
    rec_bar = round(rec_psi * PSI_TO_BAR, 2) if rec_psi is not None else None
    actual_psi = round(pressure_bar * BAR_TO_PSI, 1) if pressure_bar is not None else None
    equilibrium = _volumes_for_psi(actual_psi, temp_c) if actual_psi is not None and temp_c is not None else None

    estimated = None
    progress_percent = None
    if equilibrium is not None:
        progress = min(1.0, (age_days or 0) / _method_days_to_full(runtime.method))
        estimated = round(runtime.start_volumes + ((equilibrium - runtime.start_volumes) * progress), 2)
        progress_percent = round(min(100.0, (estimated / runtime.target_volumes) * 100), 1)
    elif runtime.active:
        estimated = runtime.start_volumes
        progress_percent = round(min(100.0, (estimated / runtime.target_volumes) * 100), 1)

    status = "Inactive"
    ready = False
    if runtime.active:
        status = "Carbonating"
        if progress_percent is not None and progress_percent >= 75:
            status = "Conditioning"
        if progress_percent is not None and progress_percent >= 95:
            status = "Ready to serve"
            ready = True

    if runtime.active and pressure_bar is not None and temp_c is not None and estimated is not None and progress_percent is not None:
        summary = f"{runtime.method} · {pressure_bar:.2f} bar · {temp_c:.1f} °C · Estimated {estimated:.2f} / {runtime.target_volumes:.2f} vol · {progress_percent:.0f}%"
    elif runtime.active and temp_c is not None and estimated is not None and progress_percent is not None:
        summary = f"{runtime.method} · {temp_c:.1f} °C · Estimated {estimated:.2f} / {runtime.target_volumes:.2f} vol · {progress_percent:.0f}% · set pressure to estimate equilibrium"
    elif runtime.active:
        summary = f"Carbonating · {runtime.method} · waiting for temperature"
    else:
        summary = f"Inactive · {runtime.method}"

    return {
        "active": runtime.active,
        "ready": ready,
        "status": status,
        "method": runtime.method,
        "target_volumes": round(runtime.target_volumes, 2),
        "start_volumes": round(runtime.start_volumes, 2),
        "temperature": round(temp_c, 1) if temp_c is not None else None,
        "recommended_pressure_bar": rec_bar,
        "recommended_pressure_psi": rec_psi,
        "actual_pressure_bar": pressure_bar,
        "actual_pressure_psi": actual_psi,
        "equilibrium_volumes": equilibrium,
        "estimated_volumes": estimated,
        "progress_percent": progress_percent,
        "started_at": runtime.started_at.isoformat() if runtime.started_at is not None else None,
        "updated_at": runtime.updated_at.isoformat() if runtime.updated_at is not None else None,
        "age_days": age_days,
        "summary": summary,
        "source": "python_runtime",
        "pressure_source": pressure_source,
        "temperature_source": temp_source,
        "local_temperature_entity": LOCAL_TEMPERATURE_ENTITY,
        "fallback_temperature_entity": FALLBACK_TEMPERATURE_ENTITY,
        "mode": "read_only",
    }
