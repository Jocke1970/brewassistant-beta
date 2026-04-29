# BrewAssistant v4 Architecture

## Core principle

BrewAssistant v4 uses self-contained backend modules.

A module may expose helpers, template sensors, scripts, automations and timers. A module should not require another module to exist unless explicitly documented.

## Module categories

### Fermentation module

Owns the fermentation process state machine and legacy `fwk_*` fermentation logic.

Typical responsibilities:

- batch active/inactive state
- process status
- next step
- gravity and temperature wrappers
- cold crash readiness
- transfer readiness
- process action buttons/scripts

### Chamber module

Owns fermentation chamber control and chamber diagnostics.

Typical responsibilities:

- chamber enabled state
- chamber alignment
- chamber status
- apply target temperature script
- climate guardrails

### Kegerator module

Owns fridge/kegerator support.

Typical responsibilities:

- kegerator enabled state
- compressor active sensor
- fan automation
- fridge status helpers

### Hot Side module

Owns brew day workflow.

Typical responsibilities:

- hot side enabled state
- mash/boil/whirlpool step data
- brew day action buttons
- brew day timers

Current note: the UI/core loads, but the Hot Side action/timer layer still needs polish.

### Brewfather adapter

Adapter only. It should not own fermentation logic.

Typical responsibilities:

- read Brewfather entities
- normalize runtime recipe values
- provide `sensor.recipe_runtime_*`
- optionally feed fermentation inputs

The fermentation module must still work without this adapter.

### Health module

Observer only.

Typical responsibilities:

- detect installed modules
- report OK/warning/error states
- tolerate missing modules
- never control brewing actions

### Notifications module

Owns notification automations only.

Typical responsibilities:

- alerts
- warnings
- brew step reminders
- health/problem notifications

## Data flow

```text
Brewfather / RAPT / manual helpers
          ↓
Adapters and input helpers
          ↓
Self-contained BrewAssistant modules
          ↓
Dashboard cards
```

## UI separation

Dashboard cards may reference module entities, but modules should not contain card YAML.

This keeps backend restart-safe and UI iterations independent.
