# RAPT Cloud Link patch: BrewZilla external/BLE temperature discovery

Target repository:

```text
berra200/home-assistant-rapt-cloud-link
```

Target file:

```text
custom_components/rapt_cloud_link/sensor.py
```

Purpose:

```text
Expose possible external/BLE/probe temperature values from the BrewZilla API payload.
```

Why:

The current BrewZilla temperature sensor only exposes the internal BrewZilla temperature from:

```python
device.get("temperature")
```

If a RAPT BLE Thermometer is connected through BrewZilla, its value may be present somewhere else in the `/BrewZillas/GetBrewZillas` payload, but the integration currently does not expose it.

Recommended first patch:

```text
1. Add BrewZilla External Temperature diagnostic sensor.
2. Add BrewZilla Raw Diagnostics diagnostic sensor.
3. Add external temperature candidates as attributes on the existing BrewZilla Temperature sensor.
4. Add fallback for BondedDeviceTemperatureSensor to read telemetry[0].temperature if top-level temperature is missing.
```

Suggested helpers:

```python
from typing import Any
from homeassistant.helpers.entity import EntityCategory

_TEMP_FIELD_HINTS = (
    "temp",
    "probe",
    "external",
    "bluetooth",
    "ble",
    "therm",
    "sensor",
    "bonded",
    "accessory",
    "telemetry",
)

_EXTERNAL_TEMP_PRIORITY_KEYS = (
    "externalTemperature",
    "externalTemp",
    "probeTemperature",
    "probeTemp",
    "bluetoothTemperature",
    "bluetoothTemp",
    "bleTemperature",
    "bleTemp",
    "sensorTemperature",
    "temperature2",
    "temp2",
    "auxTemperature",
    "accessoryTemperature",
    "bondedTemperature",
)


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _interesting_brewzilla_fields(value: Any, *, path: str = "device", depth: int = 0) -> dict[str, Any]:
    if depth > 5:
        return {}

    fields: dict[str, Any] = {}
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            key_l = str(key).lower()
            path_l = child_path.lower()
            if isinstance(child, (dict, list)):
                fields.update(_interesting_brewzilla_fields(child, path=child_path, depth=depth + 1))
                continue
            if any(hint in key_l or hint in path_l for hint in _TEMP_FIELD_HINTS):
                fields[child_path] = child
    elif isinstance(value, list):
        for idx, child in enumerate(value[:8]):
            fields.update(_interesting_brewzilla_fields(child, path=f"{path}[{idx}]", depth=depth + 1))
    return fields


def _external_temperature_candidates(device: dict[str, Any]) -> dict[str, float]:
    candidates: dict[str, float] = {}

    for key in _EXTERNAL_TEMP_PRIORITY_KEYS:
        value = _safe_float(device.get(key))
        if value is not None:
            candidates[f"device.{key}"] = value

    interesting = _interesting_brewzilla_fields(device)
    for path, raw_value in interesting.items():
        value = _safe_float(raw_value)
        if value is None:
            continue
        path_l = path.lower()
        if path_l == "device.temperature":
            continue
        if "target" in path_l or "util" in path_l or "gravity" in path_l or "battery" in path_l:
            continue
        if any(hint in path_l for hint in ("external", "probe", "bluetooth", "ble", "therm", "accessory", "bonded", "telemetry")):
            candidates[path] = value

    return candidates


def _first_external_temperature_candidate(device: dict[str, Any]) -> tuple[str | None, float | None]:
    candidates = _external_temperature_candidates(device)
    if not candidates:
        return None, None
    first_path = next(iter(candidates))
    return first_path, candidates[first_path]
```

Add these sensors to the BrewZilla section in `async_setup_entry`:

```python
sensors.append(BrewZillaExternalTemperatureSensor(brewzilla_coordinator, device_id))
sensors.append(BrewZillaRawDiagnosticsSensor(brewzilla_coordinator, device_id))
```

