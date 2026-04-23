# Entity Map

## Purpose

This document lists the entities expected by BrewAssistant and groups them by responsibility.

## Source Entities

### Brewfather
Expected examples:
- `sensor.brewfather_recipe_name`
- `sensor.brewfather_fermentation_start`
- `sensor.brewfather_target_temperature`
- `sensor.brewfather_upcoming_target_temperature`
- `sensor.brewfather_upcoming_target_temperature_change`
- `sensor.brewfather_last_reading`
- `sensor.brewfather_batch_notes`
- `sensor.brewfather_events`
- `calendar.brewfather_events`

Optional / experimental:
- `sensor.brewfather_all_batches_data`

### Live Fermentation
- `sensor.yellow_pill_temperature`
- `sensor.yellow_pill_gravity_2`

### Chamber Control
- `climate.fermentation_chamber`

## Helper Entities

### Batch Lifecycle
- `input_boolean.fwk_batch_active`
- `input_boolean.fwk_transferred_to_keg`
- `input_boolean.fwk_show_details`

### Step Completion
- `input_boolean.fwk_spunding_installed`
- `input_boolean.fwk_dry_hop_added`
- `input_boolean.fwk_cold_crash_active`

### Timing
- `input_datetime.fwk_batch_start`
- `input_datetime.fwk_cold_crash_start`

### Fallback Recipe Inputs
- `input_number.recipe_fallback_og`
- `input_number.recipe_fallback_fg`
- `input_number.recipe_fallback_dry_hop_sg_low`
- `input_number.recipe_fallback_dry_hop_sg_high`
- `input_number.recipe_fallback_spunding_after_hours`
- `input_number.recipe_fallback_spunding_target_bar`
- `input_number.recipe_fallback_cold_crash_temp`
- `input_number.recipe_fallback_cold_crash_days_min`

### Snapshot Inputs
- `input_number.fwk_sg_today`
- `input_number.fwk_sg_yesterday`
- `input_number.fwk_sg_two_days_ago`

## Runtime Sensors

### Recipe Runtime
- `sensor.recipe_runtime_name`
- `sensor.recipe_runtime_og`
- `sensor.recipe_runtime_fg`
- `sensor.recipe_runtime_primary_temp`
- `sensor.recipe_runtime_upcoming_temp`
- `sensor.recipe_runtime_dry_hop_sg_low`
- `sensor.recipe_runtime_dry_hop_sg_high`
- `sensor.recipe_runtime_spunding_after_hours`
- `sensor.recipe_runtime_spunding_target_bar`
- `sensor.recipe_runtime_cold_crash_temp`
- `sensor.recipe_runtime_cold_crash_days_min`
- `sensor.recipe_runtime_source`

### Live Runtime
- `sensor.fwk_batch_age_hours`
- `sensor.fwk_batch_age_days`
- `sensor.fwk_live_sg`
- `sensor.fwk_live_temp`
- `sensor.fwk_attenuation`
- `sensor.fwk_gravity_points_left`
- `sensor.fwk_sg_change_12h`
- `sensor.fwk_sg_change_24h`
- `sensor.fwk_fermentation_pace`
- `sensor.fwk_temperature_recommendation`

### Decision Runtime
- `sensor.fwk_process_status`
- `sensor.fwk_next_step`
- `sensor.fwk_current_action_stage`
- `sensor.fwk_next_action_stage`

## Binary Sensors

### Step Preview
- `binary_sensor.fwk_spunding_preview`
- `binary_sensor.fwk_dry_hop_preview`
- `binary_sensor.fwk_cold_crash_preview`
- `binary_sensor.fwk_transfer_preview`

### Step Active
- `binary_sensor.fwk_spunding_active`
- `binary_sensor.fwk_dry_hop_active`
- `binary_sensor.fwk_cold_crash_active_card`
- `binary_sensor.fwk_transfer_active`

### Readiness / Diagnostics
- `binary_sensor.fwk_sg_stable_2_days`
- `binary_sensor.fwk_ready_for_cold_crash`
- `binary_sensor.fwk_ready_for_transfer`
- `binary_sensor.fwk_temperature_too_high`
- `binary_sensor.fwk_temperature_too_low`
- `binary_sensor.fwk_fermentation_stalled`

## Scripts
- `script.fwk_start_batch`
- `script.fwk_mark_spunding_installed`
- `script.fwk_mark_dry_hop_added`
- `script.fwk_start_cold_crash`
- `script.fwk_mark_transferred_to_keg`
- `script.fwk_reset_batch`
