# Backend Domain Layout

Status: active development  
Last synced: 2026-09-10

BrewAssistant backend/domain logic is grouped by responsibility under `custom_components/brewassistant/`. Home Assistant platform entry files remain at the integration root.

The code-local `README.md` in each backend directory is the canonical short-form description of current ownership and implementation. Documents under `docs/backends/` are deeper design/test/history references and may intentionally describe an earlier milestone.

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
├── grainfather_fermenter/
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
| `grainfather_fermenter/` | Grainfather fermentation-device discovery/normalization; phase 1 read-only GF30 preparation and future supervised profile-target bridge |
| `fermentation/` | Legacy compatibility bridges only; no new business logic |
| `kegerator/` | Kegerator fan control/model, serving presets and legacy/policy guard/watchdog |
| `modules/` | Module/capability metadata registry; existing `grainfather` reservation remains hot-side only |
| `shared/` | Domain-neutral support helpers such as rolling temperature stats |

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

`grainfather_fermenter/` is intentionally distinct from the reserved `grainfather` hot-side module. The latter is for Grainfather brewing systems such as G30/G40-class hardware; the former is fermentation hardware, initially GF30.

## Important ownership splits

### Fermentation

```text
fermentation_tracking
  process observations/calculations/readiness

fermentation_chamber
  current chamber-air recommendation/control provider

grainfather_fermenter
  prepared Grainfather fermentation-hardware provider
  read-only until live GF30 validation

fermentation
  compatibility only
```

`fermentation_tracking` remains the process truth regardless of physical temperature provider. The chamber and Grainfather fermenter paths are alternatives, not parallel controllers. A future explicit provider selector must ensure only one physical target provider can propose/apply temperature changes at a time.

The intended GF30 control boundary is:

```text
fermentation_tracking
  -> target recommendation
  -> BrewAssistant Supervised Apply
  -> grainfather.adjust_current_step_temperature
  -> Grainfather/GF30 controller owns physical heating/cooling regulation
```

Direct heater, glycol pump, compressor or valve control must not be inferred from the current Grainfather cloud integration.

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

## Grainfather GF30 implementation horizon

Current status is deliberately **prepared but parked**: discovery/normalization exists on the feature branch, but no Grainfather command is issued and no model-specific assumptions are made without hardware evidence.

The next milestones are:

```text
Phase 1  read-only discovery/normalization                 <- current
Phase 2  live GF30 entity/service/readback validation      <- requires hardware
Phase 3  explicit physical-provider selection
Phase 4  registered Supervised Apply target executor
Phase 5  repeated field-test validation and safety guards
Phase 6  optional automatic target application             <- only if justified later
```

Automatic control is not a committed requirement. The Supervised Apply boundary is the expected first control mode after live validation.

## Documentation maintenance

When a backend contract changes, update its code-local README in the same PR. If a longer design/history document becomes stale, either sync it or label it clearly as historical/reference material instead of letting it silently compete with current code documentation.
