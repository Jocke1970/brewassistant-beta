# Entity Guide

This document describes the preferred BrewAssistant v4 entity naming model.

BrewAssistant is still evolving, so some installations may contain older `fwk_*` entities. Those are considered legacy names and should gradually be migrated to generic `brew_*` names.

---

## Naming principles

Use generic brewing names instead of kit-specific names.

Recommended direction:

```text
brew_process_*         workflow and state machine
brew_batch_*           active batch details
brew_recipe_*          recipe/runtime data
brew_chamber_*         fermentation chamber control and monitoring
brew_manual_*          manual fermentation tracking
brew_notification_*    notification settings and state
brew_hot_side_*        mash/boil/brew-day workflow
brewzilla_*            BrewZilla/RAPT device entities
```

Legacy direction:

```text
fwk_*                  old Fresh Wort Kit namespace
```

---

## Process entities

Process entities describe the current workflow state.

Recommended examples:

```text
sensor.brew_process_status
sensor.brew_process_next_step
sensor.brew_process_current_action_stage
sensor.brew_process_next_action_stage
sensor.brew_process_planned_summary
```

Typical states:

```text
Idle
Fermenting
Ready for cold crash
Cold crash
Ready for transfer
Packaged
Finished
```

---

## Batch entities

Batch entities describe the currently active batch.

Recommended examples:

```text
input_boolean.brew_batch_active
input_boolean.brew_batch_packaged
input_text.brew_batch_name
input_select.brew_batch_phase
input_datetime.brew_batch_started_at
input_datetime.brew_batch_packaged_at
```

Possible phases:

```text
Brew
Fermentation
Cold Crash
Transfer
Carbonation
Storage
Finished
```

Swedish UI labels can display these as:

```text
Bryggning
Fermentering
Cold Crash
Överföring
Karbonering
Lagring
Klar
```

---

## Recipe/runtime entities

Recipe entities describe data coming from Brewfather, manual input, RAPT or fallback helpers.

Recommended examples:

```text
sensor.brew_recipe_name
sensor.brew_recipe_source
sensor.brew_recipe_status
sensor.brew_recipe_primary_temp
sensor.brew_recipe_cold_crash_temp
sensor.brew_recipe_fermentation_start
number.brew_recipe_target_gravity
```

Existing runtime-style examples:

```text
sensor.recipe_runtime_name
sensor.recipe_runtime_status
sensor.recipe_runtime_source
sensor.recipe_runtime_primary_temp
sensor.recipe_runtime_cold_crash_temp
sensor.recipe_runtime_fermentation_start
```

These may remain as compatibility sensors or be renamed during a later cleanup.

---

## Chamber entities

Chamber entities describe fermentation chamber state and control.

Common external entities:

```text
climate.fermentation_chamber
sensor.yellow_pill_temperature
sensor.yellow_pill_specific_gravity
switch.fermentation_heating
```

Recommended derived entities:

```text
sensor.brew_chamber_liquid_temperature
sensor.brew_chamber_target_temperature
sensor.brew_chamber_delta
sensor.brew_chamber_hvac_action
binary_sensor.brew_chamber_target_aligned
script.brew_chamber_apply_recipe_target
```

---

## Manual mode entities

Manual mode is for batches without automated gravity or recipe integration.

Recommended examples:

```text
input_boolean.brew_manual_batch_active
input_boolean.brew_manual_batch_packaged
input_text.brew_manual_batch_name
input_number.brew_manual_current_gravity
input_number.brew_manual_previous_gravity
input_number.brew_manual_target_gravity
input_datetime.brew_manual_last_reading_at
sensor.brew_manual_status
sensor.brew_manual_next_step
```

Existing/manual package examples may currently use:

```text
input_boolean.manual_batch_active
input_boolean.manual_batch_packaged
input_text.manual_batch_name
```

Those can be kept if already used heavily, or migrated later.

---

## Notification entities

Recommended examples:

```text
input_boolean.brew_notification_enabled
input_boolean.brew_notification_warnings_enabled
input_boolean.brew_notification_persistent_enabled
input_boolean.brew_notification_chamber_enabled
input_boolean.brew_notification_manual_enabled
```

Existing examples may include:

```text
input_boolean.brewassistant_notifications_enabled
input_boolean.brewassistant_warnings_enabled
input_boolean.brewassistant_persistent_notifications_enabled
```

---

## Kegerator entities

Common external entities:

```text
climate.kegerator_kylskap
sensor.kyl_temperatur_4
switch.kegerator_fan
switch.extra_koksmaskin_switch_0
sensor.extra_koksmaskin_switch_0_power
```

Recommended derived entities:

```text
binary_sensor.kegerator_compressor_active
sensor.kegerator_current_temperature
sensor.kegerator_target_temperature
sensor.kegerator_delta
sensor.kegerator_hvac_action
```

Note: if target temperature is an attribute on `climate.kegerator_kylskap`, templates should read the climate attribute instead of expecting a standalone target sensor.

---

## BrewZilla/RAPT entities

Potential future entities:

```text
sensor.brewzilla_name
sensor.brewzilla_firmware_version
sensor.brewzilla_temperature
sensor.brewzilla_connection_state
switch.brewzilla_heating_enabled
switch.brewzilla_pump_enabled
number.brewzilla_heating_utilisation
number.brewzilla_pump_utilisation
number.brewzilla_target_temperature
```

---

## Migration table

Suggested direction:

| Legacy | Preferred v4 direction |
| --- | --- |
| `sensor.fwk_process_status` | `sensor.brew_process_status` |
| `sensor.fwk_next_step` | `sensor.brew_process_next_step` |
| `sensor.fwk_current_action_stage` | `sensor.brew_process_current_action_stage` |
| `sensor.fwk_next_action_stage` | `sensor.brew_process_next_action_stage` |
| `sensor.fwk_planned_summary` | `sensor.brew_process_planned_summary` |
| `input_boolean.fwk_batch_active` | `input_boolean.brew_batch_active` |
| `input_boolean.fwk_transferred_to_keg` | `input_boolean.brew_batch_packaged` |
| `input_boolean.fwk_cold_crash_active` | `input_boolean.brew_batch_cold_crash_active` |
| `binary_sensor.fwk_ready_for_cold_crash` | `binary_sensor.brew_process_ready_for_cold_crash` |
| `binary_sensor.fwk_ready_for_transfer` | `binary_sensor.brew_process_ready_for_transfer` |
| `script.fwk_start_batch` | `script.brew_batch_start` |
| `script.fwk_reset_batch` | `script.brew_batch_reset` |
| `script.fwk_apply_brewfather_target` | `script.brew_chamber_apply_recipe_target` |

---

## Migration advice

Do not rename everything blindly.

Recommended approach:

1. Add new v4 entities.
2. Keep compatibility aliases for old dashboards.
3. Update dashboard cards.
4. Remove old `fwk_*` references once dashboards and automations no longer use them.
5. Keep a migration table in the repo until the old namespace is fully gone.

