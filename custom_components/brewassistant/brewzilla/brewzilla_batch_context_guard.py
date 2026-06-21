"""BrewZilla batch-context source priority guard."""

from __future__ import annotations

from typing import Any

from . import brewzilla_learning as _base

_BASE_BATCH_CONTEXT_SNAPSHOT = _base._batch_context_snapshot
_INSTALLED = False


def _present(value: Any) -> bool:
    return value is not None


def _runtime_looks_live_brewfather(runtime: dict[str, Any]) -> bool:
    source_text = " ".join(
        str(runtime.get(key) or "")
        for key in (
            "source",
            "source_name",
            "runtime_source",
            "runtime_source_name",
        )
    ).lower()
    if "brewfather" in source_text:
        return True
    state = str(runtime.get("state") or runtime.get("runtime_state") or "").lower()
    return state in _base._ACTIVE_STATES and bool(runtime.get("brewfather_active"))


def _brewfather_tracker_is_active(hass) -> bool:
    status = str(_base._state(hass, "sensor.brewfather_brew_tracker_status", "") or "").lower()
    if status and status not in {"inactive", "idle", "unknown", "unavailable", "none"}:
        return True

    stage = hass.states.get("sensor.brewfather_brew_tracker_stage")
    if stage is not None:
        active = stage.attributes.get("active")
        if active is True or str(active).lower() in {"true", "on", "yes"}:
            return True
        batch_status = str(stage.attributes.get("brew_tracker_batch_status") or "").lower()
        if batch_status in {"brewing", "active", "running"}:
            return True

    return False


def _live_brewfather_context(hass, runtime: dict[str, Any]) -> bool:
    return _runtime_looks_live_brewfather(runtime) or _brewfather_tracker_is_active(hass)


def _choose_context_value(
    key: str,
    *,
    brewfather: dict[str, Any],
    manual: dict[str, Any],
    fallback: dict[str, Any],
) -> tuple[Any, str | None]:
    if _present(brewfather.get(key)):
        return brewfather.get(key), "brewfather"
    if _present(manual.get(key)):
        return manual.get(key), "manual_fallback"
    return fallback.get(key), None


def _batch_context_snapshot(hass, runtime: dict[str, Any], stage_kind: str) -> dict[str, Any]:
    """Resolve batch context with live Brewfather priority.

    In supervised runtime execution, a live Brewfather BrewTracker batch is the
    process source. Manual batch context must fill gaps, not override live recipe
    data from the runtime source.
    """
    snapshot = dict(_BASE_BATCH_CONTEXT_SNAPSHOT(hass, runtime, stage_kind))
    brewfather = _base._brewfather_batch_context(hass)

    if not brewfather.get("source") or not _live_brewfather_context(hass, runtime):
        snapshot["batch_context_priority"] = "manual_first_no_live_brewfather"
        snapshot["batch_context_brewfather_active"] = False
        return snapshot

    manual = _base._manual_batch_context(hass)
    resolved: dict[str, Any] = {}
    value_sources: dict[str, str] = {}

    for key in (
        "grain_amount_kg",
        "mash_water_l",
        "sparge_water_l",
        "pre_boil_volume_l",
    ):
        value, source = _choose_context_value(
            key,
            brewfather=brewfather,
            manual=manual,
            fallback=snapshot,
        )
        resolved[key] = value
        if source:
            value_sources[key] = source

    manual_grain_temp = manual.get("grain_temperature_c")
    resolved["grain_temperature_c"] = (
        manual_grain_temp if manual_grain_temp is not None else _base.DEFAULT_GRAIN_TEMPERATURE_C
    )
    value_sources["grain_temperature_c"] = "manual" if manual_grain_temp is not None else "assumed_default"

    missing = []
    if resolved.get("grain_amount_kg") is None:
        missing.append("grain_amount_kg")
    if resolved.get("mash_water_l") is None:
        missing.append("mash_water_l")
    if resolved.get("grain_temperature_c") is None:
        missing.append("grain_temperature_c")

    context_required = bool(snapshot.get("needs_batch_context") or snapshot.get("batch_context_missing"))
    source_parts = []
    if any(source == "brewfather" for source in value_sources.values()):
        source_parts.append(str(brewfather["source"]))
    if any(source in {"manual", "manual_fallback"} for source in value_sources.values()):
        source_parts.append("manual_fallback")
    if any(source == "assumed_default" for source in value_sources.values()):
        source_parts.append("assumed_default")

    snapshot.update(
        {
            "batch_context_source": "+".join(source_parts) if source_parts else snapshot.get("batch_context_source"),
            "batch_context_priority": "live_brewfather_first",
            "batch_context_brewfather_active": True,
            "batch_context_value_sources": value_sources,
            "batch_context_available": not missing,
            "needs_batch_context": bool(context_required and missing),
            "batch_context_missing": missing if context_required else [],
            "grain_amount_kg": resolved.get("grain_amount_kg"),
            "mash_water_l": resolved.get("mash_water_l"),
            "sparge_water_l": resolved.get("sparge_water_l"),
            "pre_boil_volume_l": resolved.get("pre_boil_volume_l"),
            "grain_temperature_c": resolved.get("grain_temperature_c"),
            "grain_temperature_assumed": value_sources.get("grain_temperature_c") == "assumed_default",
        }
    )
    return snapshot


def install_batch_context_guard() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _base._batch_context_snapshot = _batch_context_snapshot
    _INSTALLED = True
