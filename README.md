# BrewAssistant v4

**BrewAssistant v4** is a modular Home Assistant brewing assistant for fermentation tracking, chamber control, manual batches, notifications, dashboards, and future hot-side/brew-day integrations.

The project is designed around a clean core with optional modules. It can be used for simple manual fermentation tracking, Brewfather-assisted recipe runtime data, RAPT/Pill readings, fermentation chamber automation, kegerator visualisation, and later BrewZilla/RAPT hot-side workflows.

---

## Project goals

BrewAssistant v4 aims to provide:

- A clean Home Assistant package structure.
- Brewing workflows that survive Home Assistant restarts.
- A Swedish-friendly UI with English/core entity naming.
- Fermentation, cold crash, transfer, packaging, and storage workflow support.
- Optional integration with Brewfather, RAPT, BrewZilla and manual hydrometer readings.
- Premium dashboard cards that visualise the current batch state.
- A migration path away from older `fwk_*` helper/entity names.

---

## Current v4 philosophy

BrewAssistant v4 separates the brewing system into clear layers:

| Layer | Purpose |
| --- | --- |
| Helpers | Store user choices, toggles, manual input and workflow state. |
| Runtime | Normalize recipe, batch, Brewfather and sensor data. |
| Workflow | Decide current process state, next step and readiness. |
| Chamber | Apply and monitor fermentation chamber targets. |
| Manual Mode | Track batches without Brewfather/RAPT automation. |
| Notifications | Alert when attention is needed. |
| Dashboard | Visualize the system without owning business logic. |

The dashboard should display and control the system, but should not contain hidden workflow logic that belongs in the backend packages.

---

## Recommended repository layout

```text
brewassistant/
├── README.md
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
    ├── legacy-migration.md
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
```

The migration does not need to happen all at once, but new files should avoid adding more `fwk_*` entities unless they are deliberately marked as compatibility entities.

---

## Status

BrewAssistant v4 is actively evolving.

Recommended next cleanup steps:

1. Keep backend packages and dashboard cards aligned.
2. Document all current entities.
3. Migrate old `fwk_*` naming gradually.
4. Keep manual mode separate from automated Brewfather/RAPT mode.
5. Add future hot-side/BrewZilla logic as optional modules.

---

## Disclaimer

This project is intended for hobby brewing automation and process tracking. Always verify sanitation, pressure limits, electrical safety, and fermentation decisions manually when needed.
