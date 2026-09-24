"""Read-only coolant/freezer monitoring helpers for GF30.

The physical ownership contract is fixed:
- GF30 controller owns beer-temperature regulation and its cooling pump.
- Home Assistant generic_thermostat will own freezer ON/OFF.
- BrewAssistant observes and learns; this module never writes the freezer.
"""

from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite
from typing import Any

DEFAULT_LOCAL_FRESHNESS_SECONDS = 5 * 60
INVALID_STATES = {"unknown", "unavailable", "none", ""}


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _float(value: Any) -> float | None:
    if value is None or str(value).strip().lower() in INVALID_STATES:
        return None
    try:
        parsed = float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None
    if not isfinite(parsed):
        return None
    return parsed


def _temperature_observation(
    *,
    source: str,
    value: Any,
    observed_at: datetime | None,
    now: datetime,
    freshness_seconds: int,
) -> dict[str, Any]:
    temperature_c = _float(value)
    observed = _utc(observed_at)
    age_seconds: float | None = None
    fresh = False

    if observed is not None:
        raw_age = (now - observed).total_seconds()
        if raw_age >= -5:
            age_seconds = max(0.0, raw_age)
            fresh = (
                temperature_c is not None
                and age_seconds <= freshness_seconds
            )

    if temperature_c is None:
        state = "invalid_or_missing"
    elif observed is None:
        state = "timestamp_missing"
    elif age_seconds is None:
        state = "timestamp_in_future"
    elif fresh:
        state = "fresh"
    else:
        state = "stale"

    return {
        "source": source,
        "temperature_c": temperature_c,
        "observed_at": observed.isoformat() if observed is not None else None,
        "age_seconds": round(age_seconds, 1) if age_seconds is not None else None,
        "fresh": fresh,
        "state": state,
    }


def build_coolant_monitor_snapshot(
    *,
    coolant_temperature_c: Any = None,
    coolant_observed_at: datetime | None = None,
    freezer_air_temperature_c: Any = None,
    freezer_air_observed_at: datetime | None = None,
    thermostat_state: str | None = None,
    thermostat_target_c: Any = None,
    thermostat_hvac_action: str | None = None,
    now: datetime | None = None,
    freshness_seconds: int = DEFAULT_LOCAL_FRESHNESS_SECONDS,
) -> dict[str, Any]:
    """Build a normalized read-only coolant/freezer snapshot.

    This function intentionally does not define safe coolant setpoints. Those
    depend on the actual coolant mixture and field validation.
    """
    if freshness_seconds <= 0:
        raise ValueError("freshness_seconds must be > 0")

    current = _utc(now) or datetime.now(timezone.utc)
    coolant = _temperature_observation(
        source="coolant_reservoir",
        value=coolant_temperature_c,
        observed_at=coolant_observed_at,
        now=current,
        freshness_seconds=freshness_seconds,
    )
    freezer_air = _temperature_observation(
        source="freezer_air",
        value=freezer_air_temperature_c,
        observed_at=freezer_air_observed_at,
        now=current,
        freshness_seconds=freshness_seconds,
    )

    target_c = _float(thermostat_target_c)
    air_coolant_delta_c: float | None = None
    if coolant["fresh"] and freezer_air["fresh"]:
        air_coolant_delta_c = (
            float(freezer_air["temperature_c"])
            - float(coolant["temperature_c"])
        )

    if not coolant["fresh"]:
        status = "awaiting_fresh_coolant"
        reason = "Coolant temperature is missing, invalid, future-dated or stale"
    elif freezer_air["fresh"]:
        status = "monitor_ready"
        reason = "Coolant and freezer-air temperatures are fresh"
    else:
        status = "coolant_ready_air_degraded"
        reason = "Coolant temperature is fresh; freezer-air diagnostics are unavailable"

    thermostat_available = (
        thermostat_state is not None
        and str(thermostat_state).strip().lower() not in INVALID_STATES
    )

    return {
        "mode": "gf30_coolant_monitor",
        "control_mode": "read_only",
        "control_allowed": False,
        "status": status,
        "reason": reason,
        "coolant": coolant,
        "freezer_air": freezer_air,
        "freezer_air_minus_coolant_c": (
            round(air_coolant_delta_c, 3)
            if air_coolant_delta_c is not None
            else None
        ),
        "thermostat": {
            "available": thermostat_available,
            "state": thermostat_state,
            "target_temperature_c": target_c,
            "hvac_action": thermostat_hvac_action,
            "expected_owner": "home_assistant_generic_thermostat",
        },
        "learning_ready": bool(coolant["fresh"]),
        "safe_setpoint_known": False,
        "coolant_mixture_verified": False,
        "automatic_setpoint_changes": False,
        "direct_freezer_switching": False,
    }
