"""BrewZilla temperature role resolver patch."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from homeassistant.core import HomeAssistant

from . import brewzilla_temperature as t

MIN_DELTA_C = 0.75
_INSTALLED = False


def _age(hass: HomeAssistant, entity_id: str | None) -> int | None:
    state = t._state_obj(hass, entity_id)
    if state is None:
        return None
    stamp = getattr(state, "last_reported", None) or state.last_updated
    if stamp is None:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=UTC)
    return max(0, int(round((datetime.now(UTC) - stamp).total_seconds())))


def _delta(candidate: dict[str, Any], internal: dict[str, Any] | None) -> float | None:
    if internal is None:
        return None
    a = candidate.get("value")
    b = internal.get("value")
    if a is None or b is None:
        return None
    try:
        return round(abs(float(a) - float(b)), 2)
    except (TypeError, ValueError):
        return None


def _distinct(candidate: dict[str, Any], internal: dict[str, Any] | None) -> bool:
    d = _delta(candidate, internal)
    return bool(d is not None and d >= MIN_DELTA_C)


def _reject(candidate: dict[str, Any], *, selected: str, internal: dict[str, Any] | None) -> str | None:
    if not candidate["available"]:
        return "unavailable"
    if candidate.get("ba_value_rejected"):
        return str(candidate.get("ba_reject_reason") or "source_rejected_value")
    if not candidate.get("freshness_ok", True):
        return f"stale_{candidate.get('age_seconds')}s"
    if t._looks_like_control_telemetry(candidate) and candidate.get("source") != "BrewZilla Internal" and not _distinct(candidate, internal):
        return "external_aliasing_internal_temperature"
    return None


def _diag(candidate: dict[str, Any], *, selected: str, internal: dict[str, Any] | None) -> dict[str, Any]:
    reason = _reject(candidate, selected=selected, internal=internal)
    return {
        **{k: v for k, v in candidate.items() if k != "attrs"},
        "internal_delta_c": _delta(candidate, internal),
        "distinct_external_temperature": _distinct(candidate, internal),
        "eligible": reason is None,
        "reject_reason": reason,
    }


def _ok(candidate: dict[str, Any], *, selected: str, internal: dict[str, Any] | None) -> bool:
    return _reject(candidate, selected=selected, internal=internal) is None


def _resolve(selected: str, ble: dict[str, Any], ctl: dict[str, Any], internal: dict[str, Any]):
    if selected == "RAPT BLE Thermometer":
        ordered = [ble, internal]
    elif selected == "BrewZilla Control Device":
        ordered = [ctl, internal]
    elif selected == "BrewZilla Internal":
        ordered = [internal]
    else:
        ordered = [ble, ctl, internal]
    diagnostics = [_diag(c, selected=selected, internal=internal) for c in ordered]
    chosen = next((c for c in ordered if _ok(c, selected=selected, internal=internal)), None)
    return chosen, diagnostics


def _snapshot(hass: HomeAssistant) -> dict[str, Any]:
    selected = t.selected_mash_source(hass)
    ble = t._candidate(hass, t.BREWZILLA_BLE_TEMP_SENSOR, "RAPT BLE Thermometer")
    ctl = t._candidate(hass, t.BREWZILLA_CONTROL_DEVICE_TEMP_SENSOR, "BrewZilla Control Device")
    internal = t._candidate(hass, t.BREWZILLA_INTERNAL_TEMP_SENSOR, "BrewZilla Internal")
    chosen, ordered = _resolve(selected, ble, ctl, internal)
    mash = chosen["value"] if chosen else None
    wort = internal["value"]
    diff = round(mash - wort, 2) if mash is not None and wort is not None else None
    return {
        "source": "brewzilla_temperature_resolver",
        "mash_source_select_entity": t.MASH_SOURCE_SELECT,
        "mash_source_selected": selected,
        "mash_temperature": mash,
        "mash_temperature_entity": chosen["entity_id"] if chosen else None,
        "mash_temperature_source": chosen["source"] if chosen else "Unavailable",
        "mash_temperature_source_payload_key": (chosen or {}).get("source_payload_key"),
        "mash_temperature_selected_control_device_temperature_source": (chosen or {}).get("selected_control_device_temperature_source"),
        "mash_temperature_value_rejected": (chosen or {}).get("ba_value_rejected"),
        "mash_temperature_reject_reason": (chosen or {}).get("ba_reject_reason"),
        "mash_temperature_age_seconds": (chosen or {}).get("age_seconds"),
        "mash_temperature_freshness_ok": (chosen or {}).get("freshness_ok"),
        "mash_temperature_external_mash_candidate": (chosen or {}).get("external_mash_candidate"),
        "wort_temperature": wort,
        "wort_temperature_entity": t.BREWZILLA_INTERNAL_TEMP_SENSOR,
        "wort_temperature_source": "BrewZilla Internal",
        "wort_temperature_age_seconds": internal.get("age_seconds"),
        "temperature_delta_mash_wort": diff,
        "auto_priority": "fresh distinct external temperature > BrewZilla Internal",
        "candidate_policy": {"min_external_internal_delta_c": MIN_DELTA_C},
        "ordered_candidates": ordered,
        "candidates": {
            "ble": _diag(ble, selected=selected, internal=internal),
            "control_device": _diag(ctl, selected=selected, internal=internal),
            "internal": _diag(internal, selected=selected, internal=internal),
        },
    }


def install_temperature_roles_patch() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    t._state_age_seconds = _age
    t.brewzilla_temperature_snapshot = _snapshot
    _INSTALLED = True
