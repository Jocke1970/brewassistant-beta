"""Atomic, read-only Pill source selection preview."""
from datetime import datetime, timezone
import math

SOURCES = {
    "ble": ("sensor.yellow_pill_temperature_2", "sensor.yellow_pill_specific_gravity"),
    "cloud": ("sensor.yellow_pill_temperature", "sensor.yellow_pill_gravity"),
}
MAX_AGE = 1200

def _read(hass, entity, lo, hi, now):
    s = hass.states.get(entity)
    if s is None or s.state in ("unavailable", "unknown"):
        return {"value": None, "ok": False, "age": None}
    try:
        v = float(s.state)
    except (ValueError, TypeError):
        return {"value": None, "ok": False, "age": None}
    if not math.isfinite(v) or not lo <= v <= hi:
        return {"value": None, "ok": False, "age": None}
    updated = s.last_updated
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=timezone.utc)
    age = max(0, (now - updated).total_seconds())
    return {"value": v, "ok": age <= MAX_AGE, "age": round(age), "observed_proxy": updated.isoformat()}

def resolve(hass, now=None):
    """Select a complete pair, never mix integration sources."""
    now = now or datetime.now(timezone.utc)
    candidates = {}
    for source, (temperature_entity, gravity_entity) in SOURCES.items():
        t = _read(hass, temperature_entity, -5, 45, now)
        g = _read(hass, gravity_entity, 0.9, 1.2, now)
        connection = hass.states.get("sensor.yellow_pill_connection")
        disconnected = source == "cloud" and connection is not None and connection.state.lower() == "disconnected"
        candidates[source] = {"temperature": t, "gravity": g, "eligible": t["ok"] and g["ok"] and not disconnected}
    chosen = next((s for s in ("ble", "cloud") if candidates[s]["eligible"]), None)
    return {"active_source": chosen or "none", "temperature": candidates[chosen]["temperature"]["value"] if chosen else None,
            "gravity": candidates[chosen]["gravity"]["value"] if chosen else None,
            "status": "provisional" if chosen else "stale_or_unavailable",
            "safe_for_control": False, "candidates": candidates,
            "freshness_basis": "HA last_updated only; actual physical measurement not verified"}
