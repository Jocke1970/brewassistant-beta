# Helpers

## Purpose

Helpers are the stable layer between the dashboard and physical devices.

The dashboard should reference BrewAssistant helper/template entities whenever possible.

## Important helpers

### Kegerator section control

```yaml
input_select:
  kegerator_card_section:
    name: Kegerator Card Section
    options:
      - none
      - temps
      - status
    initial: none
    icon: mdi:fridge-industrial
```

### FWK process enable

```yaml
input_boolean:
  fwk_process_card_enabled:
    name: FWK Process Card Enabled
    icon: mdi:beer-outline
```

### FWK details toggle

```yaml
input_boolean:
  fwk_show_details:
    name: FWK Show Details
    icon: mdi:chevron-down-circle
```

### Hot Side enable

```yaml
input_boolean:
  brewassistant_hot_side_enabled:
    name: BrewAssistant Hot Side Enabled
    icon: mdi:kettle-steam
```

### Hot Side settings toggle

```yaml
input_boolean:
  brewassistant_hot_side_show_settings:
    name: BrewAssistant Hot Side Show Settings
    icon: mdi:tune-variant
```

## Kegerator power abstraction

Dashboard should use:

```yaml
sensor.brewassistant_kegerator_power_w
```

Template example:

```yaml
template:
  - sensor:
      - name: BrewAssistant Kegerator Power W
        unique_id: brewassistant_kegerator_power_w
        icon: mdi:flash
        unit_of_measurement: W
        device_class: power
        state_class: measurement
        state: >
          {{ states('sensor.extra_koksmaskin_switch_0_power') | float(0) }}
        attributes:
          source_sensor: sensor.extra_koksmaskin_switch_0_power
```

When the Shelly power strip is installed, only change the source sensor.

## Compressor active

```yaml
template:
  - binary_sensor:
      - name: Kegerator Compressor Active
        unique_id: kegerator_compressor_active
        device_class: power
        icon: mdi:fridge-industrial
        state: >
          {{ states('sensor.brewassistant_kegerator_power_w') | float(0) > 20 }}
        delay_on:
          seconds: 10
        delay_off:
          seconds: 30
        attributes:
          power_w: >
            {{ states('sensor.brewassistant_kegerator_power_w') | float(0) }}
          threshold_w: 20
          source_sensor: sensor.brewassistant_kegerator_power_w
```

## Common YAML issue

Keep `binary_sensor` and `sensor` template platforms separate:

```yaml
template:
  - binary_sensor:
      - name: Example Binary Sensor
        state: "{{ true }}"

  - sensor:
      - name: Example Sensor
        state: "OK"
```

Do not place normal sensors under `binary_sensor:`.
