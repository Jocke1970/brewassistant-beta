# Package Layout

## Goal

Define a practical repository and Home Assistant file layout for BrewAssistant.

## Recommended Repository Structure

```text
brewassistant/
├── README.md
├── docs/
│   ├── structure.md
│   ├── roadmap.md
│   ├── state-machine.md
│   ├── data-model.md
│   ├── entity-map.md
│   ├── integration-strategy.md
│   ├── ui-spec.md
│   ├── implementation-plan.md
│   └── acceptance-criteria.md
├── packages/
│   ├── brewassistant_runtime.yaml
│   ├── brewassistant_workflow.yaml
│   ├── brewassistant_notifications.yaml
│   └── brewassistant_helpers.yaml
├── dashboards/
│   ├── brewassistant_main_card.yaml
│   ├── brewassistant_action_cards.yaml
│   └── brewassistant_details.yaml
├── examples/
│   ├── example_recipe_runtime.yaml
│   ├── example_dashboard_view.yaml
│   └── example_entities.md
└── assets/
    └── screenshots/
```

## Suggested Home Assistant Layout

```text
/config/
├── packages/
│   └── brewassistant/
│       ├── runtime.yaml
│       ├── workflow.yaml
│       ├── notifications.yaml
│       └── helpers.yaml
├── dashboards/
│   └── brewassistant/
│       ├── main_card.yaml
│       ├── action_cards.yaml
│       └── details.yaml
└── www/
    └── brewassistant/
```

## Package Split Recommendation

### helpers.yaml
Contains:
- input_booleans
- input_numbers
- input_datetimes
- helper defaults

### runtime.yaml
Contains:
- normalized recipe runtime sensors
- live runtime sensors
- source-priority templates

### workflow.yaml
Contains:
- decision engine sensors
- preview/active binary sensors
- process status sensors
- scripts

### notifications.yaml
Contains:
- reminders
- warnings
- state-transition automations

## Why Split This Way

Benefits:
- easier debugging
- smaller files
- cleaner Git diffs
- easier reuse
- easier future HACS-style structure

## Docs Folder

Recommended for GitHub:
- keep all design docs in `docs/`
- keep root `README.md` short and project-oriented
