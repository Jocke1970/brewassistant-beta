# Backend Domain Layout

Status: active development  
Last synced: 2026-09-11

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
│   ├── README.md
│   └── adapter.py
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
| `fermentation_tracking/` | Hardware-neutral fermentation observations, source resolution, SG/Brix correction, progress/stability/readiness and process-level beer target recommendation |
| `fermentation_chamber/` | Current writable physical fermentation provider: chamber-air target translation plus Supervised Apply bridge |
| `grainfather_fermenter/` | Parked Phase 1 Grainfather fermentation-provider scaffold; read-only device/session discovery and future-control prerequisite diagnostics |
| `fermentation/` | Legacy compatibility bridges only; no new business logic |
| `kegerator/` | Kegerator fan control/model, serving presets and legacy/policy guard/watchdog |
| `modules/` | Module/capability metadata registry |
| `shared/` | Domain-neutral support helpers such as rolling temperature stats |

The existing `grainfather` module-registry entry is a separate future **hot-side** Grainfather adapter and must not be repurposed for GF30 fermentation control.

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

## Important ownership splits

### Fermentation

The generic fermentation architecture is:

```text
fermentation_tracking
  process observations / calculations / readiness
  desired beer/liquid temperature target
        |
        v
selected physical fermentation provider
  translate process target into controller-native target
        |
        v
local controller
  own actual heat/cool regulation
```

Current writable implementation:

```text
fermentation_tracking
        |
        v
fermentation_chamber
  chamber-air target translation
        |
        v
Supervised Apply
        |
        v
climate.fermentation_chamber
  local heat/cool controller
```

Parked future-provider scaffold:

```text
fermentation_tracking
        |
        v
grainfather_fermenter
  read-only discovery/normalization today
        |
        v
future Supervised Apply after live validation
        |
        v
Grainfather controller
  local heat/cool controller
```

`fermentation_chamber` is therefore the first writable physical provider implementation, not the owner of fermentation strategy. The downstream Home Assistant climate controller owns raw heater/cooler switching after the setpoint is accepted.

`grainfather_fermenter` exists now so the Grainfather integration surface and fail-passive selection rules are not lost before physical GF30 hardware is available. It performs no service calls and has no provider write authority.

Only one physical provider may have write authority for a fermentation session. A generic provider selector/authority layer is an architectural prerequisite before enabling a second writable provider; it is not yet implemented.

The legacy `fermentation/` package remains compatibility-only and must not become a catch-all owner for strategy, provider selection or hardware control.

See [`backends/fermentation-control.md`](./backends/fermentation-control.md) for the full provider contract.

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

## Future fermentation-provider rule

Do not add a new fermentation hardware backend by copying chamber thermostat behavior into it.

A new provider should instead answer:

```text
What process target does BrewAssistant want?
How is that target represented by this controller?
How do we write it safely?
How do we verify readback?
Which local controller owns actual heat/cool switching?
```

New providers begin fail-passive/read-only. Target writes should move through Supervised Apply after live validation. Direct actuator control is only justified if the downstream hardware does not already provide the required local regulation and the architecture explicitly assigns that ownership to BrewAssistant.

## Documentation maintenance

When a backend contract changes, update its code-local README in the same PR. If a longer design/history document becomes stale, either sync it or label it clearly as historical/reference material instead of letting it silently compete with current code documentation.
