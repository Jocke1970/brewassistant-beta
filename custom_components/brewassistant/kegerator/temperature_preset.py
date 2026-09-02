"""Kegerator temperature presets and target application.

The restored preset select is the persistent source of truth.  Kegerator
consumers can read the selected numeric target without coupling to dashboard
state or to another BrewAssistant backend.
"""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

KEGERATOR_CLIMATE = "climate.kegerator_kylskap"
KEGERATOR_PRESET_SELECT = "select.brewassistant_kegerator_temperature_preset"

PRESET_COLD_CRASH = "Cold Crash"
PRESET_STORAGE = "Storage"
PRESET_SERVING = "Serving"

PRESET_TARGETS: dict[str, float] = {
    PRESET_COLD_CRASH: 2.0,
    PRESET_STORAGE: 3.0,
    PRESET_SERVING: 4.0,
}
PRESET_OPTIONS = list(PRESET_TARGETS)
DEFAULT_PRESET = PRESET_SERVING
DEFAULT_TARGET = PRESET_TARGETS[DEFAULT_PRESET]

INVALID_STATES = {"unknown", "unavailable", "none", ""}


def target_for_preset(preset: str | None) -> float:
    """Return the numeric target for one preset, with a serving fallback."""
    return float(PRESET_TARGETS.get(str(preset), DEFAULT_TARGET))


def selected_preset(hass: HomeAssistant) -> str:
    """Return the restored/current preset state."""
    state = hass.states.get(KEGERATOR_PRESET_SELECT)
    if state is not None and state.state in PRESET_TARGETS:
        return str(state.state)
    return DEFAULT_PRESET


def selected_target(hass: HomeAssistant) -> float:
    """Return the selected kegerator base target."""
    return target_for_preset(selected_preset(hass))


def preset_from_temperature(value: float | None) -> str:
    """Return the matching preset for an exact configured target."""
    if value is None:
        return DEFAULT_PRESET
    for preset, target in PRESET_TARGETS.items():
        if abs(float(value) - target) < 0.05:
            return preset
    return DEFAULT_PRESET


async def async_apply_temperature_preset(
    hass: HomeAssistant,
    preset: str,
    *,
    ensure_cool: bool = True,
) -> dict[str, Any]:
    """Apply one kegerator preset to the physical climate controller."""
    normalized = preset if preset in PRESET_TARGETS else DEFAULT_PRESET
    target = target_for_preset(normalized)
    climate = hass.states.get(KEGERATOR_CLIMATE)

    result: dict[str, Any] = {
        "preset": normalized,
        "target_temperature": target,
        "climate_entity": KEGERATOR_CLIMATE,
        "before_state": climate.state if climate is not None else None,
        "result": "missing_climate" if climate is None else "attempting",
    }
    if climate is None:
        return result

    if ensure_cool and climate.state in {"off", "unknown", "unavailable", "none", ""}:
        await hass.services.async_call(
            "climate",
            "set_hvac_mode",
            {"entity_id": KEGERATOR_CLIMATE, "hvac_mode": "cool"},
            blocking=True,
        )

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": KEGERATOR_CLIMATE, "temperature": target},
        blocking=True,
    )

    after = hass.states.get(KEGERATOR_CLIMATE)
    result["after_state"] = after.state if after is not None else None
    result["after_target"] = (
        after.attributes.get("temperature") if after is not None else None
    )
    result["result"] = "applied"
    return result
