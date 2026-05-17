# BrewAssistant v4

**BrewAssistant v4** is a modular Home Assistant brewing assistant for fermentation tracking, chamber control, manual batches, notifications, dashboards, and future hot-side/brew-day integrations.

The project is designed around a clean core with optional modules. It can be used for simple manual fermentation tracking, Brewfather-assisted recipe runtime data, RAPT/Pill readings, fermentation chamber automation, kegerator visualisation, and later BrewZilla/RAPT hot-side workflows.

---

## Project goals

BrewAssistant v4 aims to provide:

- A clean Home Assistant package and custom integration structure.
- Brewing workflows that survive Home Assistant restarts.
- A Swedish-friendly UI with English/core entity naming.
- Fermentation, cold crash, transfer, packaging, and storage workflow support.
- Optional integration with Brewfather, RAPT, BrewZilla and manual hydrometer readings.
- Premium dashboard cards that visualise the current batch state.
- A migration path away from older `fwk_*` helper/entity names.
- A migration path from heavy YAML/Jinja decision logic into Python.

---

## Current v4 philosophy

BrewAssistant v4 separates the brewing system into clear layers:

| Layer | Purpose |
| --- | --- |
| Python Core | Normalize source entities and expose dashboard-safe, read-only state. |
| Helpers | Store user choices, toggles, manual input and workflow state. |
| Runtime | Normalize recipe, batch, Brewfather and sensor data. |
| Workflow | Decide current process state, next step and readiness. |
| Chamber | Apply and monitor fermentation chamber targets. |
| Manual Mode | Track batches without Brewfather/RAPT automation. |
| Notifications | Alert when attention is needed. |
| Dashboard | Visualize the system without owning business logic. |

The dashboard should display and control the system, but should not contain hidden workflow logic that belongs in backend packages or the Python integration.

The long-term direction is:

```text
Python custom integration = logic, normalization, state machine, calculations
YAML packages/dashboard = UI, layout, manual presentation tweaks
```

---

## Python Core v1.1

`custom_components/brewassistant/` contains the BrewAssistant Home Assistant custom integration.

Current milestone:

```text
BrewAssistant Python Core v1.1 · Read-only Core Stable
```

Current scope:

- Read existing Home Assistant entities.
- Normalize liquid temperature, chamber fallback temperature, effective target temperature and gravity.
- Use cold crash target when cold crash is active.
- Mirror process state and next process step from existing workflow/YAML signals.
- Expose smart fermentation recommendations without controlling hardware.
- Detect Pill stale/fresh status.
- Expose source health diagnostics for configured entities.
- Normalize Brewfather/runtime recipe name, status, targets and target FG.
- Expose one compact next recommended action sensor for dashboards and notifications.
- Run beside the existing YAML packages without controlling hardware.

Safety boundary:

```text
Python Core v1.1 is read-only.
No climate, switch, fan, heater, fridge, relay or compressor actions are performed by Python Core.
```

Primary documentation:

```text
docs/python-core-install-update.md
docs/python-core-branding.md
docs/python-core-v1.1-test-plan.md
docs/python-core-v1.1-release-notes.md
```

Recommended active debug/status card:

```text
dashboards/cards/brewassistant_core_debug_card_v1_1.yaml
```

---

## Python Core entity groups

### Core

```text
sensor.brewassistant_core_version
sensor.brewassistant_liquid_temperature
sensor.brewassistant_liquid_temperature_source
sensor.brewassistant_chamber_temperature
sensor.brewassistant_recipe_target_temperature
sensor.brewassistant_temperature_delta
sensor.brewassistant_temperature_target_mode
sensor.brewassistant_temperature_status
sensor.brewassistant_temperature_severity
sensor.brewassistant_source_summary
sensor.brewassistant_status_summary
sensor.brewassistant_problem_level
sensor.brewassistant_gravity
binary_sensor.brewassistant_temperature_fallback_active
binary_sensor.brewassistant_runtime_ready
```

### Process

```text
sensor.brewassistant_process_status
sensor.brewassistant_process_next_step
sensor.brewassistant_process_current_action_stage
sensor.brewassistant_process_next_action_stage
sensor.brewassistant_process_summary
```

### Smart recommendations

```text
sensor.brewassistant_smart_recommendation_summary
sensor.brewassistant_smart_heat_recommendation
sensor.brewassistant_smart_cooling_recommendation
sensor.brewassistant_smart_fan_recommendation
sensor.brewassistant_smart_heat_block_reason_core
sensor.brewassistant_smart_suggested_heat_pulse_minutes
sensor.brewassistant_smart_recommendation_mode
binary_sensor.brewassistant_smart_heat_needed_core
binary_sensor.brewassistant_smart_heat_permitted_core
binary_sensor.brewassistant_smart_cooling_recommended_core
binary_sensor.brewassistant_smart_fan_recommended_core
binary_sensor.brewassistant_smart_rising_too_fast_core
```

### Pill diagnostics

```text
sensor.brewassistant_smart_pill_status_core
sensor.brewassistant_smart_pill_temp_age_minutes_core
binary_sensor.brewassistant_smart_pill_stale_core
```

### Source health

