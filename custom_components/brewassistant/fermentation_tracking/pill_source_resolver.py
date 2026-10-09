"""Read-only atomic Pill source resolver with recovery hysteresis.

Do not connect these preview outputs to actuators or Brewfather without
verified physical measurement timestamps from the owning integrations.
"""
from __future__ import annotations

from datetime import datetime, timezone
import math

SOURCES = {
    "ble": ("sensor.yellow_pill_temperature_2", "sensor.yellow_pill_specific_gravity"),
    "cloud": ("sensor.yellow_pill_temperature", "sensor.yellow_pill_gravity"),
}
MAX_AGE = 1200
RECOVERY_OBSERVATIONS = 2


def _timestamp(state):
    """Prefer an explicit measurement timestamp; never use last_reported."""
    for key in ("measurement_time", "observed_at", "last_measurement", "last_sample"):
        raw = state.attributes.get(key)
        if raw:
            try:
                parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
                if parsed.tzinfo is not None:
                    return parsed, "physical_timestamp_attribute:" + key
            except ValueError:
                pass
    stamp = state.last_updated
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp, "ha_last_updated_proxy"


def _read(hass, entity, lo, hi, now):
    state = hass.states.get(entity)
    result = {"entity": entity, "value": None, "ok": False, "age": None,
              "timestamp": None, "basis": "none", "reason": "missing"}
    if state is None or state.state in ("unavailable", "unknown", ""):
        return result
    try:
        value = float(state.state)
    except (ValueError, TypeError):
        result["reason"] = "invalid_number"
        return result
    if not math.isfinite(value) or not lo <= value <= hi:
        result["reason"] = "outside_bounds"
        return result
    stamp, basis = _timestamp(state)
    age = (now - stamp).total_seconds()
    # A future timestamp is not an authentic measurement.
    ok = -60 <= age <= MAX_AGE
    result.update(value=value, ok=ok, age=round(max(0, age)),
                  timestamp=stamp.isoformat(), basis=basis,
                  reason="candidate" if ok else "stale_or_future")
    return result


def resolve(hass, previous=None, now=None):
    """Select the WHOLE pair; two distinct BLE updates to return from Cloud."""
    now = now or datetime.now(timezone.utc)
    previous = previous or {}
    candidates = {}
    for source, (temp_entity, gravity_entity) in SOURCES.items():
        temp = _read(hass, temp_entity, -5, 45, now)
        gravity = _read(hass, gravity_entity, 0.9, 1.2, now)
        connection = hass.states.get("sensor.yellow_pill_connection")
        disconnected = source == "cloud" and connection is not None and str(connection.state).lower() != "connected"
        valid = bool(temp["ok"] and gravity["ok"] and not disconnected)
        candidates[source] = {
            "temperature": temp, "gravity": gravity, "eligible": valid,
            "reason": "candidate" if valid else "cloud_not_connected" if disconnected else "incomplete_or_stale_pair",
        }

    ble = candidates["ble"]
    cloud = candidates["cloud"]
    signature = [ble["temperature"]["timestamp"], ble["gravity"]["timestamp"]]
    streak = int(previous.get("ble_recovery_streak", 0))
    if not ble["eligible"]:
        streak = 0
    elif signature != previous.get("last_ble_signature"):
        streak = min(RECOVERY_OBSERVATIONS, streak + 1)

    old = previous.get("active_source", "none")
    if old == "ble" and ble["eligible"]:
        selected, reason = "ble", "ble_healthy"
    elif old == "cloud" and cloud["eligible"]:
        if ble["eligible"] and streak >= RECOVERY_OBSERVATIONS:
            selected, reason = "ble", "ble_recovered"
        else:
            selected, reason = "cloud", "cloud_holding_until_ble_recovers"
    elif ble["eligible"]:
        selected, reason = "ble", "ble_preferred"
    elif cloud["eligible"]:
        selected, reason = "cloud", "ble_unavailable_cloud_candidate"
    else:
        selected, reason = "none", "no_eligible_pair"

    pair = candidates.get(selected)
    return {
        "active_source": selected,
        "temperature": pair["temperature"]["value"] if pair else None,
        "gravity": pair["gravity"]["value"] if pair else None,
        "status": "provisional" if pair else "stale_or_unavailable",
        "safe_for_control": False,
        "candidates": candidates,
        "ble_recovery_streak": streak,
        "last_ble_signature": signature if ble["eligible"] else None,
        "switch_reason": reason,
        "freshness_basis": "physical_timestamp_if_available_else_ha_last_updated_proxy",
    }
