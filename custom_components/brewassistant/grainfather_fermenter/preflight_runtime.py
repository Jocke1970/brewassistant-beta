"""Persistent read-only GF30 thermal preflight runtime.

The runtime stores manual reference observations together with the RAPT Pill
reading that was visible in Home Assistant when the observation was recorded.
It never controls the GF30, pump, freezer or coolant thermostat.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from ..configured_entities import configured_entity
from ..const import CONF_LIQUID_TEMP_ENTITY, DEFAULT_LIQUID_TEMP_ENTITY
from .learning import summarize_preflight_records
from .thermal import build_manual_preflight_snapshot

DATA_KEY = "gf30_preflight_runtime"
STORE_DATA_KEY = "gf30_preflight_runtime_store"
STORAGE_KEY = "brewassistant_gf30_preflight_runtime"
STORAGE_VERSION = 1
MAX_OBSERVATIONS = 200
INVALID_STATES = {"unknown", "unavailable", "none", ""}


@dataclass(slots=True)
class GF30PreflightRecord:
    """One manual-reference observation and its paired Pill snapshot."""

    manual_temperature_c: float
    manual_observed_at: datetime
    pill_temperature_c: float | None
    pill_observed_at: datetime | None
    pill_entity: str
    status: str
    temperature_delta_c: float | None
    absolute_temperature_delta_c: float | None
    within_tolerance: bool | None
    learning_sample_eligible: bool
    phase: str = "unspecified"
    note: str = ""
    recorded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(slots=True)
class GF30PreflightRuntime:
    """Persisted GF30 preflight state."""

    observations: list[GF30PreflightRecord] = field(default_factory=list)


def _as_datetime(value: Any, *, fallback_now: bool = False) -> datetime | None:
    """Normalize a datetime-like input to UTC."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    if value is None or str(value).strip().lower() in INVALID_STATES:
        return datetime.now(timezone.utc) if fallback_now else None

    parsed = dt_util.parse_datetime(str(value))
    if parsed is not None:
        return dt_util.as_utc(parsed)

    return datetime.now(timezone.utc) if fallback_now else None


def _as_float(value: Any) -> float | None:
    """Parse a finite-ish numeric Home Assistant state without fallback."""
    if value is None or str(value).strip().lower() in INVALID_STATES:
        return None
    try:
        parsed = float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None
    if parsed != parsed or parsed in {float("inf"), float("-inf")}:
        return None
    return parsed


def _record_to_store(record: GF30PreflightRecord) -> dict[str, Any]:
    """Serialize one record for Home Assistant storage."""
    payload = asdict(record)
    payload["manual_observed_at"] = record.manual_observed_at.isoformat()
    payload["pill_observed_at"] = (
        record.pill_observed_at.isoformat() if record.pill_observed_at is not None else None
    )
    payload["recorded_at"] = record.recorded_at.isoformat()
    return payload


def _record_from_store(payload: Any) -> GF30PreflightRecord | None:
    """Deserialize one persisted record, dropping malformed entries."""
    if not isinstance(payload, dict):
        return None

    manual_temperature_c = _as_float(payload.get("manual_temperature_c"))
    manual_observed_at = _as_datetime(payload.get("manual_observed_at"))
    if manual_temperature_c is None or manual_observed_at is None:
        return None

    recorded_at = _as_datetime(payload.get("recorded_at")) or manual_observed_at
    return GF30PreflightRecord(
        manual_temperature_c=manual_temperature_c,
        manual_observed_at=manual_observed_at,
        pill_temperature_c=_as_float(payload.get("pill_temperature_c")),
        pill_observed_at=_as_datetime(payload.get("pill_observed_at")),
        pill_entity=str(payload.get("pill_entity") or ""),
        status=str(payload.get("status") or "unknown"),
        temperature_delta_c=_as_float(payload.get("temperature_delta_c")),
        absolute_temperature_delta_c=_as_float(
            payload.get("absolute_temperature_delta_c")
        ),
        within_tolerance=(
            payload.get("within_tolerance")
            if isinstance(payload.get("within_tolerance"), bool)
            else None
        ),
        learning_sample_eligible=bool(payload.get("learning_sample_eligible", False)),
        phase=str(payload.get("phase") or "unspecified"),
        note=str(payload.get("note") or ""),
        recorded_at=recorded_at,
    )


