# Problem Center v1.1

## Purpose

Problem Center gives a single overview of BrewAssistant health.

It answers:

```text
Is anything wrong right now?
Which subsystem needs attention?
Can I start or continue brewing?
```

## Main entities

```yaml
sensor.brewassistant_problem_count
sensor.brewassistant_health_status
binary_sensor.brewassistant_any_problem_active
```

## Health status logic

```text
0 problems      → OK
1-2 problems    → Warning
3+ problems     → Critical
```

## Recommended checks

### Availability checks

```yaml
binary_sensor.brewassistant_kegerator_power_sensor_ok
binary_sensor.brewassistant_kegerator_temperature_sensor_ok
binary_sensor.brewassistant_kegerator_climate_ok
binary_sensor.brewassistant_fermentation_chamber_ok
binary_sensor.brewassistant_rapt_pill_temperature_ok
binary_sensor.brewassistant_rapt_pill_gravity_ok
binary_sensor.brewassistant_brewfather_batch_ok
binary_sensor.brewassistant_rapt_pill_battery_sensor_ok
```

### Problem checks

```yaml
binary_sensor.brewassistant_kegerator_too_warm
binary_sensor.brewassistant_kegerator_too_cold
binary_sensor.brewassistant_fermentation_chamber_too_warm
binary_sensor.brewassistant_fermentation_chamber_too_cold
binary_sensor.brewassistant_compressor_running_long
binary_sensor.brewassistant_rapt_pill_battery_low
binary_sensor.brewassistant_kegerator_temperature_sensor_battery_low
```

## Battery handling

### RAPT Pill

Entity:

```yaml
sensor.yellow_pill_battery
```

Known issue: this sensor may report `0` even when the battery is nearly full.

Recommended logic:

```yaml
state: >
  {% set batt = states('sensor.yellow_pill_battery') | float(none) %}
  {{ batt is not none and batt > 0 and batt < 20 }}
```

This ignores `0` as a low-battery trigger.

### Kegerator temperature sensor

Entity:

```yaml
sensor.kyl_batteri_4
```

Recommended threshold:

```text
Low battery below 20%
```

## Dashboard tiles

Problem Center currently shows:

```text
Kegerator
Chamber
RAPT SG
Brewfather
Battery
Compressor
```

## Common mismatch issue

If the top card shows:

```text
Warning · Active problems: 1
```

but the list says:

```text
No active problems
```

then `sensor.brewassistant_problem_count` is counting an entity that the dashboard JavaScript list does not include.

Fix: add the missing entity to the Active Problems card.
