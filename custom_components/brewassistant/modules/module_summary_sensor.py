"""Read-only module summary sensor for BrewAssistant."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity

from ..const import DOMAIN
from ..coordinator import BrewAssistantCoordinator
from ..entity import BrewAssistantEntity
from .registry import iter_module_manifests


def _manifest_rows() -> list[dict[str, Any]]:
    """Return module manifest rows suitable for HA attributes."""
    rows: list[dict[str, Any]] = []

    for manifest in iter_module_manifests():
        capabilities = [
            {
                "key": capability.key,
                "name": capability.name,
                "type": capability.capability_type.value,
                "default_policy": capability.default_policy.value,
                "description": capability.description,
            }
            for capability in manifest.capabilities
        ]

        rows.append(
            {
                "key": manifest.key,
                "name": manifest.name,
                "type": manifest.module_type.value,
                "enabled_by_default": manifest.enabled_by_default,
                "default_status": manifest.default_status.value,
                "required_sources": list(manifest.required_sources),
                "optional_sources": list(manifest.optional_sources),
                "capability_count": len(manifest.capabilities),
                "capabilities": capabilities,
                "notes": list(manifest.notes),
            }
        )

    return rows


def _summary(rows: list[dict[str, Any]]) -> str:
    """Build a compact module summary state."""
    enabled = [row for row in rows if row["enabled_by_default"]]
    disabled = [row for row in rows if not row["enabled_by_default"]]

    base_ready = sum(
        1
        for row in enabled
        if row["default_status"] in {"enabled_ready", "active"}
    )
    missing_sources = sum(
        1
        for row in enabled
        if row["default_status"] == "enabled_missing_sources"
    )

    if missing_sources:
        return f"Base partial · {base_ready} ready · {missing_sources} missing sources · {len(disabled)} optional disabled"

    return f"Base ready · {len(enabled)} enabled · {len(disabled)} optional disabled"


class BrewAssistantModuleSummarySensor(BrewAssistantEntity, SensorEntity):
    """Read-only module/capability manifest summary."""

    _attr_has_entity_name = False

    def __init__(self, coordinator: BrewAssistantCoordinator) -> None:
        """Initialize the module summary sensor."""
        super().__init__(coordinator, "module_summary")
        self._attr_name = "BrewAssistant Module Summary"
        self._attr_suggested_object_id = f"{DOMAIN}_module_summary"
        self._attr_icon = "mdi:puzzle-outline"

    @property
    def native_value(self) -> str:
        """Return a compact module manifest summary."""
        return _summary(_manifest_rows())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return module manifest attributes."""
        rows = _manifest_rows()

        enabled = [row["key"] for row in rows if row["enabled_by_default"]]
        disabled = [row["key"] for row in rows if not row["enabled_by_default"]]

        return {
            "source": "module_manifest",
            "behavior": "read_only_passive",
            "runtime_effect": "none",
            "enabled_by_default_count": len(enabled),
            "optional_disabled_count": len(disabled),
            "total_modules": len(rows),
            "enabled_by_default": enabled,
            "optional_disabled": disabled,
            "modules": {row["key"]: row for row in rows},
        }


def create_module_summary_sensors(
    coordinator: BrewAssistantCoordinator,
) -> list[SensorEntity]:
    """Create module summary sensors."""
    return [BrewAssistantModuleSummarySensor(coordinator)]
