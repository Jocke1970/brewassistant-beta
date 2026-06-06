# Kegerator Fan Backend

BrewAssistant Kegerator Fan Backend infers compressor/fan state from existing Home Assistant entities and optionally controls the kegerator fan.

## Source entities

```text
climate.kegerator_kylskap
sensor.kyl_temperatur_4
sensor.brewassistant_kegerator_air_temperature_average
sensor.kegerator_power
switch.kegerator_fan
sensor.kegerator_fan_power
```

## Exposed control

```text
switch.brewassistant_kegerator_fan_auto_enabled
```

The switch is off by default.

When enabled, BrewAssistant may turn `switch.kegerator_fan` on/off based on compressor activity, climate cooling request, temperature delta, warming trend and afterrun.

## Safety split

```text
climate.kegerator_kylskap owns compressor/cooling target control.
BrewAssistant infers compressor activity from sensor.kegerator_power.
BrewAssistant fan-auto controls only switch.kegerator_fan.
Disabling fan-auto does not force the fan off.
```

## Built-in thresholds

```text
compressor threshold: 20 W
fan power threshold: 2 W
afterrun: 10 min
too warm delta: +0.8 °C
too cold delta: -0.8 °C
warming trend: +0.20 °C/h
interval: 30 s
```

Runtime diagnostics are exposed as attributes on `switch.brewassistant_kegerator_fan_auto_enabled`.