Add this attribute block to `BrewZillaTemperatureSensor`:

```python
    @property
    def extra_state_attributes(self):
        device = self.coordinator.data.get(self._device_id, {})
        candidates = _external_temperature_candidates(device) if isinstance(device, dict) else {}
        return {
            "source": "BrewZilla API temperature",
            "internal_temperature_field": "device.temperature",
            "external_temperature_candidate_count": len(candidates),
            "external_temperature_candidates": candidates,
        }
```

Add sensor class:

```python
class BrewZillaExternalTemperatureSensor(BaseRaptSensor):
    """Potential BrewZilla external/BLE/probe temperature sensor."""

    def __init__(self, coordinator, device_id: str):
        super().__init__(
            coordinator,
            device_id,
            model="BrewZilla",
            name_suffix="External Temperature",
            unique_suffix="external_temperature",
            unit="°C",
        )
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def unit_of_measurement(self):
        unit = self.coordinator.config_entry.data.get(CONF_TEMPERATURE_UNIT, DEFAULT_TEMPERATURE_UNIT)
        return "°F" if unit == "F" else "°C"

    @property
    def native_value(self):
        device = self.coordinator.data.get(self._device_id)
        if isinstance(device, dict):
            _path, value = _first_external_temperature_candidate(device)
            return round(value, 1) if value is not None else None
        return None

    @property
    def extra_state_attributes(self):
        device = self.coordinator.data.get(self._device_id, {})
        candidates = _external_temperature_candidates(device) if isinstance(device, dict) else {}
        selected_path, selected_value = _first_external_temperature_candidate(device) if isinstance(device, dict) else (None, None)
        return {
            "source": "BrewZilla API external temperature discovery",
            "selected_path": selected_path,
            "selected_value": selected_value,
            "candidate_count": len(candidates),
            "candidates": candidates,
            "note": "Diagnostic discovery sensor. Verify selected_path before using this as control input.",
        }
```

Add diagnostics class:

```python
class BrewZillaRawDiagnosticsSensor(BaseRaptSensor):
    """BrewZilla raw payload diagnostics for discovering BLE/probe fields."""

    def __init__(self, coordinator, device_id: str):
        super().__init__(
            coordinator,
            device_id,
            model="BrewZilla",
            name_suffix="Raw Diagnostics",
            unique_suffix="raw_diagnostics",
        )
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self):
        device = self.coordinator.data.get(self._device_id)
        if not isinstance(device, dict):
            return "no_data"
        candidates = _external_temperature_candidates(device)
        return f"{len(device.keys())} keys · {len(candidates)} temp candidates"

    @property
    def extra_state_attributes(self):
        device = self.coordinator.data.get(self._device_id, {})
        if not isinstance(device, dict):
            return {"source": "BrewZilla API raw diagnostics", "available": False}
        interesting = _interesting_brewzilla_fields(device)
        candidates = _external_temperature_candidates(device)
        return {
            "source": "BrewZilla API raw diagnostics",
            "available": True,
            "raw_keys": sorted(str(key) for key in device.keys()),
            "interesting_field_count": len(interesting),
            "interesting_fields": interesting,
            "external_temperature_candidate_count": len(candidates),
            "external_temperature_candidates": candidates,
        }
```

Patch `BondedDeviceTemperatureSensor.native_value`:

```python
    @property
    def native_value(self):
        device = self.coordinator.data.get(self._device_id)
        if device:
            if device.get("temperature") is not None:
                return round(device.get("temperature"), 1)
            if "telemetry" in device and device["telemetry"]:
                value = device["telemetry"][0].get("temperature")
                return round(value, 1) if value is not None else None
        return None
```

Expected entities after restart:

```text
sensor.<brewzilla_name>_external_temperature
sensor.<brewzilla_name>_raw_diagnostics
```

Use `Raw Diagnostics` attributes to identify the real RAPT/BrewZilla field name before using the external temp value for BrewAssistant control logic.
