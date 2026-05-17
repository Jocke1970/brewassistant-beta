"""Read-only smart fermentation recommendation helpers."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.core import HomeAssistant

_UNAVAILABLE_STATES = {"unknown", "unavailable", "none", ""}
_ON_STATES = {"on", "true", "yes", "active"}


@dataclass(slots=True)
class SmartRecommendationData:
    """Read-only recommendation snapshot."""

    summary: str
    heat: str
    cooling: str
    fan: str
    block_reason: str
    suggested_pulse_minutes: int
    mode: str
    enabled: bool
    heat_needed: bool
    heat_permitted: bool
    cooling_recommended: bool
    fan_recommended: bool
    rising_too_fast: bool


def _state_float(hass: HomeAssistant, entity_id: str) -> float | None:
    state = hass.states.get(entity_id)
    if state is None or state.state in _UNAVAILABLE_STATES:
        return None
    try:
        return float(state.state)
    except (TypeError, ValueError):
        return None


def _state_string(hass: HomeAssistant, entity_id: str) -> str | None:
    state = hass.states.get(entity_id)
    if state is None or state.state in _UNAVAILABLE_STATES:
        return None
    return str(state.state)


def _is_on(hass: HomeAssistant, entity_id: str) -> bool:
    state = hass.states.get(entity_id)
    return state is not None and state.state.lower() in _ON_STATES


def build_smart_recommendations(
    hass: HomeAssistant,
    *,
    liquid_temp: float | None,
    target_temp: float | None,
    delta: float | None,
    chamber_temp: float | None,
    fallback_active: bool,
    source: str,
) -> SmartRecommendationData:
    """Build a read-only smart fermentation recommendation snapshot."""
    enabled = _is_on(hass, "input_boolean.brewassistant_smart_fermentation_enabled")
    heat_allowed = _is_on(hass, "input_boolean.brewassistant_smart_heat_allowed")
    manual_override = _is_on(hass, "input_boolean.brewassistant_smart_manual_override")
    force_heat = _is_on(hass, "input_boolean.brewassistant_smart_force_heat")
    force_fan = _is_on(hass, "input_boolean.brewassistant_smart_force_fan")
    cooldown_active = _is_on(hass, "timer.brewassistant_smart_heat_cooldown")

    mode = _state_string(hass, "input_select.brewassistant_smart_fermentation_mode") or "Off"
    mode_norm = mode.lower()

    deadband = _state_float(hass, "input_number.brewassistant_smart_deadband_low") or 0.25
    min_pulse = _state_float(hass, "input_number.brewassistant_smart_min_heat_pulse_min") or 3
    max_pulse = _state_float(hass, "input_number.brewassistant_smart_max_heat_pulse_min") or 10
    max_rising = _state_float(hass, "input_number.brewassistant_smart_max_rising_rate") or 0.25
    chamber_offset = _state_float(hass, "input_number.brewassistant_smart_chamber_heat_safety_offset") or 2.0
    temp_rate = _state_float(hass, "sensor.brewassistant_smart_temp_rate")

    rising_too_fast = temp_rate is not None and temp_rate > max_rising

    if liquid_temp is None or target_temp is None or delta is None:
        return SmartRecommendationData(
            summary="Unavailable · missing temperature or target",
            heat="Unavailable",
            cooling="Unavailable",
            fan="Unavailable",
            block_reason="Missing temperature or target",
            suggested_pulse_minutes=int(min_pulse),
            mode=mode,
            enabled=enabled,
            heat_needed=False,
            heat_permitted=False,
            cooling_recommended=False,
            fan_recommended=False,
            rising_too_fast=rising_too_fast,
        )

    heat_needed = delta < -deadband
    cooling_recommended = delta > deadband
    heat_mode_ok = "heat" in mode_norm or "auto" in mode_norm
    cool_mode_ok = "cool" in mode_norm or "auto" in mode_norm

    suggested_pulse = int(min_pulse)
    if heat_needed:
        ratio = min(1.0, abs(delta) / 2.0)
        suggested_pulse = round(min_pulse + ((max_pulse - min_pulse) * ratio))
        suggested_pulse = int(max(min_pulse, min(max_pulse, suggested_pulse)))

    if not enabled:
        block = "Smart fermentation disabled"
    elif manual_override:
        block = "Manual override active"
    elif force_heat:
        block = "Manual heat request active"
    elif not heat_allowed:
        block = "Heat not allowed"
    elif not heat_mode_ok:
        block = "Mode does not allow heat"
    elif not heat_needed:
        block = "Heat not needed"
    elif rising_too_fast:
        block = "Temperature rising too fast"
    elif cooldown_active:
        block = "Heat cooldown active"
    elif chamber_temp is not None and chamber_temp > target_temp + chamber_offset:
        block = "Chamber already warm"
    elif fallback_active:
        block = "Fallback temperature active"
    else:
        block = "Heat permitted"

    heat_permitted = heat_needed and block == "Heat permitted"

    if force_heat:
        heat = "Manual heat request"
    elif heat_permitted:
        heat = f"Heat pulse recommended · {suggested_pulse} min"
    elif heat_needed:
        heat = f"Heat needed but blocked · {block}"
    else:
        heat = "No heat needed"

    if cooling_recommended and enabled and cool_mode_ok:
        cooling = "Cooling recommended"
    elif cooling_recommended:
        cooling = "Cooling would help"
    else:
        cooling = "No cooling needed"

    fan_recommended = force_fan or cooling_recommended or abs(delta) > 0.75
    if force_fan:
        fan = "Manual fan request"
    elif fan_recommended and cooling_recommended:
        fan = "Fan assist recommended for cooling"
    elif fan_recommended:
        fan = "Fan assist recommended"
    else:
        fan = "No fan assist needed"

    summary = f"{mode} · Δ {delta:+.2f} °C · {heat} · {cooling} · {fan} · source {source}"

    return SmartRecommendationData(
        summary=summary,
        heat=heat,
        cooling=cooling,
        fan=fan,
        block_reason=block,
        suggested_pulse_minutes=suggested_pulse,
        mode=mode,
        enabled=enabled,
        heat_needed=heat_needed,
        heat_permitted=heat_permitted,
        cooling_recommended=cooling_recommended,
        fan_recommended=fan_recommended,
        rising_too_fast=rising_too_fast,
    )
