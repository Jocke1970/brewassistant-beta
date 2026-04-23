# BrewAssistant – State Machine

## Purpose
This document defines the process logic for a clean, action-focused fermentation dashboard.

The UI should:
- always show the main batch status card
- show only relevant process cards
- open cards automatically when a step becomes relevant
- hide cards automatically when a step is completed
- optionally show one current action card and one upcoming preview card

## Core Process Steps
1. Spunding
2. Dry Hop
3. Cold Crash
4. Transfer

## UI Visibility Model
Each step can be in one of three UI states:

- Hidden
- Preview
- Active

### Hidden
The step is not relevant yet, or it has already been completed.

### Preview
The step is approaching and should be visible in a softer, less urgent format.

### Active
The step is currently relevant and should be shown as the primary action card.

## Main Concepts

### Current Action Stage
A sensor should identify the most relevant current step:
- spunding
- dry_hop
- cold_crash
- transfer
- none

Suggested entity:
- `sensor.fwk_current_action_stage`

### Next Action Stage
A sensor should identify the next likely upcoming step.

Suggested entity:
- `sensor.fwk_next_action_stage`

## Step Logic

## 1. Spunding

### Hidden
- batch not active
- spunding already installed
- process already progressed well beyond spunding stage

### Preview
Show when:
- batch is active
- spunding not installed
- batch age is approaching target time

Recommended preview trigger:
- `batch_age_hours >= spunding_after_hours - 6`

Example:
- if recipe says spunding after 24h
- preview starts at 18h

### Active
Show when:
- batch is active
- spunding not installed
- batch age reached or exceeded target time

Recommended active trigger:
- `batch_age_hours >= spunding_after_hours`

### Completed
- user marks spunding installed

Suggested helper:
- `input_boolean.fwk_spunding_installed`

## 2. Dry Hop

### Hidden
- batch not active
- dry hop already added
- process already progressed into cold crash or transfer

### Preview
Show when:
- gravity is close to dry hop window
- dry hop not yet added

Recommended preview trigger:
- `sg <= dry_hop_sg_high + 0.002`
- and `sg > dry_hop_sg_high`

Example:
- dry hop high = 1.014
- preview starts around 1.016

### Active
Show when:
- SG is inside dry hop window
- dry hop not yet added

Recommended active trigger:
- `sg <= dry_hop_sg_high`
- `sg >= dry_hop_sg_low`

### Completed
- user marks dry hop added

Suggested helper:
- `input_boolean.fwk_dry_hop_added`

## 3. Cold Crash

### Hidden
- batch not active
- cold crash already active
- transfer completed

### Preview
Show when:
- SG is near terminal gravity
- fermentation pace has slowed
- but SG is not yet stable enough

Recommended preview inputs:
- gravity points left small
- SG change over last 24h is low
- not yet fully stable

Possible preview logic:
- `gravity_points_left <= 0.004`
- and `sg_stable_2_days = off`

### Active
Show when:
- SG is near target FG
- SG has been stable for 2+ days
- dry hop step is done, or not required
- cold crash is not active yet

Recommended active trigger:
- `binary_sensor.fwk_ready_for_cold_crash = on`

### Completed
- user starts cold crash

Suggested helper:
- `input_boolean.fwk_cold_crash_active`

## 4. Transfer

### Hidden
- cold crash not active yet
- transfer already completed

### Preview
Show when:
- cold crash is active
- but minimum cold crash duration has not yet been reached

Recommended preview trigger:
- `cold_crash_active = on`
- `cold_crash_days < cold_crash_days_min`

### Active
Show when:
- cold crash is active
- minimum cold crash duration reached
- transfer not completed yet

Recommended active trigger:
- `binary_sensor.fwk_ready_for_transfer = on`

### Completed
- user marks transferred to keg

Suggested helper:
- `input_boolean.fwk_transferred_to_keg`

## Priority Rules

Only one step should normally be the primary active card.

Recommended active priority:
1. Transfer
2. Cold Crash
3. Dry Hop
4. Spunding

Reason:
- later steps are usually more time-sensitive once reached
- the dashboard should focus on the most operationally relevant action now

### Suggested current action logic
- if transfer active -> `transfer`
- else if cold crash active -> `cold_crash`
- else if dry hop active -> `dry_hop`
- else if spunding active -> `spunding`
- else `none`

### Suggested next action logic
- current active step excluded
- next matching preview step becomes `sensor.fwk_next_action_stage`

## Recommended UI Layout

## Always Visible
### Main Batch Card
Show:
- recipe name
- process status
- next step
- SG
- fermentation temperature
- batch age
- attenuation / progress

## Conditionally Visible
### Current Action Card
Shows one primary action step only:
- Spunding card OR
- Dry Hop card OR
- Cold Crash card OR
- Transfer card

### Next Up Card
Optional smaller preview card showing the next upcoming step.

### Details Drawer
Manual expand/collapse section with:
- diagnostics
- source info
- calculated metrics
- chamber details
- debug entities

## Suggested Entities

### Helpers
- `input_boolean.fwk_batch_active`
- `input_boolean.fwk_spunding_installed`
- `input_boolean.fwk_dry_hop_added`
- `input_boolean.fwk_cold_crash_active`
- `input_boolean.fwk_transferred_to_keg`
- `input_boolean.fwk_show_details`

### Runtime Sensors
- `sensor.fwk_current_action_stage`
- `sensor.fwk_next_action_stage`
- `sensor.fwk_process_status`
- `sensor.fwk_next_step`
- `sensor.fwk_batch_age_hours`
- `sensor.fwk_batch_age_days`
- `sensor.fwk_attenuation`
- `sensor.fwk_gravity_points_left`
- `sensor.fwk_sg_change_12h`
- `sensor.fwk_sg_change_24h`
- `sensor.fwk_fermentation_pace`

### Binary Sensors
- `binary_sensor.fwk_spunding_preview`
- `binary_sensor.fwk_spunding_active`
- `binary_sensor.fwk_dry_hop_preview`
- `binary_sensor.fwk_dry_hop_active`
- `binary_sensor.fwk_cold_crash_preview`
- `binary_sensor.fwk_cold_crash_active_card`
- `binary_sensor.fwk_transfer_preview`
- `binary_sensor.fwk_transfer_active`

## Design Principles
- Show current state first
- Show only relevant actions
- Keep completed steps hidden
- Use preview states to reduce surprise
- Prefer operational clarity over maximum information density
- Separate recipe logic, live sensor logic, decision logic, and UI logic

## Recommended Build Order
1. Build runtime sensors
2. Build preview/active binary sensors
3. Build current/next action selectors
4. Build conditional UI cards
5. Add premium polish
