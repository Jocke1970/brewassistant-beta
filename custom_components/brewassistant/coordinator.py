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

        return BrewAssistantData(
            liquid_temperature=round(liquid_temp, 2) if liquid_temp is not None else None,
            liquid_temperature_source=source,
            liquid_temperature_entity=source_entity,
            chamber_temperature=round(chamber_temp, 2) if chamber_temp is not None else None,
            recipe_target_temperature=round(target_temp, 2) if target_temp is not None else None,
            recipe_target_temperature_entity=effective_target_entity,
            temperature_target_mode=target_mode,
            temperature_delta=delta,
            gravity=round(gravity, 3) if gravity is not None else None,
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
