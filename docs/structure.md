# BrewAssistant – Structure

## Purpose

BrewAssistant is structured as a layered Home Assistant system.

The goal is to avoid one large fragile automation and instead keep recipe data, live data, workflow logic, chamber logic, and UI separate.

## Architecture Layers

## 1. Helper Layer

File:

- `brewassistant_helpers.yaml`

Contains:

- batch active helper
- step completion helpers
- detail visibility helper
- fallback recipe values
- SG snapshot helpers

Examples:

- `input_boolean.fwk_batch_active`
- `input_boolean.fwk_spunding_installed`
- `input_boolean.fwk_dry_hop_added`
- `input_boolean.fwk_cold_crash_active`
- `input_boolean.fwk_transferred_to_keg`
- `input_number.recipe_fallback_og`
- `input_number.recipe_fallback_fg`

## 2. Runtime Layer

File:

- `brewassistant_runtime.yaml`

Normalizes source data into stable runtime sensors.

Sources:

- Brewfather
- Yellow Pill / RAPT
- fallback helpers

Examples:

- `sensor.recipe_runtime_name`
- `sensor.recipe_runtime_status`
- `sensor.recipe_runtime_primary_temp`
- `sensor.recipe_runtime_cold_crash_temp`
- `sensor.fwk_live_sg`
- `sensor.fwk_live_temp`
- `sensor.fwk_attenuation`

## 3. Workflow Layer

File:

- `brewassistant_workflow.yaml`

Handles process state and action logic.

Examples:

- `sensor.fwk_process_status`
- `sensor.fwk_next_step`
- `sensor.fwk_current_action_stage`
- `sensor.fwk_next_action_stage`
- `binary_sensor.fwk_spunding_active`
- `binary_sensor.fwk_dry_hop_active`
- `binary_sensor.fwk_ready_for_cold_crash`
- `binary_sensor.fwk_ready_for_transfer`

## 4. Notification Layer

File:

- `brewassistant_notifications.yaml`

Handles process and chamber notifications.

Current notification groups:

- spunding
- dry hop
- cold crash ready
- transfer ready
- chamber mismatch
- temp drift

## 5. Chamber Intelligence Layer

File:

- `brewassistant_chamber.yaml`

Compares Brewfather/runtime target with chamber target and live fermentation temperature.

Examples:

- `sensor.fwk_chamber_target_midpoint`
- `sensor.fwk_recipe_active_target_temp`
- `sensor.fwk_recipe_vs_chamber_delta`
- `sensor.fwk_live_vs_recipe_delta`
- `sensor.fwk_chamber_alignment_status`

## 6. Smart Automation Layer

File:

- `brewassistant_smart_automation_v2.yaml`

Provides safe semiauto control.

Features:

- suggested chamber range
- apply Brewfather target button
- guarded semiauto script
- optional auto-apply toggle
- cold crash suggestion
- safety disable when chamber is turned off

## 7. UI Layer

Dashboard/card files:

- `brewassistant_main_card_dark_v1.yaml`
- `brewassistant_chamber_card_v1_2_semiauto.yaml`
- `brewassistant_kegerator_card_v1_1_premium.yaml`

UI principles:

- current state first
- only relevant actions visible
- dark premium style
- expandable detail sections
- no full auto without safeguards


## Planned Module Structure

BrewAssistant is intended to be modular. Each hardware stage should add functionality without breaking the previous setup.

```text
BrewAssistant
├── Core Workflow
│   ├── Batch state
│   ├── Current phase
│   ├── Next step
│   ├── Progress
│   └── Notifications
│
├── Fermentation / Kegerator Chamber
│   ├── Cooling control
│   ├── Compressor protection
│   ├── Fan circulation
│   ├── Cold crash support
│   └── Serving / storage support
│
├── DigiBoil BIAB Guide
│   ├── Power monitoring only
│   ├── Manual mash workflow
│   ├── Manual sparge workflow
│   ├── Timers
│   └── Checklists
│
├── Fercubator Module
│   ├── Dedicated fermentation chamber
│   ├── Recipe temperature targets
│   ├── Fermentation profiles
│   └── Chamber-specific automation
│
└── BrewZilla RAPT Module
    ├── RAPT telemetry
    ├── Heating status
    ├── Pump status
    ├── Target temperature
    ├── Mash profile support
    └── Advanced hot-side workflow