```text
sensor.brewassistant_source_health_summary
sensor.brewassistant_source_health_level
sensor.brewassistant_configured_liquid_temp_entity
sensor.brewassistant_configured_chamber_temp_entity
sensor.brewassistant_configured_recipe_target_entity
sensor.brewassistant_configured_cold_crash_active_entity
sensor.brewassistant_configured_cold_crash_target_entity
sensor.brewassistant_configured_gravity_entity
binary_sensor.brewassistant_source_liquid_temp_available
binary_sensor.brewassistant_source_chamber_temp_available
binary_sensor.brewassistant_source_recipe_target_available
binary_sensor.brewassistant_source_cold_crash_active_available
binary_sensor.brewassistant_source_cold_crash_target_available
binary_sensor.brewassistant_source_gravity_available
```

### Runtime / Brewfather

```text
sensor.brewassistant_runtime_recipe_name
sensor.brewassistant_runtime_status
sensor.brewassistant_runtime_primary_target_temperature
sensor.brewassistant_runtime_cold_crash_target_temperature
sensor.brewassistant_runtime_target_fg
sensor.brewassistant_runtime_source_status
binary_sensor.brewassistant_runtime_brewfather_available
```

### Next action

```text
sensor.brewassistant_next_recommended_action
```

---

## Recommended repository layout

```text
brewassistant/
├── README.md
├── custom_components/
│   └── brewassistant/
│       ├── manifest.json
│       ├── __init__.py
│       ├── config_flow.py
│       ├── coordinator.py
│       ├── sensor.py
│       ├── binary_sensor.py
│       └── translations/
├── packages/
│   ├── brewassistant_helpers.yaml
│   ├── brewassistant_runtime.yaml
│   ├── brewassistant_workflow.yaml
│   ├── brewassistant_chamber.yaml
│   ├── brewassistant_notifications.yaml
│   ├── brewassistant_manual_mode.yaml
│   └── brewassistant_hot_side_workflow.yaml        # optional / future
├── dashboards/
│   ├── fermentation.yaml
│   ├── manual-mode.yaml
│   ├── chamber.yaml
│   ├── kegerator.yaml
│   ├── cards/
│   │   └── brewassistant_core_debug_card_v1_1.yaml
│   └── brewzilla.yaml                             # optional / future
└── docs/
    ├── setup.md
    ├── structure.md
    ├── entities.md
    ├── state-machine.md
    ├── manual-mode.md
    ├── dashboard.md
    ├── brewfather.md
    ├── custom-integration.md
    ├── legacy-migration.md
    ├── python-core-install-update.md
    ├── python-core-branding.md
    └── roadmap.md
```

---

## Core modules

### Helpers

`brewassistant_helpers.yaml` contains the reusable Home Assistant helpers used by the rest of the system.

Typical helper categories:

- Batch active / packaged state.
- Current phase.
- Manual batch name and notes.
- Target gravity and measured gravity.
- Automation toggles.
- Dashboard expand/collapse toggles.
- Notification preferences.

### Runtime

`brewassistant_runtime.yaml` normalizes external data into predictable internal sensors.

Examples:

- Recipe name.
- Recipe source.
- Fermentation status.
- Primary fermentation target temperature.
- Cold crash target temperature.
- Fermentation start date.
- Target FG.

### Workflow

`brewassistant_workflow.yaml` decides what is currently happening.

Examples:

- Idle.
- Fermenting.
- Ready for cold crash.
- Cold crash.
- Ready for transfer.
- Packaged / finished.

### Chamber

`brewassistant_chamber.yaml` connects recipe targets and workflow decisions to the fermentation chamber.

Examples:

- Apply Brewfather target to `climate.fermentation_chamber`.
- Show delta between liquid temperature and target.
- Detect cooling/heating/idle state.
- Support semi-automatic chamber updates.

### Manual Mode

`brewassistant_manual_mode.yaml` is a standalone manual fermentation tracker.

It is intended for:

- Cider.
- Small test batches.
- Hydrometer-only fermentation.
- Batches without Brewfather or RAPT data.

### Notifications

`brewassistant_notifications.yaml` contains alerts and persistent notifications.

Examples:

- Fermentation appears complete.
- Cold crash can start.
- Cold crash appears complete.
- Batch is ready for transfer.
- Manual SG reading reminder.

---

## Naming direction

Older BrewAssistant builds used many `fwk_*` names. Those names came from a Fresh Wort Kit focused workflow.

In v4, the recommended direction is more generic:

```text
fwk_*                  legacy
brew_process_*         workflow/process state
brew_batch_*           current batch state
brew_recipe_*          recipe/runtime data
brew_chamber_*         fermentation chamber data
brew_manual_*          manual mode data
brew_notification_*    notification controls/state
brewassistant_*        Python Core / custom integration entities
```

The migration does not need to happen all at once, but new files should avoid adding more `fwk_*` entities unless they are deliberately marked as compatibility entities.

---

## Status

BrewAssistant v4 is actively evolving.

Current Python Core status:

```text
v1.1 Read-only Core Stable + dashboard branding polish
```

Recommended next cleanup steps:

1. Keep backend packages, Python Core and dashboard cards aligned.
2. Document all current entities.
3. Migrate old `fwk_*` naming gradually.
4. Move dashboard decision logic into Python support sensors.
5. Keep manual mode separate from automated Brewfather/RAPT mode.
6. Add future hot-side/BrewZilla logic as optional modules.

---

## Disclaimer

This project is intended for hobby brewing automation and process tracking. Always verify sanitation, pressure limits, electrical safety, and fermentation decisions manually when needed.
