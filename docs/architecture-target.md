# BrewAssistant Target Architecture

This document describes the intended long-term architecture for BrewAssistant after the current BrewZilla-focused beta phase.

The goal is to keep BrewAssistant centered on the brewing process rather than on a single hardware platform.

```text
BrewAssistant Core
├─ Base Workflow
│  ├─ Brewday Runtime
│  └─ Fermentation Tracking
├─ Source Providers
│  ├─ Brewfather Home Assistant integration
│  ├─ RAPT Cloud Link
│  ├─ BrewCreator / Fercubator
│  ├─ Grainfather
│  └─ Generic Home Assistant entities
├─ Hardware Adapters
│  ├─ BrewZilla
│  ├─ Grainfather
│  ├─ Fercubator / BrewCreator
│  ├─ Generic hot-side adapter
│  └─ Generic chamber/climate adapter
└─ Optional Modules
   ├─ Kegerator / Serving
   ├─ Carbonation
   ├─ Fermentation Chamber Control
   ├─ Counterflow Chiller
   ├─ Notifications
   └─ Diagnostics
```

---

## Design principles

```text
1. BrewAssistant should be process-first, not hardware-first.
2. Brewday and fermentation tracking form the default base workflow.
3. Hardware integrations should be adapters, not core assumptions.
4. External integrations should be source providers, not hard dependencies.
5. Dashboards should present state and expose explicit operator actions.
6. Python backend should own normalization, state interpretation, calculations and policy decisions.
7. Entities should only be created for enabled or relevant capabilities where possible.
8. Control must be capability-scoped, not global.
```

The current BrewZilla beta remains valuable because it proves the runtime, stage engine, orchestration, dashboard and safety model. It should not define the whole product shape.

---

## Base workflow

The default/base installation should provide a brewing lifecycle that works even without connected brewing hardware.

Recommended base:

```text
Core
Brewday Runtime
Manual Brewday
Fermentation Tracking
Basic carbonation guidance/calculations
Source health / diagnostics
```

Fermentation belongs in the base as tracking/lifecycle support:

```text
Brewday → Fermentation → Cold crash → Packaging → Serving
```

However, active fermentation chamber control should remain optional.

---

## Optional modules

Optional modules should be enabled explicitly in config/options flow or a future module registry.

```text
BrewZilla hardware
Grainfather hardware
Kegerator / Serving
Fermentation Chamber Control
Fercubator / BrewCreator chamber adapter
Carbonation session tracking
Counterflow Chiller
Notifications
Advanced diagnostics
```

A module should not assume all other modules exist. For example:

```text
Brewday can run without BrewZilla.
Carbonation can calculate guidance without a kegerator.
Fermentation tracking can run without chamber control.
Kegerator fan-auto can run without active fermentation.
```

---

## Source providers

Source providers expose data from external integrations or manually configured Home Assistant entities.

Examples:

```text
Brewfather Home Assistant integration
RAPT Cloud Link for Home Assistant
BrewCreator / Fercubator integration
Grainfather community integration
RAPT Pill / BLE / gravity sources
Shelly / power telemetry
Generic HA climate/sensor/switch entities
```

Source providers should answer questions like:

```text
Is a source available?
How fresh is the source?
What entities are mapped?
What values are usable?
Is this source read-only or action-capable?
```

They should not own BrewAssistant workflow logic.

---

## Hardware adapters

Hardware adapters normalize device-specific entities into common BrewAssistant capabilities.

### Hot-side adapter

Used for BrewZilla, Grainfather or other brewing systems.

Common capabilities:

```text
current_temperature
mash_temperature
wort_temperature
target_temperature
heating_state
pump_state
power_w
set_target_temperature
set_heater_state
set_pump_state
abort
```

### Fermentation chamber adapter

Used for generic Home Assistant climate entities, Fercubator/BrewCreator or other chamber controllers.

Common capabilities:

```text
current_temperature
target_temperature
mode
heating_state
cooling_state
set_target_temperature
set_mode
turn_off
```

### Serving/cooling adapter

Used for kegerator, serving fridge or cooling storage.

Common capabilities:

```text
current_temperature
target_temperature
compressor_active
fan_running
set_serving_target
set_storage_target
fan_auto_control
```

Adapters should be small and replaceable. Domain logic should remain in BrewAssistant core/runtime modules.

---

## Capability policy

Control should be scoped per capability rather than globally.

Suggested policy values:

```text
read_only          Observe only. Never apply actions.
confirm            Prepare action and require operator confirmation.
direct             Apply action directly when safe.
guidance_only      Calculate and recommend, but no device action exists.
disabled           Capability is not available or not enabled.
```

Examples:

```text
BrewZilla heater control        = confirm during first real brewday
BrewZilla pump control          = confirm or direct depending on stage
Kegerator fan-auto              = direct, because it only controls circulation fan
Fermentation chamber target     = read_only or confirm until validated
Carbonation pressure guidance   = guidance_only
```

This keeps BrewAssistant aligned with a supervised brewing model.

---

## Entity creation strategy

Future setup should reduce entity sprawl.

Preferred behavior:

```text
Core entities are always created.
Base workflow entities are created by default.
Optional module entities are created only when the module is enabled or relevant.
Hardware adapter entities are created only when their source/config is present.
Legacy/local helpers should not be recreated by the Python integration.
```

This is important for long-term maintainability and to avoid large groups of unavailable legacy entities.

---

## Installation target

A future config/options flow should guide the user through:

```text
1. Choose base profile
   - Core only
   - Brewday + Fermentation Tracking
   - Full beta / advanced

2. Enable optional modules
   - BrewZilla
   - Grainfather
   - Kegerator / Serving
   - Fermentation Chamber Control
   - Carbonation
   - Counterflow Chiller
   - Notifications

3. Choose source providers
   - Brewfather
   - RAPT Cloud Link
   - BrewCreator / Fercubator
   - Grainfather
   - Generic HA entities

4. Map entities
   - Temperature sensors
   - Power sensors
   - Climate entities
   - Fan/pump/heater switches
   - Gravity sources

5. Choose capability policies
   - read_only
   - confirm
   - direct
   - guidance_only
```

---

## Roadmap from current beta

The current beta path should continue, but with a clearer architecture target.

Recommended next steps:

```text
1. Keep current BrewZilla beta flow intact.
2. Define module and capability manifests.
3. Introduce enabled/available state per module.
4. Normalize BrewZilla as the first hot-side adapter.
5. Normalize kegerator as the first serving/cooling adapter.
6. Split fermentation tracking from fermentation chamber control.
7. Prepare future adapters for Grainfather and Fercubator/BrewCreator.
8. Add config/options flow later.
9. Clean legacy HA entities module-by-module, not as a bulk destructive step.
```

The direction is therefore evolutionary, not a rewrite.
