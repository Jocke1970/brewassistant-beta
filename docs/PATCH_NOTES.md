# Patch Notes

## v4 modular split notes

The first modular split preserved existing entity IDs and separated backend modules by responsibility.

## Confirmed fixes and adjustments

### Fermentation status behavior

`sensor.fwk_process_status` should now distinguish between:

```text
Power/card off → Off
Power/card on, no active batch → Idle
Active batch → current process state
Transferred → Finished / transferred to keg
```

Recommended `state:` logic:

```yaml
state: |
  {% set bf_status = states('sensor.recipe_runtime_status') %}
  {% set batch_active = is_state('input_boolean.fwk_batch_active', 'on') %}

  {% if is_state('input_boolean.fwk_process_card_enabled', 'off') %}
    Off
  {% elif is_state('input_boolean.fwk_transferred_to_keg', 'on') %}
    Finished / transferred to keg
  {% elif not batch_active %}
    Idle
  {% elif is_state('input_boolean.fwk_cold_crash_active', 'on') %}
    Cold crash
  {% elif is_state('binary_sensor.fwk_ready_for_transfer', 'on') %}
    Ready for transfer
  {% elif is_state('binary_sensor.fwk_ready_for_cold_crash', 'on') %}
    Ready for cold crash
  {% elif is_state('binary_sensor.fwk_dry_hop_active', 'on') %}
    Dry hop now
  {% elif is_state('binary_sensor.fwk_spunding_active', 'on') %}
    Install spunding
  {% elif batch_active %}
    Primary fermentation
  {% elif bf_status not in ['unknown', 'unavailable', 'none', ''] %}
    {{ bf_status }}
  {% else %}
    Idle
  {% endif %}
```

### Kegerator compressor binary sensor

Added/confirmed:

```yaml
binary_sensor:
  - name: Kegerator Compressor Active
    unique_id: kegerator_compressor_active
    icon: mdi:engine
    state: |
      {% set p = states('sensor.extra_koksmaskin_switch_0_power') | float(0) %}
      {{ p > 20 }}
```

### Brewfather target FG fallback

`Recipe Runtime Target FG` should use `input_number.fwk_recipe_fg` if the new helper does not exist:

```yaml
state: |
  {% set fg = states('input_number.brewassistant_fermentation_target_fg') | float(none) %}
  {% set fwk_fg = states('input_number.fwk_recipe_fg') | float(none) %}
  {% if fg is not none %}
    {{ fg | round(3) }}
  {% elif fwk_fg is not none %}
    {{ fwk_fg | round(3) }}
  {% else %}
    unknown
  {% endif %}
```

### Details toggle helper

Current UI uses:

```text
input_boolean.fwk_show_details
```

For compatibility, this helper belongs in `brewassistant_fermentation_module.yaml` for now.

Future polish may split this into module-specific UI toggles such as:

```text
input_boolean.brewfather_show_details
input_boolean.hot_side_show_details
```

### RAPT Pill gravity entity

Detected RAPT gravity entity:

```text
sensor.yellow_pill_gravity_2
```

Recommended long-term wrapper:

```text
sensor.fwk_live_sg
```

or a configurable helper:

```text
input_text.brewassistant_smart_gravity_entity
```

## Known remaining work

```text
1. Hot Side action layer
2. Hot Side timer engine
3. Remove remaining unknown/unavailable UI states
4. Optional: module-specific UI detail toggles
5. Optional: Brewfather full step sync
```
