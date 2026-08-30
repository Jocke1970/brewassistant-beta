"""BrewZilla mash/wort temperature resolver."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from homeassistant.core import HomeAssistant

MASH_SOURCE_SELECT = "select.brewassistant_brewzilla_mash_temperature_source"

MASH_SOURCE_OPTIONS = [
    "Auto",
    "RAPT BLE Thermometer",
    "BrewZilla Control Device",
    "BrewZilla Internal",
]

BREWZILLA_INTERNAL_TEMP_SENSOR = "sensor.brewzilla_temperature"
BREWZILLA_BLE_TEMP_SENSOR = "sensor.brewzilla_ble_thermometer_temperature"
BREWZILLA_CONTROL_DEVICE_TEMP_SENSOR = "sensor.brewzilla_control_device_temperature"

BREWDAY_RUNTIME_STATE_SENSOR = "sensor.brewassistant_brewday_runtime_state"
BREWDAY_RUNTIME_STAGE_SENSOR = "sensor.brewassistant_brewday_stage"
BREWDAY_RUNTIME_STEP_SENSOR = "sensor.brewassistant_brewday_runtime_step"

MAX_EXTERNAL_MASH_TEMPERATURE_AGE_SECONDS = 180
MIN_EXTERNAL_INTERNAL_DELTA_C = 0.75

_RESOLVER_DATA_KEY = "brewzilla_temperature_resolver"
_ACTIVE_RUNTIME_STATES = {
    "live",
    "running",
    "paused",
    "awaiting_snapshot",
    "prepared",
    "awaiting_confirm",
}
_RELEASE_STAGE_WORDS = ("boil", "kok", "chill", "kyl", "transfer", "cleanup", "rengör")

_BAD = {None, "unknown", "unavailable", "none", ""}


def _state_obj(hass: HomeAssistant, entity_id: str | None):
    if not entity_id:
        return None
    return hass.states.get(entity_id)


def _state_value(hass: HomeAssistant, entity_id: str | None) -> str | None:
    state = _state_obj(hass, entity_id)
    if state is None or state.state in _BAD:
        return None
    return state.state


def _float_state(hass: HomeAssistant, entity_id: str | None) -> float | None:
    raw = _state_value(hass, entity_id)
    try:
        if raw is None or str(raw).lower() in _BAD:
            return None
        return round(float(raw), 2)
    except (TypeError, ValueError):
        return None


def _state_age_seconds(hass: HomeAssistant, entity_id: str | None) -> int | None:
    state = _state_obj(hass, entity_id)
    if state is None:
        return None
    updated = getattr(state, "last_reported", None) or state.last_updated
    if updated is None:
        return None
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=UTC)
    return max(0, int(round((datetime.now(UTC) - updated).total_seconds())))


def _attrs(hass: HomeAssistant, entity_id: str | None) -> dict[str, Any]:
    state = _state_obj(hass, entity_id)
    return dict(state.attributes) if state is not None else {}


def _resolver_store(hass: HomeAssistant) -> dict[str, Any]:
    return hass.data.setdefault("brewassistant", {}).setdefault(
        _RESOLVER_DATA_KEY,
        {
            "latched_auto_entity": None,
            "latched_auto_source": None,
            "verified_external_entities": {},
        },
    )


def _hot_side_process_sensor_owned(hass: HomeAssistant) -> bool:
    """Return true while Brewday owns the extra process sensor before Boil.

    The external mash/process probe belongs to Brewday from Heat strike through
    pre-boil. Reaching the same temperature as the BrewZilla internal probe must
    not release that ownership. Ownership ends when Boil (or a later hot-side
    stage) actually starts.
    """

    runtime_state = str(_state_value(hass, BREWDAY_RUNTIME_STATE_SENSOR) or "").strip().lower()
    if runtime_state not in _ACTIVE_RUNTIME_STATES:
        return False

    stage = str(_state_value(hass, BREWDAY_RUNTIME_STAGE_SENSOR) or "").strip().lower()
    step = str(_state_value(hass, BREWDAY_RUNTIME_STEP_SENSOR) or "").strip().lower()
    combined = f"{stage} {step}"

    if "pre-boil" in combined or "pre boil" in combined or "förkok" in combined:
        return True

    return not any(word in combined for word in _RELEASE_STAGE_WORDS)


def selected_mash_source(hass: HomeAssistant) -> str:
    """Return operator-selected mash temperature source."""
    selected = _state_value(hass, MASH_SOURCE_SELECT)
    if selected in MASH_SOURCE_OPTIONS:
        return str(selected)
    return "Auto"


def _looks_like_control_telemetry(candidate: dict[str, Any]) -> bool:
    return bool(
        candidate.get("source_payload_key") == "controlDeviceTemperature"
        or candidate.get("selected_control_device_temperature_source") == "telemetry"
    )


def _internal_delta_c(candidate: dict[str, Any], internal: dict[str, Any] | None) -> float | None:
    if internal is None:
        return None
    value = candidate.get("value")
    internal_value = internal.get("value")
    if value is None or internal_value is None:
        return None
    try:
        return round(abs(float(value) - float(internal_value)), 2)
    except (TypeError, ValueError):
        return None


def _distinct_from_internal(candidate: dict[str, Any], internal: dict[str, Any] | None) -> bool:
    delta = _internal_delta_c(candidate, internal)
    return bool(delta is not None and delta >= MIN_EXTERNAL_INTERNAL_DELTA_C)


def _candidate(hass: HomeAssistant, entity_id: str, label: str) -> dict[str, Any]:
    value = _float_state(hass, entity_id)
    attrs = _attrs(hass, entity_id)
    age_seconds = _state_age_seconds(hass, entity_id)
    external = label != "BrewZilla Internal"
    raw_rejected = bool(attrs.get("ba_value_rejected"))
    raw_reject_reason = attrs.get("ba_reject_reason")

    freshness_ok = True
    if external and age_seconds is not None:
        freshness_ok = age_seconds <= MAX_EXTERNAL_MASH_TEMPERATURE_AGE_SECONDS

    return {
        "value": value,
        "entity_id": entity_id,
        "source": label,
        "available": value is not None,
        "attrs": attrs,
        "age_seconds": age_seconds,
        "freshness_ok": freshness_ok,
        "max_age_seconds": MAX_EXTERNAL_MASH_TEMPERATURE_AGE_SECONDS if external else None,
        "external_mash_candidate": external,
        "source_payload_key": attrs.get("source_payload_key"),
        "selected_control_device_temperature_source": attrs.get("selected_control_device_temperature_source"),
        "ba_value_rejected": raw_rejected,
        "ba_reject_reason": raw_reject_reason,
    }


def _candidate_reject_reason(candidate: dict[str, Any], *, selected: str, internal: dict[str, Any] | None) -> str | None:
    if not candidate["available"]:
        return "unavailable"
    if candidate.get("ba_value_rejected"):
        return str(candidate.get("ba_reject_reason") or "source_rejected_value")
    if not candidate.get("freshness_ok", True):
        return f"stale_{candidate.get('age_seconds')}s"

    source = candidate.get("source")
    control_telemetry = _looks_like_control_telemetry(candidate)
    distinct = _distinct_from_internal(candidate, internal)

    if selected == "Auto" and source == "RAPT BLE Thermometer" and control_telemetry and not distinct:
        return "ble_aliasing_internal_temperature"

    if selected == "Auto" and source == "BrewZilla Control Device" and control_telemetry and not distinct:
        return "control_device_aliasing_internal_temperature"

    return None


def _eligible(candidate: dict[str, Any], *, selected: str, internal: dict[str, Any] | None) -> bool:
    return _candidate_reject_reason(candidate, selected=selected, internal=internal) is None


def _basic_external_usable(candidate: dict[str, Any]) -> bool:
    """Return true for a latched external source even when values converge."""
    return bool(
        candidate.get("external_mash_candidate")
        and candidate.get("available")
        and candidate.get("freshness_ok", True)
        and not candidate.get("ba_value_rejected")
    )


def _with_diagnostics(candidate: dict[str, Any], *, selected: str, internal: dict[str, Any] | None) -> dict[str, Any]:
    reject_reason = _candidate_reject_reason(candidate, selected=selected, internal=internal)
    return {
        **{k: v for k, v in candidate.items() if k != "attrs"},
        "internal_delta_c": _internal_delta_c(candidate, internal),
        "distinct_external_temperature": _distinct_from_internal(candidate, internal),
        "eligible": reject_reason is None,
        "reject_reason": reject_reason,
    }


def _remember_verified_external(
    store: dict[str, Any],
    candidates: tuple[dict[str, Any], ...],
    internal: dict[str, Any],
) -> None:
    """Remember external channels that have demonstrated independent telemetry."""
    verified = store.setdefault("verified_external_entities", {})
    for candidate in candidates:
        if not _basic_external_usable(candidate):
            continue
        if not _distinct_from_internal(candidate, internal):
            continue
        verified[str(candidate["entity_id"])] = {
            "source": candidate.get("source"),
            "verified_at": datetime.now(UTC).isoformat(),
        }


def _candidate_by_entity(
    entity_id: str | None,
    candidates: tuple[dict[str, Any], ...],
) -> dict[str, Any] | None:
    if not entity_id:
        return None
    return next((candidate for candidate in candidates if candidate.get("entity_id") == entity_id), None)


def _resolve_mash_candidate(
    selected: str,
    ble: dict[str, Any],
    control: dict[str, Any],
    internal: dict[str, Any],
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    if selected == "RAPT BLE Thermometer":
        ordered = [ble, internal]
    elif selected == "BrewZilla Control Device":
        ordered = [control, internal]
    elif selected == "BrewZilla Internal":
        ordered = [internal]
    else:
        ordered = [ble, control, internal]

    diagnostics = [_with_diagnostics(candidate, selected=selected, internal=internal) for candidate in ordered]
    mash = next((candidate for candidate in ordered if _eligible(candidate, selected=selected, internal=internal)), None)
    return mash, diagnostics


def _resolve_auto_with_hot_side_ownership(
    hass: HomeAssistant,
    ble: dict[str, Any],
    control: dict[str, Any],
    internal: dict[str, Any],
) -> tuple[dict[str, Any] | None, bool, str | None]:
    """Keep a verified external process source stable through convergence."""
    store = _resolver_store(hass)
    externals = (ble, control)
    all_candidates = (ble, control, internal)
    _remember_verified_external(store, externals, internal)

    if not _hot_side_process_sensor_owned(hass):
        store["latched_auto_entity"] = None
        store["latched_auto_source"] = None
        mash, _ = _resolve_mash_candidate("Auto", ble, control, internal)
        return mash, False, None

    latched = _candidate_by_entity(store.get("latched_auto_entity"), all_candidates)
    if latched is not None:
        if _basic_external_usable(latched):
            return latched, True, None

        # Safety fallback is allowed while the owned probe is stale/unavailable,
        # but the latch identity is retained so the same process source resumes
        # automatically when it becomes healthy again.
        fallback, _ = _resolve_mash_candidate("Auto", ble, control, internal)
        reason = _candidate_reject_reason(latched, selected=str(latched.get("source")), internal=internal)
        return fallback, True, reason or "latched_external_temporarily_unusable"

    mash, _ = _resolve_mash_candidate("Auto", ble, control, internal)
    if mash is not None and mash.get("external_mash_candidate"):
        store["latched_auto_entity"] = mash.get("entity_id")
        store["latched_auto_source"] = mash.get("source")
        return mash, True, None

    verified = store.get("verified_external_entities") or {}
    for candidate in externals:
        if candidate.get("entity_id") not in verified:
            continue
        if not _basic_external_usable(candidate):
            continue
        store["latched_auto_entity"] = candidate.get("entity_id")
        store["latched_auto_source"] = candidate.get("source")
        return candidate, True, None

    return mash, False, None


def brewzilla_temperature_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    """Return resolved BrewZilla mash/wort temperature snapshot.

    Wort/kettle temperature is always the BrewZilla internal thermometer.
    Mash temperature is operator-selectable. Auto prefers a valid, fresh external
    mash temperature. During active hot-side ownership before Boil, a verified
    external process source is latched so physical convergence with the internal
    probe cannot silently replace the mash/BLE source.
    """
    selected = selected_mash_source(hass)

    ble = _candidate(hass, BREWZILLA_BLE_TEMP_SENSOR, "RAPT BLE Thermometer")
    control = _candidate(hass, BREWZILLA_CONTROL_DEVICE_TEMP_SENSOR, "BrewZilla Control Device")
    internal = _candidate(hass, BREWZILLA_INTERNAL_TEMP_SENSOR, "BrewZilla Internal")

    store = _resolver_store(hass)
    _remember_verified_external(store, (ble, control), internal)

    source_lock_active = False
    source_lock_degraded_reason = None
    if selected == "Auto":
        mash, source_lock_active, source_lock_degraded_reason = _resolve_auto_with_hot_side_ownership(
            hass,
            ble,
            control,
            internal,
        )
        _, ordered_diagnostics = _resolve_mash_candidate(selected, ble, control, internal)
    else:
        store["latched_auto_entity"] = None
        store["latched_auto_source"] = None
        mash, ordered_diagnostics = _resolve_mash_candidate(selected, ble, control, internal)

    # External-sensor visibility must not disappear merely because a physically
    # owned process probe converges with the internal thermometer. Outside an
    # active lock, keep the original Auto aliasing heuristics.
    if source_lock_active and mash is not None and mash.get("external_mash_candidate") and _basic_external_usable(mash):
        external = _with_diagnostics(mash, selected=str(mash.get("source")), internal=internal)
        external = {**external, "source_lock_active": True}
    else:
        external_ble = _with_diagnostics(ble, selected="Auto", internal=internal)
        external_control = _with_diagnostics(control, selected="Auto", internal=internal)
        external_candidates = [external_ble, external_control]
        external = next((candidate for candidate in external_candidates if candidate.get("eligible")), None)

    external_ble = _with_diagnostics(ble, selected="Auto", internal=internal)
    external_control = _with_diagnostics(control, selected="Auto", internal=internal)

    mash_temperature = mash["value"] if mash else None
    mash_entity = mash["entity_id"] if mash else None
    mash_source = mash["source"] if mash else "Unavailable"

    wort_temperature = internal["value"]
    delta = None
    if mash_temperature is not None and wort_temperature is not None:
        delta = round(mash_temperature - wort_temperature, 2)

    return {
        "source": "brewzilla_temperature_resolver",
        "mash_source_select_entity": MASH_SOURCE_SELECT,
        "mash_source_selected": selected,
        "mash_temperature": mash_temperature,
        "mash_temperature_entity": mash_entity,
        "mash_temperature_source": mash_source,
        "mash_temperature_source_payload_key": (mash or {}).get("source_payload_key"),
        "mash_temperature_selected_control_device_temperature_source": (mash or {}).get(
            "selected_control_device_temperature_source"
        ),
        "mash_temperature_value_rejected": (mash or {}).get("ba_value_rejected"),
        "mash_temperature_reject_reason": (mash or {}).get("ba_reject_reason"),
        "mash_temperature_age_seconds": (mash or {}).get("age_seconds"),
        "mash_temperature_freshness_ok": (mash or {}).get("freshness_ok"),
        "mash_temperature_external_mash_candidate": (mash or {}).get("external_mash_candidate"),
        "mash_temperature_source_lock_active": source_lock_active,
        "mash_temperature_source_lock_entity": store.get("latched_auto_entity"),
        "mash_temperature_source_lock_source": store.get("latched_auto_source"),
        "mash_temperature_source_lock_degraded_reason": source_lock_degraded_reason,
        "hot_side_process_sensor_owned": _hot_side_process_sensor_owned(hass),
        "verified_external_temperature_entities": dict(store.get("verified_external_entities") or {}),
        "external_temperature_available": external is not None,
        "external_temperature_source": external.get("source") if external else None,
        "external_temperature_entity": external.get("entity_id") if external else None,
        "external_temperature_age_seconds": external.get("age_seconds") if external else None,
        "external_temperature_candidates": {
            "ble": external_ble,
            "control_device": external_control,
        },
        "wort_temperature": wort_temperature,
        "wort_temperature_entity": BREWZILLA_INTERNAL_TEMP_SENSOR,
        "wort_temperature_source": "BrewZilla Internal",
        "wort_temperature_age_seconds": internal.get("age_seconds"),
        "temperature_delta_mash_wort": delta,
        "auto_priority": (
            "active hot-side: latched verified external process source > healthy fallback; "
            "idle/post-boil: fresh distinct external mash temperature > BrewZilla Internal"
        ),
        "candidate_policy": {
            "max_external_mash_temperature_age_seconds": MAX_EXTERNAL_MASH_TEMPERATURE_AGE_SECONDS,
            "min_external_internal_delta_c": MIN_EXTERNAL_INTERNAL_DELTA_C,
            "auto_accepts_control_telemetry_when_distinct_from_internal": True,
            "auto_rejects_unverified_external_aliasing_internal_temperature": True,
            "active_hot_side_latches_verified_external_source_across_convergence": True,
            "latched_external_may_fallback_when_stale_or_unavailable": True,
            "explicit_source_selection_overrides_aliasing_guard": True,
        },
        "ordered_candidates": ordered_diagnostics,
        "candidates": {
            "ble": _with_diagnostics(ble, selected=selected, internal=internal),
            "control_device": _with_diagnostics(control, selected=selected, internal=internal),
            "internal": _with_diagnostics(internal, selected=selected, internal=internal),
        },
    }
