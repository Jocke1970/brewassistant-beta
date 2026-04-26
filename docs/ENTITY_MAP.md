# Entity Map

This file documents the current BrewAssistant v4 entity assumptions.

Update this file whenever physical sensors or helpers are renamed.

## Physical / integration entities currently used

### Kegerator

```yaml
climate.kegerator_kylskap
sensor.kyl_temperatur_4
sensor.kyl_batteri_4
sensor.extra_koksmaskin_switch_0_power
switch.kegerator_fan
```

### Fermentation Chamber

```yaml
climate.fermentation_chamber
```

### RAPT Pill

Current known entities:

```yaml
sensor.yellow_pill_temperature
sensor.yellow_pill_gravity_2
sensor.yellow_pill_battery
```

Older/alternative gravity entity sometimes used:

```yaml
sensor.yellow_pill_specific_gravity
```

Use the actual entity from your Home Assistant instance.

### Brewfather / Recipe Runtime

```yaml
sensor.brewfather_active_batch
sensor.brewfather_fermentation_temperature

sensor.recipe_runtime_name
sensor.recipe_runtime_status
sensor.recipe_runtime_source
sensor.recipe_runtime_og
sensor.recipe_runtime_fg
sensor.recipe_runtime_primary_temp
sensor.recipe_runtime_cold_crash_temp
sensor.recipe_runtime_fermenting_days_left
```

## BrewAssistant abstraction entities

### Power

```yaml
sensor.brewassistant_kegerator_power_w
binary_sensor.kegerator_compressor_active
binary_sensor.brewassistant_kegerator_power_sensor_ok
```

### Health

```yaml
sensor.brewassistant_problem_count
sensor.brewassistant_health_status
binary_sensor.brewassistant_any_problem_active
```

### Kegerator Health

```yaml
binary_sensor.brewassistant_kegerator_temperature_sensor_ok
binary_sensor.brewassistant_kegerator_climate_ok
binary_sensor.brewassistant_kegerator_too_warm
binary_sensor.brewassistant_kegerator_too_cold
binary_sensor.brewassistant_kegerator_temperature_sensor_battery_low
```

### Chamber Health

```yaml
binary_sensor.brewassistant_fermentation_chamber_ok
binary_sensor.brewassistant_fermentation_chamber_too_warm
binary_sensor.brewassistant_fermentation_chamber_too_cold
```

### RAPT Pill Health

```yaml
binary_sensor.brewassistant_rapt_pill_temperature_ok
binary_sensor.brewassistant_rapt_pill_gravity_ok
binary_sensor.brewassistant_rapt_pill_battery_sensor_ok
binary_sensor.brewassistant_rapt_pill_battery_low
```

### Brewfather Health

```yaml
binary_sensor.brewassistant_brewfather_batch_ok
```

## Dashboard helpers

```yaml
input_select.kegerator_card_section

input_boolean.fwk_process_card_enabled
input_boolean.fwk_show_details

input_boolean.brewassistant_hot_side_enabled
input_boolean.brewassistant_hot_side_show_settings
```

## Future Shelly mapping

When the Shelly 4-outlet power strip is added, update:

```yaml
sensor.brewassistant_kegerator_power_w
```

to use the Shelly outlet power entity.

Suggested future map:

```yaml
sensor.shelly_outlet_1_power -> sensor.brewassistant_kegerator_power_w
sensor.shelly_outlet_2_power -> sensor.brewassistant_chamber_heat_power_w
sensor.shelly_outlet_3_power -> sensor.brewassistant_fan_power_w
sensor.shelly_total_power     -> sensor.brewassistant_total_power_w
```
