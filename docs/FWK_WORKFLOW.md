# FWK / Fermentation Process Workflow

## Purpose

The FWK process card tracks fermentation batch progress and common actions.

It is intended for the FWK IPL / fermentation workflow.

## Enable helper

```yaml
input_boolean:
  fwk_process_card_enabled:
    name: FWK Process Card Enabled
    icon: mdi:beer-outline
```

When disabled, only the top card is visible.

When enabled, the status tiles, action buttons and details toggle become visible.

## Details helper

```yaml
input_boolean:
  fwk_show_details:
    name: FWK Show Details
    icon: mdi:chevron-down-circle
```

## Batch lifecycle helpers

```yaml
input_boolean.fwk_batch_active
input_boolean.fwk_spunding_installed
input_boolean.fwk_dry_hop_added
input_boolean.fwk_cold_crash_active
input_boolean.fwk_transferred_to_keg
```

## Time helpers

```yaml
input_datetime.fwk_batch_start
input_datetime.fwk_cold_crash_start
```

## Gravity snapshot helpers

```yaml
input_number.fwk_sg_today
input_number.fwk_sg_yesterday
input_number.fwk_sg_two_days_ago
```

Used for stable gravity checks.

## Runtime sensors used by dashboard

```yaml
sensor.fwk_process_status
sensor.fwk_next_step
sensor.fwk_current_action_stage
sensor.fwk_next_action_stage
sensor.fwk_planned_summary

sensor.fwk_live_sg
sensor.fwk_sg_last_updated
sensor.fwk_live_temp
sensor.fwk_batch_age_hours
sensor.fwk_batch_age_days
sensor.fwk_attenuation
sensor.fwk_gravity_points_left
sensor.fwk_fermentation_pace

sensor.recipe_runtime_name
sensor.recipe_runtime_status
sensor.recipe_runtime_source
sensor.recipe_runtime_og
sensor.recipe_runtime_fg
sensor.recipe_runtime_primary_temp
sensor.recipe_runtime_cold_crash_temp
sensor.recipe_runtime_fermenting_days_left
```

## Action buttons

The FWK card expects scripts:

```yaml
script.fwk_start_batch
script.fwk_mark_spunding_installed
script.fwk_mark_dry_hop_added
script.fwk_start_cold_crash
script.fwk_mark_transferred_to_keg
```

## UI behavior

Collapsed:

```text
Top status card only
```

Expanded:

```text
Ferment Temp
Gravity
Planned Temp
Days Left
Current Action
Next Up
Start Batch
Spunding
Dry Hop
Cold Crash
Transfer to Keg
Details toggle
```

## Notes

The FWK card is intentionally separate from the Fermentation Chamber climate card. One handles process workflow; the other handles temperature control.
