"""Coordinator for BrewAssistant normalized state."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .brewday.brewday_operator_abort import async_load_brewday_operator_abort
from .brewday.brewday_refresh import maybe_request_brewfather_refresh
from .brewzilla.brewzilla_learning import async_update_brewday_advice_notification
from .brewzilla.brewzilla_orchestration import async_apply_brewzilla_target_if_allowed
from .climate_backend.climate_supervisor import async_apply_climate_supervisor
from .const import (
    CONF_CHAMBER_TEMP_ENTITY,
    CONF_COLD_CRASH_ACTIVE_ENTITY,
    CONF_COLD_CRASH_TARGET_ENTITY,
    CONF_FERMENTATION_HEAT_POWER_ENTITY,
    CONF_GRAVITY_ENTITY,
    CONF_KEGERATOR_AIR_TEMP_ENTITY,
    CONF_KEGERATOR_FAN_POWER_ENTITY,
    CONF_KEGERATOR_POWER_ENTITY,
    CONF_LIQUID_TEMP_ENTITY,
    CONF_RECIPE_TARGET_ENTITY,
    DEFAULT_CHAMBER_TEMP_ENTITY,
    DEFAULT_COLD_CRASH_ACTIVE_ENTITY,
    DEFAULT_COLD_CRASH_TARGET_ENTITY,
    DEFAULT_FERMENTATION_HEAT_POWER_ENTITY,
    DEFAULT_GRAVITY_ENTITY,
    DEFAULT_KEGERATOR_AIR_TEMP_ENTITY,
    DEFAULT_KEGERATOR_FAN_POWER_ENTITY,
    DEFAULT_KEGERATOR_POWER_ENTITY,
    DEFAULT_LIQUID_TEMP_ENTITY,
    DEFAULT_RECIPE_TARGET_ENTITY,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .fermentation.fermentation_runtime import (
    async_setup_fermentation_runtime,
    build_fermentation_snapshot,
)
from .kegerator.fan_control import async_apply_kegerator_fan_auto

_LOGGER = logging.getLogger(__name__)
_UNAVAILABLE_STATES = {"unknown", "unavailable", "none", ""}
_ON_STATES = {"on", "true", "yes", "active"}
_ACTIVE_FERMENTATION_STAGES = {"fermentation", "cold_crash"}
_FERMENTATION_ACTIVITY_ENTITIES = (
    "input_boolean.brew_batch_active",
    "input_boolean.brewassistant_fermentation_active",
    "input_boolean.brewassistant_fermentation_module_active",
    "input_boolean.manual_batch_active",
)
_INACTIVE_RUNTIME_STATUSES = {
    "completed",
    "complete",
    "finished",
    "packaged",
    "transferred",
    "transferred to keg",
    "serving",
    "carbonating",
    "conditioning",
}
FAN_AUTO_SWITCH = "switch.brewassistant_kegerator_fan_auto_enabled"


@dataclass(slots=True)
class BrewAssistantData:
    """Normalized BrewAssistant data snapshot."""

    liquid_temperature: float | None
    liquid_temperature_source: str
    liquid_temperature_entity: str | None
    chamber_temperature: float | None
    recipe_target_temperature: float | None
    recipe_target_temperature_entity: str | None
    temperature_target_mode: str
    temperature_delta: float | None
    temperature_status: str
    temperature_severity: str
    temperature_icon_hint: str
    temperature_color_hint: str
    source_summary: str
    status_summary: str
    problem_level: str
    process_status: str
    process_next_step: str
    process_current_action_stage: str
    process_next_action_stage: str
    process_summary: str
    process_reason: str
    gravity: float | None
    fallback_active: bool
    ready: bool


def _entity_from_entry(entry: ConfigEntry, key: str, fallback: str) -> str:
    return str(entry.options.get(key) or entry.data.get(key) or fallback)


def _state_float(hass: HomeAssistant, entity_id: str | None) -> float | None:
    if not entity_id:
        return None
    state = hass.states.get(entity_id)
    if state is None or state.state in _UNAVAILABLE_STATES:
        return None
    try:
        return float(str(state.state).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _state_string(hass: HomeAssistant, entity_id: str | None) -> str | None:
    if not entity_id:
        return None
    state = hass.states.get(entity_id)
    if state is None or state.state in _UNAVAILABLE_STATES:
        return None
    return str(state.state)


def _state_is_on(hass: HomeAssistant, entity_id: str | None) -> bool:
    if not entity_id:
        return False
    state = hass.states.get(entity_id)
    return state is not None and state.state.lower() in _ON_STATES


def _any_state_is_on(hass: HomeAssistant, entity_ids: tuple[str, ...]) -> bool:
    return any(_state_is_on(hass, entity_id) for entity_id in entity_ids)


def _format_temp(value: float | None) -> str:
    return "—" if value is None else f"{value:.1f}"


def _format_gravity(value: float | None) -> str:
    return "—" if value is None else f"{value:.3f}"


def _temperature_context(
    liquid_temp: float | None,
    target_temp: float | None,
    delta: float | None,
    source: str,
    fallback_active: bool,
    target_mode: str,
) -> dict[str, str]:
    if liquid_temp is None:
        return {
            "status": "Unavailable",
            "severity": "problem",
            "icon_hint": "alert-circle",
            "color_hint": "red",
            "source_summary": f"{source} unavailable",
            "status_summary": "Temperature unavailable · check source entities",
            "problem_level": "problem",
        }
    if target_temp is None or delta is None:
        return {
            "status": "Monitoring",
            "severity": "warning",
            "icon_hint": "thermometer-alert",
            "color_hint": "amber",
            "source_summary": f"{source} · no target",
            "status_summary": f"{_format_temp(liquid_temp)} °C · target unavailable · {source}",
            "problem_level": "warning",
        }

    abs_delta = abs(delta)
    if abs_delta <= 0.25:
        status, severity, icon_hint, color_hint, problem_level = (
            "On target",
            "ok",
            "check-circle",
            "green",
            "ok",
        )
    elif abs_delta <= 0.5:
        status, severity, icon_hint, color_hint, problem_level = (
            "Slight offset",
            "info",
            "delta",
            "amber",
            "info",
        )
    else:
        status, severity, icon_hint, color_hint, problem_level = (
            "Temp offset",
            "warning",
            "thermometer-alert",
            "red",
            "warning",
        )

    if fallback_active:
        status = "Fallback active"
        severity = "warning" if severity == "ok" else severity
        icon_hint = "fridge-alert"
        color_hint = "amber"
        problem_level = "warning" if problem_level == "ok" else problem_level

    direction = "above" if delta > 0 else "below" if delta < 0 else "on"
    source_summary = f"{source}{' · fallback' if fallback_active else ''}"
    return {
        "status": status,
        "severity": severity,
        "icon_hint": icon_hint,
        "color_hint": color_hint,
        "source_summary": source_summary,
        "status_summary": (
            f"{target_mode} · {_format_temp(liquid_temp)} → {_format_temp(target_temp)} °C "
            f"· Δ {delta:+.2f} °C · {direction} target · {source_summary}"
        ),
        "problem_level": problem_level,
    }


def _standby_temperature_context(
    context: dict[str, str],
    process: dict[str, str],
    liquid_temp: float | None,
    target_temp: float | None,
    delta: float | None,
) -> dict[str, str]:
    temp_part = ""
    if liquid_temp is not None and target_temp is not None and delta is not None:
        temp_part = f" · {_format_temp(liquid_temp)} → {_format_temp(target_temp)} °C · Δ {delta:+.2f} °C"
    elif liquid_temp is not None:
        temp_part = f" · {_format_temp(liquid_temp)} °C"
    status = "Completed" if process["status"] == "Finished / transferred to keg" else "Standby"
    return {
        **context,
        "status": status,
        "severity": "ok",
        "icon_hint": "sleep",
        "color_hint": "blue",
        "problem_level": "ok",
        "status_summary": f"Fermentation {status.lower()} · {process['reason']}{temp_part}",
    }


def _process_context(
    *,
    cold_crash_active: bool,
    target_mode: str,
    runtime_status: str | None,
    liquid_temp: float | None,
    target_temp: float | None,
    gravity: float | None,
    fermentation: dict[str, Any],
) -> dict[str, str]:
    normalized_runtime = (runtime_status or "").lower()

    if cold_crash_active or target_mode == "Cold crash":
        status = "Cold crash"
        next_step = "Maintain cold crash and positive pressure"
        current_stage = "cold_crash"
        next_stage = "transfer"
        reason = "Cold crash target is active"
    elif fermentation.get("active"):
        status = str(fermentation.get("status") or "Primary fermentation")
        next_step = str(fermentation.get("next_action") or "Monitor fermentation")
        current_stage = "fermentation"
        next_stage = "cold_crash" if fermentation.get("ready_for_cold_crash") else "fermentation"
        reason = (
            "Python-owned fermentation runtime active · "
            f"gravity source {fermentation.get('gravity_source') or 'unavailable'}"
        )
    elif normalized_runtime in _INACTIVE_RUNTIME_STATUSES:
        status = "Finished / transferred to keg"
        next_step = "Batch completed"
        current_stage = "none"
        next_stage = "none"
        reason = f"Runtime status indicates inactive batch: {normalized_runtime}"
    elif normalized_runtime == "fermenting":
        status = "Primary fermentation"
        next_step = "Monitor fermentation"
        current_stage = "fermentation"
        next_stage = "cold_crash"
        reason = "Runtime status is fermenting"
    elif normalized_runtime:
        status = runtime_status or "Monitoring"
        next_step = "Monitor active runtime"
        current_stage = "runtime"
        next_stage = "none"
        reason = "Runtime status is available but not fermentation-scoped"
    else:
        status = "Idle"
        next_step = "Start or select an active batch"
        current_stage = "none"
        next_stage = "none"
        reason = "No active Python runtime detected"

    summary_parts = [status, next_step]
    if liquid_temp is not None and target_temp is not None:
        summary_parts.append(f"{_format_temp(liquid_temp)} → {_format_temp(target_temp)} °C")
    if gravity is not None:
        summary_parts.append(f"SG {_format_gravity(gravity)}")
    return {
        "status": status,
        "next_step": next_step,
        "current_stage": current_stage,
        "next_stage": next_stage,
        "summary": " · ".join(summary_parts),
        "reason": reason,
    }


class BrewAssistantCoordinator(DataUpdateCoordinator[BrewAssistantData]):
    """Collect normalized BrewAssistant state from HA entities and Python stores."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.config_entry = entry

    async def _async_update_data(self) -> BrewAssistantData:
        # Load the persisted operator ABORT before any Brewday refresh or
        # orchestration decision. A Home Assistant restart must never silently
        # re-arm a previously aborted hot-side session.
        await async_load_brewday_operator_abort(self.hass)
        await async_setup_fermentation_runtime(self.hass)

        refresh_result = await maybe_request_brewfather_refresh(self.hass)
        brewzilla_result = await async_apply_brewzilla_target_if_allowed(self.hass)
        if refresh_result.get("refreshed") or brewzilla_result.get("applied"):
            self.hass.data.setdefault(DOMAIN, {})["last_brewday_tick"] = {
                "refresh": refresh_result,
                "brewzilla": brewzilla_result,
            }
        advice_notification_result = await async_update_brewday_advice_notification(self.hass)
        if advice_notification_result.get("notification_result") in {
            "created",
            "dismissed_no_pending",
            "dismissed_after_apply",
            "dismissed_after_deny",
        }:
            self.hass.data.setdefault(DOMAIN, {}).setdefault("last_brewday_tick", {})[
                "advice_notification"
            ] = advice_notification_result

        await async_apply_climate_supervisor(self.hass)
        if self.hass.states.is_state(FAN_AUTO_SWITCH, "on"):
            fan_result = await async_apply_kegerator_fan_auto(self.hass)
            self.hass.data.setdefault(DOMAIN, {})["last_kegerator_fan_auto_tick"] = fan_result

        liquid_entity = _entity_from_entry(self.config_entry, CONF_LIQUID_TEMP_ENTITY, DEFAULT_LIQUID_TEMP_ENTITY)
        chamber_entity = _entity_from_entry(self.config_entry, CONF_CHAMBER_TEMP_ENTITY, DEFAULT_CHAMBER_TEMP_ENTITY)
        target_entity = _entity_from_entry(self.config_entry, CONF_RECIPE_TARGET_ENTITY, DEFAULT_RECIPE_TARGET_ENTITY)
        cold_crash_active_entity = _entity_from_entry(
            self.config_entry, CONF_COLD_CRASH_ACTIVE_ENTITY, DEFAULT_COLD_CRASH_ACTIVE_ENTITY
        )
        cold_crash_target_entity = _entity_from_entry(
            self.config_entry, CONF_COLD_CRASH_TARGET_ENTITY, DEFAULT_COLD_CRASH_TARGET_ENTITY
        )
        gravity_entity = _entity_from_entry(self.config_entry, CONF_GRAVITY_ENTITY, DEFAULT_GRAVITY_ENTITY)

        pill_temp = _state_float(self.hass, liquid_entity)
        chamber_temp = _state_float(self.hass, chamber_entity)
        recipe_target_temp = _state_float(self.hass, target_entity)
        cold_crash_target_temp = _state_float(self.hass, cold_crash_target_entity)

        gravity_state = self.hass.states.get(gravity_entity)
        external_gravity = _state_float(self.hass, gravity_entity)
        external_updated_at = gravity_state.last_updated if external_gravity is not None and gravity_state else None
        fermentation = build_fermentation_snapshot(
            self.hass,
            external_sg=external_gravity,
            external_updated_at=external_updated_at,
            external_entity=gravity_entity,
        )
        gravity = fermentation.get("current_sg")

        runtime_status = _state_string(self.hass, "sensor.recipe_runtime_status")
        normalized_runtime = (runtime_status or "").lower()
        runtime_inactive = normalized_runtime in _INACTIVE_RUNTIME_STATUSES
        runtime_active = bool(normalized_runtime and not runtime_inactive)
        fermentation_context_active = (
            runtime_active
            or bool(fermentation.get("active"))
            or _any_state_is_on(self.hass, _FERMENTATION_ACTIVITY_ENTITIES)
        )

        cold_crash_active = _state_is_on(self.hass, cold_crash_active_entity)
        cold_crash_in_scope = (
            cold_crash_active
            and cold_crash_target_temp is not None
            and not runtime_inactive
            and fermentation_context_active
        )
        if cold_crash_in_scope:
            target_temp = cold_crash_target_temp
            effective_target_entity = cold_crash_target_entity
            target_mode = "Cold crash"
        else:
            target_temp = recipe_target_temp
            effective_target_entity = target_entity
            target_mode = "Recipe"

        if pill_temp is not None:
            liquid_temp = pill_temp
            source = "RAPT Pill"
            source_entity: str | None = liquid_entity
            fallback_active = False
        else:
            liquid_temp = chamber_temp
            source = "Chamber fallback" if chamber_temp is not None else "Unavailable"
            source_entity = chamber_entity if chamber_temp is not None else None
            fallback_active = chamber_temp is not None

        delta = round(liquid_temp - target_temp, 2) if liquid_temp is not None and target_temp is not None else None
        rounded_liquid = round(liquid_temp, 2) if liquid_temp is not None else None
        rounded_chamber = round(chamber_temp, 2) if chamber_temp is not None else None
        rounded_target = round(target_temp, 2) if target_temp is not None else None
        rounded_gravity = round(float(gravity), 3) if gravity is not None else None

        context = _temperature_context(
            rounded_liquid,
            rounded_target,
            delta,
            source,
            fallback_active,
            target_mode,
        )
        process = _process_context(
            cold_crash_active=cold_crash_in_scope,
            target_mode=target_mode,
            runtime_status=runtime_status,
            liquid_temp=rounded_liquid,
            target_temp=rounded_target,
            gravity=rounded_gravity,
            fermentation=fermentation,
        )
        if process["current_stage"] not in _ACTIVE_FERMENTATION_STAGES:
            context = _standby_temperature_context(context, process, rounded_liquid, rounded_target, delta)

        status_summary = context["status_summary"]
        if rounded_gravity is not None:
            status_summary = f"{status_summary} · SG {_format_gravity(rounded_gravity)}"

        return BrewAssistantData(
            liquid_temperature=rounded_liquid,
            liquid_temperature_source=source,
            liquid_temperature_entity=source_entity,
            chamber_temperature=rounded_chamber,
            recipe_target_temperature=rounded_target,
            recipe_target_temperature_entity=effective_target_entity,
            temperature_target_mode=target_mode,
            temperature_delta=delta,
            temperature_status=context["status"],
            temperature_severity=context["severity"],
            temperature_icon_hint=context["icon_hint"],
            temperature_color_hint=context["color_hint"],
            source_summary=context["source_summary"],
            status_summary=status_summary,
            problem_level=context["problem_level"],
            process_status=process["status"],
            process_next_step=process["next_step"],
            process_current_action_stage=process["current_stage"],
            process_next_action_stage=process["next_stage"],
            process_summary=process["summary"],
            process_reason=process["reason"],
            gravity=rounded_gravity,
            fallback_active=fallback_active,
            ready=liquid_temp is not None and target_temp is not None,
        )

    @property
    def configured_entities(self) -> dict[str, Any]:
        return {
            CONF_LIQUID_TEMP_ENTITY: _entity_from_entry(
                self.config_entry, CONF_LIQUID_TEMP_ENTITY, DEFAULT_LIQUID_TEMP_ENTITY
            ),
            CONF_CHAMBER_TEMP_ENTITY: _entity_from_entry(
                self.config_entry, CONF_CHAMBER_TEMP_ENTITY, DEFAULT_CHAMBER_TEMP_ENTITY
            ),
            CONF_RECIPE_TARGET_ENTITY: _entity_from_entry(
                self.config_entry, CONF_RECIPE_TARGET_ENTITY, DEFAULT_RECIPE_TARGET_ENTITY
            ),
            CONF_COLD_CRASH_ACTIVE_ENTITY: _entity_from_entry(
                self.config_entry, CONF_COLD_CRASH_ACTIVE_ENTITY, DEFAULT_COLD_CRASH_ACTIVE_ENTITY
            ),
            CONF_COLD_CRASH_TARGET_ENTITY: _entity_from_entry(
                self.config_entry, CONF_COLD_CRASH_TARGET_ENTITY, DEFAULT_COLD_CRASH_TARGET_ENTITY
            ),
            CONF_GRAVITY_ENTITY: _entity_from_entry(
                self.config_entry, CONF_GRAVITY_ENTITY, DEFAULT_GRAVITY_ENTITY
            ),
            CONF_KEGERATOR_AIR_TEMP_ENTITY: _entity_from_entry(
                self.config_entry, CONF_KEGERATOR_AIR_TEMP_ENTITY, DEFAULT_KEGERATOR_AIR_TEMP_ENTITY
            ),
            CONF_KEGERATOR_POWER_ENTITY: _entity_from_entry(
                self.config_entry, CONF_KEGERATOR_POWER_ENTITY, DEFAULT_KEGERATOR_POWER_ENTITY
            ),
            CONF_KEGERATOR_FAN_POWER_ENTITY: _entity_from_entry(
                self.config_entry,
                CONF_KEGERATOR_FAN_POWER_ENTITY,
                DEFAULT_KEGERATOR_FAN_POWER_ENTITY,
            ),
            CONF_FERMENTATION_HEAT_POWER_ENTITY: _entity_from_entry(
                self.config_entry,
                CONF_FERMENTATION_HEAT_POWER_ENTITY,
                DEFAULT_FERMENTATION_HEAT_POWER_ENTITY,
            ),
        }
