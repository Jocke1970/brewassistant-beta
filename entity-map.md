# BrewAssistant – Entity Map

## Helpers

### Batch lifecycle

- `input_boolean.fwk_batch_active`
- `input_boolean.fwk_transferred_to_keg`
- `input_boolean.fwk_show_details`

### Step completion

- `input_boolean.fwk_spunding_installed`
- `input_boolean.fwk_dry_hop_added`
- `input_boolean.fwk_cold_crash_active`

### Semiauto

- `input_boolean.fwk_semiauto_enabled`
- `input_boolean.fwk_auto_apply_bf_target`
- `input_boolean.fwk_allow_cold_crash_semiauto`

### Fallback recipe values

- `input_number.recipe_fallback_og`
- `input_number.recipe_fallback_fg`
- `input_number.recipe_fallback_primary_temp`
- `input_number.recipe_fallback_primary_temp_low`
- `input_number.recipe_fallback_primary_temp_high`
- `input_number.recipe_fallback_dry_hop_sg_low`
- `input_number.recipe_fallback_dry_hop_sg_high`
- `input_number.recipe_fallback_spunding_after_hours`
- `input_number.recipe_fallback_spunding_target_bar`
- `input_number.recipe_fallback_cold_crash_temp`
- `input_number.recipe_fallback_cold_crash_days_min`

## Brewfather Runtime

- `sensor.recipe_runtime_name`
- `sensor.recipe_runtime_status`
- `sensor.recipe_runtime_batch_number`
- `sensor.recipe_runtime_fermentation_start`
- `sensor.recipe_runtime_fermenting_end`
- `sensor.recipe_runtime_fermenting_days_left`
- `sensor.recipe_runtime_primary_temp`
- `sensor.recipe_runtime_cold_crash_temp`
- `sensor.recipe_runtime_source`

## Live Runtime

- `sensor.fwk_live_sg`
- `sensor.fwk_live_temp`
- `sensor.fwk_batch_age_hours`
- `sensor.fwk_batch_age_days`
- `sensor.fwk_cold_crash_days`
- `sensor.fwk_attenuation`
- `sensor.fwk_gravity_points_left`
- `sensor.fwk_fermentation_pace`

## Workflow

- `sensor.fwk_process_status`
- `sensor.fwk_next_step`
- `sensor.fwk_current_action_stage`
- `sensor.fwk_next_action_stage`
- `sensor.fwk_planned_summary`

## Workflow Binary Sensors

- `binary_sensor.fwk_spunding_preview`
- `binary_sensor.fwk_spunding_active`
- `binary_sensor.fwk_dry_hop_preview`
- `binary_sensor.fwk_dry_hop_active`
- `binary_sensor.fwk_cold_crash_preview`
- `binary_sensor.fwk_cold_crash_active_card`
- `binary_sensor.fwk_transfer_preview`
- `binary_sensor.fwk_transfer_active`
- `binary_sensor.fwk_ready_for_cold_crash`
- `binary_sensor.fwk_ready_for_transfer`

## Chamber Intelligence

- `sensor.fwk_chamber_target_midpoint`
- `sensor.fwk_chamber_target_span`
- `sensor.fwk_recipe_active_target_temp`
- `sensor.fwk_recipe_vs_chamber_delta`
- `sensor.fwk_live_vs_recipe_delta`
- `sensor.fwk_chamber_action`
- `sensor.fwk_chamber_alignment_status`
- `sensor.fwk_chamber_summary`

## Smart Automation

- `sensor.fwk_suggested_chamber_low`
- `sensor.fwk_suggested_chamber_high`
- `sensor.fwk_suggested_chamber_range`
- `sensor.fwk_semiauto_recommendation`
- `binary_sensor.fwk_semiauto_apply_recommended`
- `binary_sensor.fwk_semiauto_cold_crash_apply_recommended`

## Scripts

- `script.fwk_start_batch`
- `script.fwk_mark_spunding_installed`
- `script.fwk_mark_dry_hop_added`
- `script.fwk_start_cold_crash`
- `script.fwk_mark_transferred_to_keg`
- `script.fwk_reset_batch`
- `script.fwk_apply_brewfather_target`
- `script.fwk_suggest_brewfather_target`

## Kegerator

- `climate.kegerator_kylskap`
- `sensor.kyl_temperatur_4`
- `binary_sensor.kegerator_cooling_active`
- `binary_sensor.kegerator_reglering_aktiv`
- `sensor.kegerator_flaktstatus`
- `sensor.kegerator_driftstatus`
- `input_boolean.kegerator_show_modes`
- `input_boolean.kegerator_show_temps`
- `input_boolean.kegerator_show_status`
