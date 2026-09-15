# Backend Domain Layout

Status: active development  
Last synced: 2026-09-15

BrewAssistant backend/domain logic is grouped by responsibility under `custom_components/brewassistant/`. Home Assistant platform entry files remain at the integration root.

The code-local `README.md` in each implemented backend directory is the canonical short-form description of current ownership and implementation. Documents under `docs/backends/` are deeper design/test/history references and may also describe planned modules before code exists.

## Current layout

```text
custom_components/brewassistant/
├── README.md
├── __init__.py
├── manifest.json
├── config_flow.py
├── const.py
├── coordinator.py
├── entity.py
├── sensor.py
├── binary_sensor.py
├── switch.py
├── button.py
├── select.py
├── number.py
├── services.yaml
├── brand/
├── brewday/
│   └── README.md
├── brewzilla/
│   └── README.md
├── carbonation_backend/
│   └── README.md
├── climate_backend/
│   └── README.md
├── cooling/
│   └── README.md
├── fermentation/
│   └── README.md
├── fermentation_chamber/
│   └── README.md
├── fermentation_tracking/
│   └── README.md
├── kegerator/
│   └── README.md
├── modules/
│   └── README.md
├── shared/
│   └── README.md
└── translations/
```

## Package responsibilities

| Package | Responsibility |
| --- | --- |
| `brewday/` | Normalized Brewday Runtime, Manual Brewday, stage engine, physical timing, addition alerts and persisted Flight Recorder |
| `brewzilla/` | BrewZilla/RAPT hot-side adapter, physical control chain, Mash-In contract, telemetry recovery/fail-passive and ABORT |
| `carbonation_backend/` | Persisted carbonation session, pressure/volume guidance and progress estimates |
| `climate_backend/` | Kegerator Climate Supervisor; dynamic climate-target selection/application |
| `cooling/` | Cooling Runtime v2 for CFC/immersion/manual cooling, sanitation context and cooling advice |
| `fermentation_tracking/` | Independent fermentation observations, source resolution, SG/Brix correction, progress/stability/readiness |
| `fermentation_chamber/` | Fermentation/cold-crash chamber-air recommendation plus Supervised Apply bridge |
| `fermentation/` | Legacy compatibility bridges only; no new business logic |
| `kegerator/` | Kegerator fan control/model, serving presets and legacy/policy guard/watchdog |
| `modules/` | Module/capability metadata registry |
| `shared/` | Domain-neutral support helpers such as rolling temperature stats |

## Planned HLT and shared power coordination

The following layout is design intent only and is **not present as executable backend code yet**:

```text
custom_components/brewassistant/
├── hlt/
│   └── README.md               # created when implementation begins
└── power_budget/               # likely coordination domain; final name TBD
    └── README.md               # created when implementation begins
```

Planned responsibility split:

```text
hlt/
  sparge-water target/readiness/state machine
  HLT heater demand
  HLT local temperature/safety behavior
  no-sparge handling

power_budget/
  shared electrical reservations/grants
  BrewZilla/HLT capacity accounting
  HLT revoke + verified release before BrewZilla reclaim
  diagnostics/audit for circuit-budget decisions

brewzilla/
  remains owner of BrewZilla process demand and physical write chain
```

Planning references:

- [`backends/hlt-backend.md`](./backends/hlt-backend.md)
- [`power-budget-arbiter.md`](./power-budget-arbiter.md)

The coordination layer is intentionally proposed as its own domain rather than a generic helper in `shared/`: it owns safety-relevant electrical allocation state and handoff sequencing. `shared/` should continue to contain reusable helpers that do not own a process or safety decision.

## Platform-root rule

Keep Home Assistant platform entry files at the integration root:

```text
sensor.py
binary_sensor.py
switch.py
button.py
select.py
number.py
```

They should act primarily as routers/registrars and import backend entities from domain packages.

## Naming rule

Avoid backend package names that collide with top-level Home Assistant platform/module files. Existing examples:

```text
carbonation.py          + carbonation_backend/
climate platform/module + climate_backend/
```

The final power-arbiter package name should also avoid collision with any future Home Assistant platform naming.

## Important ownership splits

### Fermentation

```text
fermentation_tracking
  process observations/calculations/readiness

fermentation_chamber
  chamber-air recommendation/control bridge

fermentation
  compatibility only
```

### Kegerator

```text
climate.kegerator_kylskap
  normal refrigeration/compressor behavior

climate_backend/
  dynamic target selection/application

kegerator/fan_control.py
  circulation fan only

kegerator/guard.py
  separate legacy/policy physical-switch guard + restart watchdog
```

### External process temperature

```text
Heat strike -> Pre-boil
  hot-side Brewday/BrewZilla ownership

BOIL start
  handoff

Chill -> Transfer
  Cooling ownership as CFC outlet/process temperature when applicable
```

### Shared electrical capacity — planned

```text
BrewZilla
  publishes desired process demand
  keeps ownership of its physical controls

HLT
  publishes sparge-water heat demand
  may energize only with a valid electrical grant

Power Budget Arbiter
  owns reservation/grant accounting and safe capacity transfer
```

A temporary low BrewZilla watt reading is not, by itself, permission for HLT to start. Capacity must be reserved and coordinated.

## Documentation maintenance

When an implemented backend contract changes, update its code-local README in the same PR. If a longer design/history document becomes stale, either sync it or label it clearly as historical/reference material instead of letting it silently compete with current code documentation.

For planned modules, keep them under `docs/` until executable code exists. When implementation begins, create the code-local README and explicitly reconcile any planning decisions that changed.
