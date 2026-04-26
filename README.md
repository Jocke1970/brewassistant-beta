# BrewAssistant v4 🍺

Premium Home Assistant dashboard and helper package for homebrewing workflows.

BrewAssistant v4 focuses on a practical brewing control panel with clear status cards, expandable workflows, problem detection, and hardware abstraction so physical devices can be replaced without rebuilding the dashboard.

## Current status

**Recommended release label:** `v1.2-dashboard-cleanup`

Included modules:

- Problem Center v1.1
- FWK / Fermentation Process card
- Fermentation Chamber card
- Kegerator Premium card
- Hot Side Premium Workflow v1.1
- Helper abstraction for future Shelly 4-outlet power strip
- RAPT Pill / gravity / temperature status integration
- Brewfather/runtime recipe fallback support

## Design principles

BrewAssistant uses a simple separation:

```text
Dashboard cards
  use stable BrewAssistant entities

Helpers / templates
  map BrewAssistant entities to physical integrations

Physical devices
  Shelly, RAPT, Brewfather, climate entities, sensors
```

This makes it easier to replace hardware later. For example, when replacing a temporary power sensor with a Shelly power strip, the dashboard should keep using:

```yaml
sensor.brewassistant_kegerator_power_w
binary_sensor.kegerator_compressor_active
```

Only the helper/template mapping should need to change.

## Main UI modules

### Problem Center

A top-level health panel showing:

- overall BrewAssistant health
- active problem count
- kegerator status
- chamber status
- RAPT SG status
- Brewfather status
- battery status
- compressor/power status

### FWK / Fermentation Process

Workflow card for fermentation batches, including:

- top status card
- enable/power button
- fermentation temperature
- gravity
- planned temperature
- days left
- Start / Spunding / Dry Hop / Cold Crash / Transfer actions
- expandable details section

### Fermentation Chamber

Climate-control card for fermentation chamber logic.

### Kegerator Premium

Premium kegerator card with:

- current/target/delta/cooling
- compressor state
- fan state
- expandable Temps/System sections

### Hot Side Premium Workflow

Brew day workflow card with:

- power/enable button
- recipe and batch
- current phase/instruction
- next action
- timer
- mash/chill targets
- Start / Previous / Next / Pause / Timer / Reset
- settings section

## Required custom cards

Install through HACS or manually:

- `custom:button-card`
- `custom:stack-in-card`
- `custom:vertical-stack-in-card`
- `custom:mushroom-template-card`
- `custom:mushroom-entity-card`
- `card-mod`

## Suggested repository structure

```text
BrewAssistant-v4/
├── README.md
├── CHANGELOG.md
├── docs/
│   ├── INSTALLATION.md
│   ├── DASHBOARD.md
│   ├── HELPERS.md
│   ├── PROBLEM_CENTER.md
│   ├── POWER_CENTER_PREP.md
│   ├── HOT_SIDE.md
│   ├── FWK_WORKFLOW.md
│   └── ENTITY_MAP.md
└── packages/
    └── brewassistant_helpers.yaml
```

## Safety note

BrewAssistant is a dashboard/helper layer. It should not be treated as a certified safety controller. Use physical temperature limits, safe wiring, proper fusing, and manufacturer-approved power ratings for all heating/cooling equipment.