def _store(hass: HomeAssistant) -> Store:
    """Return the preflight Store instance."""
    data = hass.data.setdefault("brewassistant", {})
    store = data.get(STORE_DATA_KEY)
    if not isinstance(store, Store):
        store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        data[STORE_DATA_KEY] = store
    return store


def get_gf30_preflight_runtime(hass: HomeAssistant) -> GF30PreflightRuntime:
    """Return the in-memory preflight runtime."""
    data = hass.data.setdefault("brewassistant", {})
    runtime = data.get(DATA_KEY)
    if not isinstance(runtime, GF30PreflightRuntime):
        runtime = GF30PreflightRuntime()
        data[DATA_KEY] = runtime
    return runtime


async def async_load_gf30_preflight_runtime(
    hass: HomeAssistant,
) -> GF30PreflightRuntime:
    """Load persisted preflight observations."""
    payload = await _store(hass).async_load()
    observations: list[GF30PreflightRecord] = []

    if isinstance(payload, dict):
        raw_observations = payload.get("observations")
        if isinstance(raw_observations, list):
            for raw in raw_observations[-MAX_OBSERVATIONS:]:
                record = _record_from_store(raw)
                if record is not None:
                    observations.append(record)

    runtime = GF30PreflightRuntime(observations=observations)
    hass.data.setdefault("brewassistant", {})[DATA_KEY] = runtime
    return runtime


async def async_save_gf30_preflight_runtime(hass: HomeAssistant) -> None:
    """Persist current preflight observations."""
    runtime = get_gf30_preflight_runtime(hass)
    await _store(hass).async_save(
        {
            "observations": [
                _record_to_store(record)
                for record in runtime.observations[-MAX_OBSERVATIONS:]
            ]
        }
    )


def _pill_observation(
    hass: HomeAssistant,
    pill_entity: str,
) -> tuple[float | None, datetime | None]:
    """Return current Pill temperature and HA last-updated timestamp."""
    state = hass.states.get(pill_entity)
    if state is None:
        return None, None

    value = _as_float(state.state)
    observed_at = state.last_updated if value is not None else None
    if observed_at is not None:
        observed_at = dt_util.as_utc(observed_at)
    return value, observed_at


def record_gf30_manual_reference(
    hass: HomeAssistant,
    *,
    temperature_c: float,
    observed_at: Any = None,
    note: str = "",
    phase: str = "unspecified",
    pill_entity: str | None = None,
) -> GF30PreflightRecord:
    """Record a manual GF30 reference and pair it with the current Pill state."""
    now = datetime.now(timezone.utc)
    manual_temperature = _as_float(temperature_c)
    if manual_temperature is None:
        raise ValueError("temperature_c must be numeric")

    manual_at = _as_datetime(observed_at, fallback_now=True)
    if manual_at is None:
        manual_at = now

    resolved_pill_entity = pill_entity or configured_entity(
        hass,
        CONF_LIQUID_TEMP_ENTITY,
        DEFAULT_LIQUID_TEMP_ENTITY,
    )
    pill_temperature, pill_at = _pill_observation(hass, resolved_pill_entity)

    snapshot = build_manual_preflight_snapshot(
        pill_temperature_c=pill_temperature,
        manual_temperature_c=manual_temperature,
        pill_observed_at=pill_at,
        manual_observed_at=manual_at,
        now=now,
    )

    record = GF30PreflightRecord(
        manual_temperature_c=manual_temperature,
        manual_observed_at=manual_at,
        pill_temperature_c=pill_temperature,
        pill_observed_at=pill_at,
        pill_entity=resolved_pill_entity,
        status=str(snapshot["status"]),
        temperature_delta_c=snapshot.get("temperature_delta_c"),
        absolute_temperature_delta_c=snapshot.get("absolute_temperature_delta_c"),
        within_tolerance=snapshot.get("within_tolerance"),
        learning_sample_eligible=bool(snapshot.get("learning_sample_eligible")),
        phase=str(phase or "unspecified").strip().lower() or "unspecified",
        note=str(note or ""),
        recorded_at=now,
    )

    runtime = get_gf30_preflight_runtime(hass)
    runtime.observations.append(record)
    if len(runtime.observations) > MAX_OBSERVATIONS:
        runtime.observations[:] = runtime.observations[-MAX_OBSERVATIONS:]
    return record


