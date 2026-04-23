# Data Model

## Purpose

This document defines the runtime data model for BrewAssistant.

The main design goal is to normalize data from different sources into a stable set of runtime entities that the decision engine and UI can use.

## Data Layers

## 1. Recipe Source Data
Comes from one or more of:

- Brewfather integration
- BeerXML import / parser
- manual fallback helpers

### Typical fields
- recipe name
- style
- batch size
- OG
- FG
- fermentation start
- primary target temperature
- future temperature step
- dry hop target range
- spunding schedule
- cold crash recommendation
- transfer guidance

## 2. Live Fermentation Data
Comes from sensors such as:

- `sensor.yellow_pill_temperature`
- `sensor.yellow_pill_gravity_2`

### Derived live fields
- current SG
- current fermentation temperature
- attenuation
- gravity points left
- SG delta 12h
- SG delta 24h
- fermentation pace
- stability score
- near-terminal estimate

## 3. Workflow Decision Data
Computed from recipe + live data + user step confirmations.

### Typical fields
- current process status
- next step
- current action stage
- next action stage
- preview state per step
- active state per step
- ready for cold crash
- ready for transfer

## Source Priority

Runtime fields should use a defined source priority to avoid ambiguity.

## Recommended priority
1. Brewfather raw / attribute data
2. Brewfather standard sensors
3. BeerXML parsed data
4. manual fallback helpers

## Example

### Runtime OG
- use Brewfather OG if available
- else use BeerXML OG if available
- else use `input_number.recipe_fallback_og`

### Runtime FG
- use Brewfather FG if available
- else use BeerXML FG if available
- else use `input_number.recipe_fallback_fg`

## Runtime Entity Groups

## Recipe Runtime
Suggested normalized entities:
- `sensor.recipe_runtime_name`
- `sensor.recipe_runtime_style`
- `sensor.recipe_runtime_og`
- `sensor.recipe_runtime_fg`
- `sensor.recipe_runtime_primary_temp`
- `sensor.recipe_runtime_upcoming_temp`
- `sensor.recipe_runtime_spunding_after_hours`
- `sensor.recipe_runtime_spunding_target_bar`
- `sensor.recipe_runtime_dry_hop_sg_low`
- `sensor.recipe_runtime_dry_hop_sg_high`
- `sensor.recipe_runtime_cold_crash_temp`
- `sensor.recipe_runtime_cold_crash_days_min`
- `sensor.recipe_runtime_source`

## Live Runtime
Suggested normalized entities:
- `sensor.fwk_live_sg`
- `sensor.fwk_live_temp`
- `sensor.fwk_attenuation`
- `sensor.fwk_gravity_points_left`
- `sensor.fwk_sg_change_12h`
- `sensor.fwk_sg_change_24h`
- `sensor.fwk_fermentation_pace`
- `sensor.fwk_stability_score`

## Decision Runtime
Suggested normalized entities:
- `sensor.fwk_process_status`
- `sensor.fwk_next_step`
- `sensor.fwk_current_action_stage`
- `sensor.fwk_next_action_stage`

## Important Design Rule

The UI must never depend directly on raw source fields if a normalized runtime entity exists.

This keeps the UI stable even if Brewfather, BeerXML, or fallback helpers change.
