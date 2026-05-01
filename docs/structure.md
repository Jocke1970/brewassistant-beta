# Project Structure

BrewAssistant v4 is structured as a modular Home Assistant package set.

The main goal is to keep business logic in backend packages and keep dashboard YAML focused on presentation.

---

## Recommended repository structure

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
│   └── brewassistant_hot_side_workflow.yaml
├── dashboards/
│   ├── fermentation.yaml
│   ├── manual-mode.yaml
│   ├── chamber.yaml
│   ├── kegerator.yaml
│   └── brewzilla.yaml
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

## Package responsibilities

### `brewassistant_helpers.yaml`

Contains reusable helpers.

Examples:

- `input_boolean`
- `input_select`
- `input_text`
- `input_number`
- `input_datetime`

This file should not contain complex decision logic.

---

### `brewassistant_runtime.yaml`

Normalizes external brewing data into internal recipe/runtime sensors.

Sources may include:

- Brewfather.
- RAPT Cloud.
- Manual input.
- Static fallback helpers.

The runtime layer should answer questions like:

- What batch is active?
- What recipe is active?
- What is the target fermentation temperature?
- What is the target final gravity?
- What source is currently providing the data?

---

### `brewassistant_workflow.yaml`

Contains the process state machine.

The workflow layer should answer questions like:

- Is a batch active?
- Is fermentation complete?
- Is cold crash ready?
- Is the batch ready for transfer?
- What is the next recommended action?

---

### `brewassistant_chamber.yaml`

Controls and monitors fermentation chamber behaviour.

Responsibilities:

- Compare liquid temperature to target.
- Read chamber climate state.
- Show cooling/heating/idle status.
- Apply recipe target temperature when requested.
- Keep chamber automation separated from generic process state.

---

### `brewassistant_notifications.yaml`

Contains user-facing notifications and alert toggles.

Responsibilities:

- Warning notifications.
- Persistent notifications.
- Manual-mode reminders.
- Cold crash and transfer readiness alerts.

---

### `brewassistant_manual_mode.yaml`

Standalone manual fermentation tracker.

Responsibilities:

- Manual batch state.
- Manual gravity readings.
- Manual target FG.
- Manual packaging state.
- Simple derived manual status.

This module should be able to run without Brewfather, RAPT or BrewZilla.

---

### `brewassistant_hot_side_workflow.yaml`

Optional/future module for brew-day and hot-side logic.

Potential responsibilities:

- Mash step state.
- Boil state.
- Hop addition reminders.
- BrewZilla/RAPT control status.
- Brewfather BrewTracker data.

---

## Dashboard responsibilities

Dashboard cards should:

- Display current state.
- Provide buttons for user actions.
- Show status, warnings and next steps.
- Avoid duplicating backend workflow logic.

A card can contain display calculations for formatting, but the real state should come from backend sensors.

---

## Naming conventions

Recommended v4 naming direction:

```text
brew_process_*         workflow/process state
brew_batch_*           batch state
brew_recipe_*          recipe/runtime state
brew_chamber_*         chamber state
brew_manual_*          manual mode
brew_notification_*    notifications
brew_hot_side_*        hot-side workflow
brewzilla_*            BrewZilla/RAPT device data
```

Legacy names:

```text
fwk_*                  old Fresh Wort Kit specific namespace
```

New development should avoid adding new `fwk_*` entities.

---

## Design rule

If a piece of logic affects brewing decisions, place it in a package.

If it only affects how something looks, place it in the dashboard card.

