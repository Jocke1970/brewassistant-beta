# Hot Side Premium Workflow v1.1

## Purpose

Hot Side is the brew day workflow module.

It helps track:

- recipe
- batch
- current phase
- next action
- timer
- mash target
- chill target
- workflow navigation

## Enable helper

```yaml
input_boolean:
  brewassistant_hot_side_enabled:
    name: BrewAssistant Hot Side Enabled
    icon: mdi:kettle-steam
```

When disabled, only the top card is shown.

When enabled, the full workflow is visible.

## Settings helper

```yaml
input_boolean:
  brewassistant_hot_side_show_settings:
    name: BrewAssistant Hot Side Show Settings
    icon: mdi:tune-variant
```

## Core workflow entities

```yaml
sensor.brewassistant_hot_side_status
sensor.brewassistant_hot_side_progress
sensor.brewassistant_hot_side_recipe_name
sensor.brewassistant_hot_side_batch_name
sensor.brewassistant_hot_side_instruction
sensor.brewassistant_hot_side_next_action
sensor.brewassistant_hot_side_next_phase
sensor.brewassistant_hot_side_timer_display

input_select.brewassistant_hot_side_phase
timer.brewassistant_hot_side_timer
```

## Control buttons

```yaml
input_button.brewassistant_hot_side_start
input_button.brewassistant_hot_side_previous
input_button.brewassistant_hot_side_next
input_button.brewassistant_hot_side_pause_resume
input_button.brewassistant_hot_side_start_timer
input_button.brewassistant_hot_side_reset
```

## Settings entities

```yaml
input_boolean.brewassistant_hot_side_auto_start_timers
input_boolean.brewassistant_hot_side_notifications

input_number.brewassistant_hot_side_strike_water_temp
input_number.brewassistant_hot_side_mash_target_temp
input_number.brewassistant_hot_side_mash_minutes
input_number.brewassistant_hot_side_mashout_minutes
input_number.brewassistant_hot_side_boil_minutes
input_number.brewassistant_hot_side_whirlpool_minutes
input_number.brewassistant_hot_side_chill_target_temp

input_text.brewassistant_hot_side_manual_recipe_name
input_text.brewassistant_hot_side_manual_batch_name
```

## Phases

Suggested phase list:

```text
Idle
Preparation
Heat Strike Water
Mash In
Mash Rest
Mash Out
Sparge / Drain
Heat To Boil
Boil
Whirlpool
Chill
Transfer To Fermenter
Done
```

## Power button behavior

Current behavior:

```text
Power button toggles the UI/module only.
It does not switch physical power.
```

Future behavior may map to Shelly outlet control, but this should be added carefully with safety checks.