def clear_gf30_preflight_runtime(hass: HomeAssistant) -> GF30PreflightRuntime:
    """Clear all GF30 preflight observations."""
    runtime = GF30PreflightRuntime()
    hass.data.setdefault("brewassistant", {})[DATA_KEY] = runtime
    return runtime


def _record_dict(record: GF30PreflightRecord) -> dict[str, Any]:
    """Return a JSON/attribute-friendly record representation."""
    return {
        "manual_temperature_c": record.manual_temperature_c,
        "manual_observed_at": record.manual_observed_at.isoformat(),
        "pill_temperature_c": record.pill_temperature_c,
        "pill_observed_at": (
            record.pill_observed_at.isoformat()
            if record.pill_observed_at is not None
            else None
        ),
        "pill_entity": record.pill_entity,
        "status": record.status,
        "temperature_delta_c": record.temperature_delta_c,
        "absolute_temperature_delta_c": record.absolute_temperature_delta_c,
        "within_tolerance": record.within_tolerance,
        "learning_sample_eligible": record.learning_sample_eligible,
        "phase": record.phase,
        "note": record.note,
        "recorded_at": record.recorded_at.isoformat(),
    }


def build_gf30_preflight_runtime_snapshot(
    hass: HomeAssistant,
    *,
    pill_entity: str | None = None,
) -> dict[str, Any]:
    """Build current read-only preflight diagnostics and history summary."""
    runtime = get_gf30_preflight_runtime(hass)
    resolved_pill_entity = pill_entity or configured_entity(
        hass,
        CONF_LIQUID_TEMP_ENTITY,
        DEFAULT_LIQUID_TEMP_ENTITY,
    )
    pill_temperature, pill_at = _pill_observation(hass, resolved_pill_entity)
    latest = runtime.observations[-1] if runtime.observations else None
    now = datetime.now(timezone.utc)

    current = build_manual_preflight_snapshot(
        pill_temperature_c=pill_temperature,
        manual_temperature_c=(
            latest.manual_temperature_c if latest is not None else None
        ),
        pill_observed_at=pill_at,
        manual_observed_at=(
            latest.manual_observed_at if latest is not None else None
        ),
        now=now,
    )

    eligible = [
        record
        for record in runtime.observations
        if record.learning_sample_eligible
        and record.temperature_delta_c is not None
        and record.absolute_temperature_delta_c is not None
    ]
    mean_delta = (
        round(
            sum(float(record.temperature_delta_c) for record in eligible)
            / len(eligible),
            3,
        )
        if eligible
        else None
    )
    mean_absolute_delta = (
        round(
            sum(float(record.absolute_temperature_delta_c) for record in eligible)
            / len(eligible),
            3,
        )
        if eligible
        else None
    )
    max_absolute_delta = (
        round(
            max(float(record.absolute_temperature_delta_c) for record in eligible),
            3,
        )
        if eligible
        else None
    )

    record_payloads = [_record_dict(record) for record in runtime.observations]
    learning = summarize_preflight_records(record_payloads)

    return {
        **current,
        "pill_entity": resolved_pill_entity,
        "observation_count": len(runtime.observations),
        "eligible_sample_count": len(eligible),
        "mean_temperature_delta_c": mean_delta,
        "mean_absolute_temperature_delta_c": mean_absolute_delta,
        "max_absolute_temperature_delta_c": max_absolute_delta,
        "learning": learning,
        "learning_confidence": learning.get("confidence"),
        "latest_pill_rate_c_per_hour": learning.get("latest_pill_rate_c_per_hour"),
        "mean_cooling_rate_c_per_hour": learning.get("mean_cooling_rate_c_per_hour"),
        "mean_warming_rate_c_per_hour": learning.get("mean_warming_rate_c_per_hour"),
        "latest_record": _record_dict(latest) if latest is not None else None,
        "recent_records": [
            _record_dict(record) for record in runtime.observations[-10:]
        ],
        "persistence": "home_assistant_store",
        "history_limit": MAX_OBSERVATIONS,
        "control_allowed": False,
    }
