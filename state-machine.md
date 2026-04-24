# BrewAssistant – State Machine

## Purpose

The state machine keeps the dashboard focused on what matters now.

It drives:

- process status
- next step
- current action
- next action
- step visibility
- notifications

## Main States

The process is modeled around these high-level phases:

- Idle
- Primary fermentation
- Install spunding
- Dry hop now
- Ready for cold crash
- Cold crash
- Ready for transfer
- Finished / transferred to keg

## Current Action Stage

Entity:

- `sensor.fwk_current_action_stage`

Expected values:

- `none`
- `spunding`
- `dry_hop`
- `cold_crash`
- `transfer`

Only one stage should normally be active at a time.

## Next Action Stage

Entity:

- `sensor.fwk_next_action_stage`

Expected values:

- `none`
- `spunding`
- `dry_hop`
- `cold_crash`
- `transfer`

This is used for preview cards.

## Step Logic

## Spunding

Preview:

- batch active
- spunding not installed
- within preview window before scheduled spunding time

Active:

- batch active
- spunding not installed
- batch age is greater than or equal to configured spunding time

Completed:

- `input_boolean.fwk_spunding_installed = on`

## Dry Hop

Preview:

- batch active
- dry hop not added
- SG approaching dry hop window

Active:

- batch active
- dry hop not added
- SG inside dry hop window

Completed:

- `input_boolean.fwk_dry_hop_added = on`

## Cold Crash

Preview:

- gravity close to FG
- not yet SG-stable enough

Active:

- SG stable
- near target FG
- batch active
- cold crash not active

Completed / entered:

- `input_boolean.fwk_cold_crash_active = on`

## Transfer

Preview:

- cold crash active
- minimum cold crash time not yet reached

Active:

- cold crash active
- minimum cold crash days reached
- transfer not completed

Completed:

- `input_boolean.fwk_transferred_to_keg = on`

## Design Rule

The dashboard should show:

- main status always
- current action only when needed
- next action only when useful
- details only when expanded

Completed steps should disappear from the main action area.
