"""Coordinator for BrewAssistant normalized state."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_CHAMBER_TEMP_ENTITY,
    CONF_COLD_CRASH_ACTIVE_ENTITY,
    CONF_COLD_CRASH_TARGET_ENTITY,
    CONF_GRAVITY_ENTITY,
    CONF_LIQUID_TEMP_ENTITY,
    CONF_RECIPE_TARGET_ENTITY,
    DEFAULT_CHAMBER_TEMP_ENTITY,
    DEFAULT_COLD_CRASH_ACTIVE_ENTITY,
    DEFAULT_COLD_CRASH_TARGET_ENTITY,
    DEFAULT_GRAVITY_ENTITY,
    DEFAULT_LIQUID_TEMP_ENTITY,
    DEFAULT_RECIPE_TARGET_ENTITY,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)
_UNAVAILABLE_STATES = {"unknown", "unavailable", "none", ""}
_ON_STATES = {"on", "true", "yes", "active"}


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
    gravity: float | None
    fallback_active: bool
    ready: bool


def _entity_from_entry(entry: ConfigEntry, key: str, fallback: str) -> str:
    """Return an entity id from entry options/data with a fallback."""
    return str(entry.options.get(key) or entry.data.get(key) or fallback)


def _state_float(hass: HomeAssistant, entity_id: str | None) -> float | None:
    """Read a Home Assistant state as float, returning None when invalid."""
    if not entity_id:
        return None

    state = hass.states.get(entity_id)
    if state is None or state.state in _UNAVAILABLE_STATES:
        return None

    try:
        return float(state.state)
    except (TypeError, ValueError):
        return None


def _state_is_on(hass: HomeAssistant, entity_id: str | None) -> bool:
    """Return whether an entity state should be treated as active/on."""
    if not entity_id:
        return False

    state = hass.states.get(entity_id)
    if state is None:
        return False

    return state.state.lower() in _ON_STATES


def _format_temp(value: float | None) -> str:
    """Format a temperature for status summaries."""
    if value is None:
        return "—"
    return f"{value:.1f}"


def _format_gravity(value: float | None) -> str:
    """Format specific gravity for status summaries."""
    if value is None:
        return "—"
    return f"{value:.3f}"


def _temperature_context(
    liquid_temp: float | None,
    target_temp: float | None,
    delta: float | None,
    source: str,
    fallback_active: bool,
    target_mode: str,
) -> dict[str, str]:
    """Build dashboard-friendly temperature status fields."""
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
        status = "On target"
        severity = "ok"
        icon_hint = "check-circle"
        color_hint = "green"
        problem_level = "ok"
    elif abs_delta <= 0.5:
        status = "Slight offset"
        severity = "info"
        icon_hint = "delta"
        color_hint = "amber"
        problem_level = "info"
    else:
        status = "Temp offset"
        severity = "warning"
        icon_hint = "thermometer-alert"
        color_hint = "red"
        problem_level = "warning"

    if fallback_active:
        status = "Fallback active"
        severity = "warning" if severity == "ok" else severity
        icon_hint = "fridge-alert"
        color_hint = "amber"
        problem_level = "warning" if problem_level == "ok" else problem_level

    direction = "above" if delta > 0 else "below" if delta < 0 else "on"
    source_summary = f"{source}{' · fallback' if fallback_active else ''}"
    status_summary = (
        f"{target_mode} · {_format_temp(liquid_temp)} → {_format_temp(target_temp)} °C "
        f"· Δ {delta:+.2f} °C · {direction} target · {source_summary}"
    )

    return {
        "status": status,
        "severity": severity,
        "icon_hint": icon_hint,
        "color_hint": color_hint,
        "source_summary": source_summary,
        "status_summary": status_summary,
        "problem_level": problem_level,
    }


class BrewAssistantCoordinator(DataUpdateCoordinator[BrewAssistantData]):
    """Collect normalized BrewAssistant state from existing HA entities."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.config_entry = entry

    async def _async_update_data(self) -> BrewAssistantData:
        """Fetch one normalized snapshot from Home Assistant state machine."""
        liquid_entity = _entity_from_entry(
            self.config_entry,
            CONF_LIQUID_TEMP_ENTITY,
            DEFAULT_LIQUID_TEMP_ENTITY,
        )
        chamber_entity = _entity_from_entry(
            self.config_entry,
            CONF_CHAMBER_TEMP_ENTITY,
            DEFAULT_CHAMBER_TEMP_ENTITY,
        )
        target_entity = _entity_from_entry(
            self.config_entry,
            CONF_RECIPE_TARGET_ENTITY,
            DEFAULT_RECIPE_TARGET_ENTITY,
        )
        cold_crash_active_entity = _entity_from_entry(
            self.config_entry,
            CONF_COLD_CRASH_ACTIVE_ENTITY,
            DEFAULT_COLD_CRASH_ACTIVE_ENTITY,
        )
        cold_crash_target_entity = _entity_from_entry(
            self.config_entry,
            CONF_COLD_CRASH_TARGET_ENTITY,
            DEFAULT_COLD_CRASH_TARGET_ENTITY,
        )
        gravity_entity = _entity_from_entry(
            self.config_entry,
            CONF_GRAVITY_ENTITY,
            DEFAULT_GRAVITY_ENTITY,
        )

        pill_temp = _state_float(self.hass, liquid_entity)
        chamber_temp = _state_float(self.hass, chamber_entity)
        recipe_target_temp = _state_float(self.hass, target_entity)
        cold_crash_target_temp = _state_float(self.hass, cold_crash_target_entity)
        gravity = _state_float(self.hass, gravity_entity)

        cold_crash_active = _state_is_on(self.hass, cold_crash_active_entity)
        if cold_crash_active and cold_crash_target_temp is not None:
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

        delta = None
        if liquid_temp is not None and target_temp is not None:
            delta = round(liquid_temp - target_temp, 2)

        rounded_liquid = round(liquid_temp, 2) if liquid_temp is not None else None
        rounded_chamber = round(chamber_temp, 2) if chamber_temp is not None else None
        rounded_target = round(target_temp, 2) if target_temp is not None else None
        rounded_gravity = round(gravity, 3) if gravity is not None else None
        context = _temperature_context(
            rounded_liquid,
            rounded_target,
            delta,
            source,
            fallback_active,
            target_mode,
        )

        if rounded_gravity is not None:
            status_summary = f"{context['status_summary']} · SG {_format_gravity(rounded_gravity)}"
        else:
            status_summary = context["status_summary"]

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
            gravity=rounded_gravity,
            fallback_active=fallback_active,
            ready=liquid_temp is not None and target_temp is not None,
        )

    @property
    def configured_entities(self) -> dict[str, Any]:
        """Return configured source entities."""
        return {
            CONF_LIQUID_TEMP_ENTITY: _entity_from_entry(
                self.config_entry,
                CONF_LIQUID_TEMP_ENTITY,
                DEFAULT_LIQUID_TEMP_ENTITY,
            ),
            CONF_CHAMBER_TEMP_ENTITY: _entity_from_entry(
                self.config_entry,
                CONF_CHAMBER_TEMP_ENTITY,
                DEFAULT_CHAMBER_TEMP_ENTITY,
            ),
            CONF_RECIPE_TARGET_ENTITY: _entity_from_entry(
                self.config_entry,
                CONF_RECIPE_TARGET_ENTITY,
                DEFAULT_RECIPE_TARGET_ENTITY,
            ),
            CONF_COLD_CRASH_ACTIVE_ENTITY: _entity_from_entry(
                self.config_entry,
                CONF_COLD_CRASH_ACTIVE_ENTITY,
                DEFAULT_COLD_CRASH_ACTIVE_ENTITY,
            ),
            CONF_COLD_CRASH_TARGET_ENTITY: _entity_from_entry(
                self.config_entry,
                CONF_COLD_CRASH_TARGET_ENTITY,
                DEFAULT_COLD_CRASH_TARGET_ENTITY,
            ),
            CONF_GRAVITY_ENTITY: _entity_from_entry(
                self.config_entry,
                CONF_GRAVITY_ENTITY,
                DEFAULT_GRAVITY_ENTITY,
            ),
        }
