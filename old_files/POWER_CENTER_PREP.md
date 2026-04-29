# Power Center Prep

## Purpose

Power Center is planned for the future Shelly 4-outlet power strip.

For now, BrewAssistant v1.2 prepares the abstraction layer.

## Current abstraction

Dashboard should use:

```yaml
sensor.brewassistant_kegerator_power_w
binary_sensor.kegerator_compressor_active
binary_sensor.brewassistant_kegerator_power_sensor_ok
```

Not raw physical entities.

## Current temporary source

Example current source:

```yaml
sensor.extra_koksmaskin_switch_0_power
```

## Future Shelly source

When Shelly is installed, rename outlets clearly in Home Assistant.

Suggested outlet names:

```text
Outlet 1: Kegerator / Compressor
Outlet 2: Fermentation Heat
Outlet 3: Circulation Fan
Outlet 4: BrewAssistant Spare
```

Suggested future BrewAssistant entities:

```yaml
sensor.brewassistant_kegerator_power_w
sensor.brewassistant_chamber_heat_power_w
sensor.brewassistant_fan_power_w
sensor.brewassistant_total_power_w

switch.brewassistant_kegerator_power
switch.brewassistant_chamber_heat_power
switch.brewassistant_fan_power
switch.brewassistant_spare_power
```

## Safety recommendation

Before using Shelly outlets for heating/cooling control:

- verify max current rating
- verify device load
- avoid switching high loads too frequently
- keep physical safety limits active
- use manufacturer-supported wiring
- label outlets clearly

## v1.3 Power Center idea

Future card sections:

```text
Total Power
Kegerator Power
Heat Power
Fan Power
Spare Outlet
Compressor Runtime
Outlet Status
Power Alerts
```

Potential alerts:

```text
Compressor running too long
Unexpected power draw
Outlet unavailable
Fan off while cooling
Heater powered while chamber disabled
Total power too high
```
