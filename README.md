# BrewAssistant

BrewAssistant is a Home Assistant based brewing workflow system for recipe-aware and sensor-aware fermentation, chamber control, and kegerator monitoring.

It combines:

- **Brewfather** for recipe context, fermentation plan, target temperatures, and batch status
- **RAPT / Yellow Pill** for live fermentation temperature and gravity
- **Home Assistant** for workflow logic, state machine, notifications, semiauto control, and premium dashboards

## Current Status

BrewAssistant is now at an early functional v1 stage.

Implemented:

- Core helpers
- Runtime sensor layer
- Workflow / state machine
- Notifications v1
- Chamber intelligence layer
- Smart automation layer v2
- Brewfather-aware runtime
- Premium fermentation dashboard
- Premium fermentation chamber card
- Premium kegerator card

## Core Concepts

BrewAssistant separates the system into layers:

1. **Recipe runtime**
   - Brewfather first
   - manual fallback when Brewfather is unavailable

2. **Live runtime**
   - Yellow Pill / RAPT temperature and gravity

3. **Workflow engine**
   - process status
   - next step
   - current action
   - next action

4. **Chamber intelligence**
   - recipe target vs chamber target
   - live temp vs recipe target
   - alignment status

5. **Smart automation**
   - semiauto target application
   - guarded optional auto-apply
   - cold crash suggestions

6. **UI**
   - clean current-state-first dashboard
   - expandable detail sections
   - premium dark card style

## Main Packages

Recommended package files:

- `brewassistant_helpers.yaml`
- `brewassistant_runtime.yaml`
- `brewassistant_workflow.yaml`
- `brewassistant_notifications.yaml`
- `brewassistant_chamber.yaml`
- `brewassistant_smart_automation_v2.yaml`

## Dashboard Files

Recommended dashboard/card files:

- `brewassistant_main_card_dark_v1.yaml`
- `brewassistant_chamber_card_v1_2_semiauto.yaml`
- `brewassistant_kegerator_card_v1_1_premium.yaml`

## Current Live Entities

Known live entities used in the current system:

- `climate.fermentation_chamber`
- `climate.kegerator_kylskap`
- `sensor.yellow_pill_temperature`
- `sensor.yellow_pill_gravity_2`
- `sensor.kyl_temperatur_4`

## Current Brewfather Source

Primary Brewfather source:

- `sensor.brewfather_all_batches_data`

Used for:

- recipe name
- batch status
- batch number
- fermentation steps
- primary target temperature
- cold crash target temperature
- fermenting days left

## Notes

OG and FG are currently still fallback-backed unless verified from Brewfather data.

The system is designed to remain useful even when Brewfather is offline.
