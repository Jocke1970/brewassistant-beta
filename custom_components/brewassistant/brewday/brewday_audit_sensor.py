"""Brewday Audit sensor entities."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass

from .brewday_audit import build_brewday_audit_snapshot
from ..const import DOMAIN
from ..coordinator import BrewAssistantCoordinator
from ..entity import BrewAssistantEntity


AUDIT_SENSORS: dict[str, dict[str, Any]] = {
    "brewday_event_log_summary": {"field": "status", "include_events": True},
    "brewday_event_log_event_count": {
        "field": "event_count",
        "unit": "events",
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "brewday_event_log_last_event": {"field": "last_event_type"},
    "brewday_event_log_last_step": {"field": "last_step"},
    "brewday_event_log_last_target": {"field": "last_target"},
}


HEAVY_ATTRIBUTE_KEYS = {"events"}


def _display_name_from_key(key: str) -> str:
    return f"BrewAssistant {key.replace('_', ' ').title()}"


def _lightweight_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Return event-log diagnostics without repeating the full event list.

    The summary sensor keeps the complete event list for dashboard/event-log UI.
    Secondary sensors expose the same counters/status diagnostics but omit heavy
    nested attributes so template rendering and the HA state machine stay lighter.
    """
    return {key: value for key, value in snapshot.items() if key not in HEAVY_ATTRIBUTE_KEYS}


def create_brewday_audit_sensors(coordinator: BrewAssistantCoordinator) -> list[SensorEntity]:
    """Create Brewday Audit sensors."""
    return [BrewAssistantBrewdayAuditSensor(coordinator, key) for key in AUDIT_SENSORS]


class BrewAssistantBrewdayAuditSensor(BrewAssistantEntity, SensorEntity):
    """Read-only Brewday Audit sensor."""

    _attr_has_entity_name = False

    def __init__(self, coordinator: BrewAssistantCoordinator, key: str) -> None:
        super().__init__(coordinator, key)
        self._key = key
        self._field = str(AUDIT_SENSORS[key]["field"])
        self._include_events = bool(AUDIT_SENSORS[key].get("include_events", False))
        self._attr_name = _display_name_from_key(key)
        self._attr_suggested_object_id = f"{DOMAIN}_{key}"
        self._attr_native_unit_of_measurement = AUDIT_SENSORS[key].get("unit")
        self._attr_state_class = AUDIT_SENSORS[key].get("state_class")

    @property
    def native_value(self) -> Any:
        return build_brewday_audit_snapshot(self.coordinator.hass).get(self._field)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        snapshot = build_brewday_audit_snapshot(self.coordinator.hass)
        if self._include_events:
            return snapshot
        attrs = _lightweight_snapshot(snapshot)
        attrs["events_attribute_entity"] = f"sensor.{DOMAIN}_brewday_event_log_summary"
        return attrs
