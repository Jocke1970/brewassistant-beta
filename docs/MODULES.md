# Module Reference

## brewassistant_fermentation_module.yaml

Main fermentation process module.

Important entities:

```text
input_boolean.brewassistant_fermentation_enabled
input_boolean.fwk_process_card_enabled
input_boolean.fwk_batch_active
input_boolean.fwk_cold_crash_active
input_boolean.fwk_transferred_to_keg
input_boolean.fwk_show_details
sensor.fwk_process_status
sensor.fwk_next_step
sensor.fwk_live_sg
sensor.fwk_live_temp
sensor.fwk_batch_age_days
sensor.fwk_attenuation
script.fwk_start_batch
script.fwk_reset_batch
```

Current status behavior:

```text
fwk_process_card_enabled = off → Off
fwk_process_card_enabled = on and no batch → Idle
fwk_batch_active = on → Primary fermentation / workflow status
fwk_transferred_to_keg = on → Finished / transferred to keg
```

## brewassistant_chamber_module.yaml

Fermentation chamber module.

Important entities:

```text
input_boolean.brewassistant_chamber_enabled
sensor.brewassistant_chamber_status
sensor.brewassistant_chamber_alignment
sensor.fwk_chamber_target_midpoint
script.fwk_apply_brewfather_target
climate.fermentation_chamber
```

Expected inactive states:

```text
sensor.brewassistant_chamber_status = Off
sensor.brewassistant_chamber_alignment = Waiting for data / Chamber off
```

## brewassistant_kegerator_module.yaml

Kegerator/fridge module.

Important entities:

```text
input_boolean.brewassistant_kegerator_enabled
binary_sensor.kegerator_compressor_active
sensor.kyl_temperatur_4
switch.kegerator_fan
climate.kegerator_kylskap
```

Compressor logic:

```text
sensor.extra_koksmaskin_switch_0_power > 20 W → compressor active
```

## brewassistant_brewfather_adapter.yaml

Brewfather/runtime adapter.

Important entities:

```text
sensor.recipe_runtime_name
sensor.recipe_runtime_status
sensor.recipe_runtime_source
sensor.recipe_runtime_primary_temp
sensor.recipe_runtime_cold_crash_temp
sensor.recipe_runtime_fermenting_days_left
sensor.recipe_runtime_target_fg
sensor.recipe_runtime_og
sensor.recipe_runtime_fg
```

Expected fallback values:

```text
sensor.recipe_runtime_name = Manual / fallback recipe
sensor.recipe_runtime_source = manual_fallback
```

## brewassistant_hot_side_module.yaml

Brew day / hot side module.

Important entities:

```text
input_boolean.brewassistant_hot_side_enabled
input_boolean.brewassistant_hot_side_auto_start_timers
input_boolean.brewassistant_hot_side_notifications_enabled
input_number.brewassistant_hot_side_strike_temp
input_number.brewassistant_hot_side_mash_temp
input_number.brewassistant_hot_side_mash_minutes
input_number.brewassistant_hot_side_boil_minutes
script.brewassistant_hot_side_start
script.brewassistant_hot_side_next
input_button.brewassistant_hot_side_next
```

Current known item:

```text
Hot Side UI/core loads, but timer/action layer should be reviewed next.
```

## brewassistant_health_module.yaml

Health/problem center.

Important entities:

```text
input_boolean.brewassistant_health_enabled
sensor.brewassistant_health_status
sensor.brewassistant_active_problem_count
```

Health must tolerate missing modules.

## brewassistant_notifications_module.yaml

Notification module.

Important entity:

```text
input_boolean.brewassistant_notifications_enabled
```

Notifications should be guarded by this helper.

## brewassistant_cleaning_module.yaml

Cleaning/checklist helper module.

Used for keg/FermZilla/cleaning related workflows that did not belong cleanly in fermentation or kegerator.
