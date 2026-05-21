"""Read-only BrewAssistant workflow/lifecycle engine."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .runtime import build_runtime_snapshot

_UNAVAILABLE_STATES = {"unknown", "unavailable", "none", ""}
_ON_STATES = {"on", "true", "yes", "active"}

DEFAULT_BATCH_ACTIVE_ENTITY = "input_boolean.brew_batch_active"
DEFAULT_COLD_CRASH_ACTIVE_ENTITY = "input_boolean.brew_cold_crash_active"
DEFAULT_PACKAGING_DONE_ENTITY = "input_boolean.brew_packaging_done"
DEFAULT_TRANSFERRED_TO_KEG_ENTITY = "input_boolean.brew_transferred_to_keg"
DEFAULT_LEGACY_PROCESS_STATUS_ENTITY = "sensor.brew_process_status"

PACKAGING_MAX_TEMP_C = 5.0
TRANSFER_MAX_TEMP_C = 5.0
GRAVITY_READY_MARGIN = 0.002


def _state_string(hass: HomeAssistant, entity_id: str | None) -> str | None:
    """Return a valid HA state string."""
    if not entity_id:
        return None
    state = hass.states.get(entity_id)
    if state is None or state.state.lower() in _UNAVAILABLE_STATES:
        return None
    return str(state.state)


def _state_float(hass: HomeAssistant, entity_id: str | None) -> float | None:
    """Return a valid HA state float."""
    raw = _state_string(hass, entity_id)
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _state_is_on(hass: HomeAssistant, entity_id: str | None) -> bool:
    """Return whether a HA entity is on/active."""
    raw = _state_string(hass, entity_id)
    return raw is not None and raw.lower() in _ON_STATES


def _format_temp(value: float | None) -> str:
    """Format a temperature."""
    if value is None:
        return "—"
    return f"{value:.1f}"


def _format_gravity(value: float | None) -> str:
    """Format specific gravity."""
    if value is None:
        return "—"
    return f"{value:.3f}"


def _runtime_available(runtime: dict[str, Any]) -> bool:
    """Return whether runtime data looks usable."""
    return bool(runtime.get("brewfather_available")) or bool(runtime.get("recipe_name"))


def _gravity_at_target(gravity: float | None, target_fg: float | None) -> bool:
    """Return whether gravity is close enough to target FG for packaging readiness."""
    if gravity is None:
        return False
    if target_fg is None:
        return gravity <= 1.010
    return gravity <= round(target_fg + GRAVITY_READY_MARGIN, 3)


def _normalize_legacy_status(value: str | None) -> str:
    """Normalize old YAML process status for conservative bridge decisions."""
    return (value or "").strip().lower()


def build_workflow_snapshot(
    hass: HomeAssistant,
    *,
    data: Any | None,
    runtime: dict[str, Any],
) -> dict[str, Any]:
    """Build one read-only workflow/lifecycle snapshot.

    This deliberately does not control climate, switches, fans or helpers.
    It reads current HA/runtime/Pill state and produces Python-owned lifecycle signals.
    """
    liquid_temp = getattr(data, "liquid_temperature", None) if data is not None else None
    target_temp = getattr(data, "recipe_target_temperature", None) if data is not None else None
    target_mode = getattr(data, "temperature_target_mode", None) if data is not None else None
    gravity = getattr(data, "gravity", None) if data is not None else None
    fallback_active = bool(getattr(data, "fallback_active", False)) if data is not None else False

    runtime_status = runtime.get("status")
    target_fg = runtime.get("target_fg")
    recipe_name = runtime.get("recipe_name")

    batch_active = _state_is_on(hass, DEFAULT_BATCH_ACTIVE_ENTITY)
    cold_crash_active = _state_is_on(hass, DEFAULT_COLD_CRASH_ACTIVE_ENTITY)
    packaging_done = _state_is_on(hass, DEFAULT_PACKAGING_DONE_ENTITY)
    transferred_to_keg = _state_is_on(hass, DEFAULT_TRANSFERRED_TO_KEG_ENTITY)
    legacy_status = _state_string(hass, DEFAULT_LEGACY_PROCESS_STATUS_ENTITY)
    legacy = _normalize_legacy_status(legacy_status)

    runtime_is_active = _runtime_available(runtime) and str(runtime_status or "").lower() not in {
        "archived",
        "completed",
        "done",
    }
    inferred_batch_active = batch_active or runtime_is_active or legacy not in {"", "idle"}
    cold_crash_by_runtime = target_mode == "Cold crash"
    cold_crash_by_legacy = "cold" in legacy
    cold_crash = cold_crash_active or cold_crash_by_runtime or cold_crash_by_legacy

    temp_ready_for_packaging = liquid_temp is not None and liquid_temp <= PACKAGING_MAX_TEMP_C
    temp_ready_for_transfer = liquid_temp is not None and liquid_temp <= TRANSFER_MAX_TEMP_C
    gravity_ready = _gravity_at_target(gravity, target_fg)
    source_ok = data is not None and liquid_temp is not None and target_temp is not None

    ready_for_packaging = (
        inferred_batch_active
        and cold_crash
        and temp_ready_for_packaging
        and gravity_ready
        and not transferred_to_keg
    )
    ready_for_transfer = ready_for_packaging and not packaging_done

    if transferred_to_keg:
        stage = "serving_storage"
        status = "Transferred to keg"
        status_sv = "Överförd till fat"
        next_step = "Lager or serve"
        next_step_sv = "Lagra eller servera"
        reason = "Transferred-to-keg flag is active"
    elif packaging_done:
        stage = "packaging_done"
        status = "Packaging done"
        status_sv = "Fatning klar"
        next_step = "Mark transferred to keg when complete"
        next_step_sv = "Markera överförd till fat när klart"
        reason = "Packaging-done flag is active"
    elif ready_for_transfer:
        stage = "ready_for_transfer"
        status = "Ready for transfer"
        status_sv = "Redo för överföring"
        next_step = "Perform closed transfer to keg"
        next_step_sv = "Gör syrefri överföring till fat"
        reason = "Cold, gravity-ready and batch active"
    elif ready_for_packaging:
        stage = "ready_for_packaging"
        status = "Ready for packaging"
        status_sv = "Redo för fatning"
        next_step = "Prepare keg and transfer setup"
        next_step_sv = "Förbered fat och överföring"
        reason = "Cold and gravity-ready"
    elif cold_crash:
        stage = "cold_crash"
        status = "Cold crash"
        status_sv = "Cold crash"
        next_step = "Wait until packaging checks pass"
        next_step_sv = "Vänta tills fatningskontrollerna är gröna"
        reason = "Cold crash is active or inferred"
    elif inferred_batch_active:
        stage = "fermentation"
        status = "Fermentation"
        status_sv = "Jäsning"
        next_step = "Monitor fermentation"
        next_step_sv = "Följ jäsningen"
        reason = "Active batch/runtime detected"
    else:
        stage = "idle"
        status = "Idle"
        status_sv = "Viloläge"
        next_step = "Start or select a batch"
        next_step_sv = "Starta eller välj batch"
        reason = "No active batch detected"

    checks = {
        "batch_active": inferred_batch_active,
        "cold_crash_active": cold_crash,
        "temperature_ready_for_packaging": temp_ready_for_packaging,
        "temperature_ready_for_transfer": temp_ready_for_transfer,
        "gravity_ready": gravity_ready,
        "source_ok": source_ok,
        "fallback_active": fallback_active,
        "packaging_done": packaging_done,
        "transferred_to_keg": transferred_to_keg,
    }

    summary_parts = [status_sv, next_step_sv]
    if liquid_temp is not None and target_temp is not None:
        summary_parts.append(f"{_format_temp(liquid_temp)} → {_format_temp(target_temp)} °C")
    if gravity is not None:
        summary_parts.append(f"SG {_format_gravity(gravity)}")

    return {
        "status": status,
        "status_sv": status_sv,
        "stage": stage,
        "next_step": next_step,
        "next_step_sv": next_step_sv,
        "summary": " · ".join(summary_parts),
        "reason": reason,
        "ready_for_packaging": ready_for_packaging,
        "ready_for_transfer": ready_for_transfer,
        "batch_active": inferred_batch_active,
        "cold_crash_active": cold_crash,
        "recipe_name": recipe_name,
        "runtime_status": runtime_status,
        "legacy_process_status": legacy_status,
        "target_fg": target_fg,
        "liquid_temperature": liquid_temp,
        "target_temperature": target_temp,
        "gravity": gravity,
        "checks": checks,
        "source_entities": {
            "batch_active": DEFAULT_BATCH_ACTIVE_ENTITY,
            "cold_crash_active": DEFAULT_COLD_CRASH_ACTIVE_ENTITY,
            "packaging_done": DEFAULT_PACKAGING_DONE_ENTITY,
            "transferred_to_keg": DEFAULT_TRANSFERRED_TO_KEG_ENTITY,
            "legacy_process_status": DEFAULT_LEGACY_PROCESS_STATUS_ENTITY,
        },
        "safe_mode": "read_only",
        "hardware_control": False,
    }


def workflow_attrs(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Return common workflow attributes for entities."""
    return {
        "stage": snapshot.get("stage"),
        "reason": snapshot.get("reason"),
        "recipe_name": snapshot.get("recipe_name"),
        "runtime_status": snapshot.get("runtime_status"),
        "legacy_process_status": snapshot.get("legacy_process_status"),
        "target_fg": snapshot.get("target_fg"),
        "liquid_temperature": snapshot.get("liquid_temperature"),
        "target_temperature": snapshot.get("target_temperature"),
        "gravity": snapshot.get("gravity"),
        "checks": snapshot.get("checks"),
        "source_entities": snapshot.get("source_entities"),
        "safe_mode": snapshot.get("safe_mode"),
        "hardware_control": snapshot.get("hardware_control"),
    }


def build_workflow_snapshot_from_coordinator(coordinator: Any) -> dict[str, Any]:
    """Build workflow snapshot from a BrewAssistant coordinator."""
    from .sensor import _runtime_entities  # local import avoids circular module import at startup

    runtime = build_runtime_snapshot(coordinator.hass, _runtime_entities(coordinator))
    return build_workflow_snapshot(coordinator.hass, data=coordinator.data, runtime=runtime)
