# BrewZilla Temperature Sources

BrewAssistant now separates BrewZilla temperature readings into two roles:

- Mash temperature: the process/mash temperature used by the operator and learning logic.
- Wort temperature: the BrewZilla internal kettle/wort thermometer.
- Delta: mash temperature minus wort temperature.

## Entities

Operator selection:

- `select.brewassistant_brewzilla_mash_temperature_source`

Resolved sensors:

- `sensor.brewassistant_brewzilla_mash_temperature`
- `sensor.brewassistant_brewzilla_wort_temperature`
- `sensor.brewassistant_brewzilla_temperature_delta_mash_wort`
- `sensor.brewassistant_brewzilla_mash_temperature_source`
- `sensor.brewassistant_brewzilla_mash_temperature_source_entity`

## Mash source options

The mash source selector supports:

- Auto
- RAPT BLE Thermometer
- BrewZilla Control Device
- BrewZilla Internal

Auto mode prefers the external BLE/control-device temperature when available and falls back to the internal BrewZilla temperature when needed.

## Wort source

Wort temperature is always the BrewZilla internal thermometer:

- `sensor.brewzilla_temperature`

## RAPT Cloud Link

The external RAPT BLE Thermometer is consumed through RAPT Cloud Link when BrewZilla/RAPT Cloud exposes the control-device temperature. BrewAssistant does not read the BLE thermometer locally.

RAPT Cloud Link should expose control-device diagnostics so the operator can see whether root or telemetry data was selected, and whether a value was rejected as unavailable.

## BrewZilla Learning

BrewZilla Learning uses the same Python resolver as the dashboard sensors.

- Ramp and mash-hold context use resolved mash temperature.
- Boil, cooling and other kettle contexts use the internal wort/kettle temperature.

## Dashboard policy

Dashboard cards should show these values separately:

- Mash = selected or Auto source.
- Wort = BrewZilla Internal.
- Delta = Mash minus Wort.

The dashboard may expose the select control, but source selection and fallback logic belong in Python.
