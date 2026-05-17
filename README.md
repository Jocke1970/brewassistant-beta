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
    └── roadmap.md
```

---

## Python Core

`custom_components/brewassistant/` contains the BrewAssistant Home Assistant custom integration.

Current scope:

- Read existing Home Assistant entities.
- Normalize liquid temperature, chamber fallback temperature, effective target temperature and gravity.
- Use cold crash target when cold crash is active.
- Expose dashboard-support sensors such as target mode, status summary, severity and problem level.
- Run beside the existing YAML packages without controlling hardware.

Current Python Core entities include:

```text
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

The Python Core is intentionally read-only at this stage. Hardware control should only move into Python after the recommendation/status layer has been tested safely.

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
