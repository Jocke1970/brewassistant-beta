"""BrewZilla temperature filter."""

from __future__ import annotations

from typing import Any

from homeassistant.util import dt as dt_util

from . import brewzilla_orchestration as base

_BASE_BUILD = base.build_orchestration_snapshot
_INSTALLED = False
STORE = "brewzilla_temp_filter"
DROP_C = 4.0
WINDOW_S = 180
MAX_AGE_S = 900


def _num(v: Any) -> float | None:
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


def _age(ts: Any) -> int | None:
    parsed = dt_util.parse_datetime(str(ts)) if ts else None
    return None if parsed is None else max(0, int((dt_util.utcnow() - dt_util.as_utc(parsed)).total_seconds()))


def _store(hass) -> dict[str, Any]:
    return hass.data.setdefault("brewassistant", {}).setdefault(STORE, {})


def _hot(s: dict[str, Any]) -> bool:
    return bool(base._runtime_active(str(s.get("brewday_state") or "idle")) and not s.get("completed_runtime") and (s.get("heater_on") or s.get("desired_heater_on") or s.get("heating_needed")))


def _apply_hold_recalc(s: dict[str, Any], temp: float) -> None:
    target = _num(s.get("requested_target"))
    if target is None:
        return
    heat_needed = temp < target - base.TARGET_SYNC_TOLERANCE
    s["heating_needed"] = heat_needed
    if not heat_needed:
        s["desired_heat_utilization"] = 0.0
        s["desired_heater_on"] = False
        s["heater_action_needed"] = False
        s["heater_stop_needed"] = bool(s.get("heater_on"))
        s["heat_utilization_action_needed"] = base._utilization_action_needed(_num(s.get("heat_utilization")), 0.0)


def build_orchestration_snapshot(hass):
    snap = _BASE_BUILD(hass)
    st = _store(hass)
    now = dt_util.utcnow().isoformat()
    raw = _num(snap.get("current_temperature"))
    trusted = _num(st.get("trusted"))
    trusted_age = _age(st.get("trusted_at"))
    filtered = False
    reason = None
    delta = None
    if raw is None:
        filtered = trusted is not None
        reason = "raw_missing" if filtered else None
    elif trusted is not None and trusted_age is not None and trusted_age <= WINDOW_S:
        delta = raw - trusted
        if _hot(snap) and delta <= -DROP_C:
            filtered = True
            reason = "drop_during_heat"
        else:
            trusted = raw
            st.update({"trusted": raw, "trusted_at": now})
    else:
        trusted = raw
        st.update({"trusted": raw, "trusted_at": now})
    st.update({"last_raw": raw, "last_raw_at": now})
    if filtered and trusted is not None:
        snap["raw_current_temperature"] = raw
        snap["current_temperature"] = trusted
        _apply_hold_recalc(snap, trusted)
        snap["control_reason"] = f"Temp sample filtered ({reason}); using trusted {trusted:.2f}°C. {snap.get('control_reason')}"
        snap["rapt_critical_refresh_recommended"] = True
    snap.update({
        "temperature_raw": raw,
        "temperature_trusted": trusted,
        "temperature_trusted_at": st.get("trusted_at"),
        "temperature_filter_active": True,
        "temperature_sample_filtered": filtered,
        "temperature_filter_reason": reason,
        "temperature_filter_delta_c": round(delta, 2) if delta is not None else None,
        "temperature_filter_drop_c": DROP_C,
        "temperature_filter_window_seconds": WINDOW_S,
        "temperature_filter_max_trusted_age_seconds": MAX_AGE_S,
    })
    return snap


def install_temp_filter() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    base.build_orchestration_snapshot = build_orchestration_snapshot
    _INSTALLED = True
