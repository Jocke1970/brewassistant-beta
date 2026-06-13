# Kegerator Fan Backend

BrewAssistant Kegerator Fan Backend infers compressor/fan state from existing Home Assistant entities and optionally controls the kegerator circulation fan.

It is intended as a small Python-owned replacement for old YAML/input-helper fan automations. It keeps compressor/cooling target responsibility in the Home Assistant climate layer.

## Source entities

```text
climate.kegerator_kylskap
sensor.kyl_temperatur_4
sensor.brewassistant_kegerator_air_temperature_average
sensor.kegerator_power
switch.kegerator_fan
sensor.kegerator_fan_power
climate.fermentation_chamber
```

## Exposed control

The backend is exposed through a Home Assistant switch created by BrewAssistant:

```text
switch.brewassistant_kegerator_fan_auto_enabled
```

Preferred Home Assistant entity IDs should use the clean BrewAssistant namespace without area/device prefixes. If old prefixed entities exist locally, clean them through Home Assistant's Entity Registry UI before validating dashboards.

The switch is off by default.

When enabled, BrewAssistant may turn `switch.kegerator_fan` on/off based on compressor activity, climate cooling request, temperature delta, warming trend and afterrun.

## Safety split

```text
climate.kegerator_kylskap owns compressor/cooling target control.
BrewAssistant infers compressor activity from sensor.kegerator_power.
BrewAssistant fan-auto controls only switch.kegerator_fan.
Disabling fan-auto does not force the fan off.
```

The backend must not directly toggle `switch.kegerator` as part of fan automation.

## Runtime states

```text
off          climate is off or unavailable
cooling      compressor is inferred active from power draw
afterrun     compressor has stopped, but fan continues for the configured afterrun window
circulating  fan is running while compressor is idle
standby      no fan action is currently needed
```

## Decision rules

```text
Compressor active: sensor.kegerator_power > 20 W
Fan running: switch.kegerator_fan is on or sensor.kegerator_fan_power > 2 W
```

Fan should run when:

```text
- climate is enabled and compressor is active
- afterrun is active after compressor stop
- climate requests cooling
- air temperature is too warm
- air temperature trend is warming at a reasonable rate
```

Fan should stop when:

```text
- climate is off
- chamber is too cold and compressor is idle
- afterrun has expired and no circulation reason remains
```

## Built-in thresholds

```text
compressor threshold: 20 W
fan power threshold: 2 W
default afterrun: 10 min
summer/warm-room afterrun recommendation: 2-3 min
too warm delta: +0.8 °C
too cold delta: -0.8 °C
warming trend: +0.20 °C/h
max reasonable warming trend: +5.00 °C/h
interval: 30 s
```

The max reasonable warming trend guard prevents restart/statistics spikes from waking the fan automation after Home Assistant restarts.

## Apply behavior

When fan-auto is enabled, the switch performs one backend tick every 30 seconds.

If the backend decides that a fan action is needed, it calls Home Assistant switch services with blocking service calls:

```text
fan_action: turn_on_fan  -> switch.turn_on switch.kegerator_fan
fan_action: turn_off_fan -> switch.turn_off switch.kegerator_fan
fan_action: none         -> no service call
```

Diagnostics are exposed as attributes on the fan-auto switch.

Important attributes:

```text
status
summary
compressor_active
afterrun_active
afterrun_remaining_minutes
fan_running
fan_should_run
fan_action
fan_reason
warning_level
```

## Validated test flow

Initial live validation covered:

```text
compressor active -> fan_should_run True -> fan remains on
compressor stops  -> status afterrun -> fan remains on during afterrun
compressor restarts during afterrun -> status cooling -> fan_reason compressor_active
manual switch.turn_off switch.kegerator_fan works
restart trend spike ignored by max reasonable warming guard
```

Still pending:

```text
full automatic fan turn-off after afterrun expiry
longer multi-cycle validation after HA restart
```
