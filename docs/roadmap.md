# Roadmap

This document outlines the evolving BrewAssistant v4 roadmap.

The roadmap has shifted from:

```text
YAML packages with optional Python helpers
```

toward:

```text
Python integration as source of truth
YAML as presentation layer only
```

---

## Current project status

### Already working in Python Core

```text
[x] Custom integration skeleton
[x] Config flow
[x] Read-only coordinator
[x] Runtime normalization
[x] Source health engine
[x] Next recommended action engine
[x] Carbonation calculations and estimates
[x] Dashboard support entities
[x] Process/status mirror entities
[x] Swedish + English translations
[x] Debug/runtime dashboard cards
[x] Read-only safe-mode architecture
[x] Brewday Runtime Engine
[x] Brewfather Brew Tracker normalization
[x] Brewday current-step timer resolver
[x] Brewday stage timer resolver
[x] Brewday timeline generation
[x] Brewday refresh compensation hook
[x] Guarded manual Brewfather refresh service
[x] Manual Brewday Python engine
[x] Manual Brewday source adapter
[x] Manual Brewday persistent session in hass.data
[x] Manual Brewday Python services
[x] Manual Brewday Control Card v3
[x] BrewZilla runtime skeleton
```

### Current architectural phase

```text
Python Core stabilization
↓
Brewday Runtime validation
↓
BrewZilla/RAPT reality testing
↓
Workflow/lifecycle migration
↓
Timed Fermentation Runtime
↓
YAML retirement
↓
Future orchestration/control
```

---

# v4.3 Brewday Runtime Stabilization

Goal: stabilize Brewday Runtime before expanding into hardware orchestration.

Completed:

```text
[x] Brewfather Brew Tracker source adapter
[x] Manual Brewday source adapter
[x] Runtime state normalization
[x] Current/next step resolver
[x] Timeline generation
[x] Snapshot age tracking
[x] Live countdown between Brewfather snapshots
[x] Separate current-step remaining from stage remaining
[x] Awaiting snapshot state
[x] Guarded automatic refresh at step boundary
[x] Manual Brewfather refresh service with 15 minute cooldown
[x] Manual Brewday Runtime engine
[x] Manual Brewday persistent session in hass.data
[x] Manual Brewday services
[x] Manual Brewday Control Card v3
```

Remaining:

```text
[ ] Validate Manual Brewday service flow in Home Assistant
[ ] Add Manual timed-step auto-advance
[ ] Add Manual timed-step awaiting-confirm behavior at 0 seconds
[ ] Add Manual session persistence across Home Assistant restart
[ ] Add optional Manual plan import/building from Brewfather recipe data
[ ] Add optional Manual plan editing/profile selection
[ ] Add services documentation and dashboard examples
```

---

# v4.4 BrewZilla/RAPT hardware reality mapping

Goal: map real BrewZilla/RAPT entities into BrewAssistant hardware abstractions.

Current status:

```text
[x] BrewZilla read-only runtime skeleton
[x] BrewZilla UI stub
[ ] Identify actual RAPT/HA entity names
[ ] Map current temperature source
[ ] Map target temperature source
[ ] Map power/heating source
[ ] Map pump state source
[ ] Map connected/availability source
[ ] Map profile/mode/status source if exposed
[ ] Expose normalized BrewAssistant BrewZilla sensors
[ ] Keep all hardware actions disabled until reviewed
```

Safety rule:

```text
Read and visualize first.
Recommend second.
Control only after explicit design and validation.
```

---

# v4.5 Workflow/lifecycle engine

Goal: move fermentation/batch lifecycle ownership into Python.

Tasks:

```text
[ ] Create integration-owned lifecycle model
[ ] Add process status engine
[ ] Add next-step engine
[ ] Add process summary engine
[ ] Add packaging readiness engine
[ ] Add transfer readiness engine
[ ] Add lifecycle stage engine
[ ] Add integration-owned batch state
[ ] Add batch lifecycle buttons/services
[ ] Add internal BrewAssistant event model
[ ] Switch dashboards fully to Python lifecycle entities
```

---

# v4.6 Timed Fermentation Runtime

Goal: create a Python-owned fermentation schedule/runtime engine using the same architecture as Brewday Runtime.

Target flow:

```text
Brewfather fermentation schedule
Manual fallback schedule
Current batch age
Current gravity/temperature context
↓
Timed Fermentation Runtime
↓
Current fermentation stage
Current target temperature
Next temperature step
Time to next step
Chamber recommendation/apply layer
```

Planned entities:

```text
[ ] sensor.brewassistant_fermentation_runtime_state
[ ] sensor.brewassistant_fermentation_schedule_source
[ ] sensor.brewassistant_fermentation_current_stage
[ ] sensor.brewassistant_fermentation_current_target_temp
[ ] sensor.brewassistant_fermentation_next_stage
[ ] sensor.brewassistant_fermentation_next_target_temp
[ ] sensor.brewassistant_fermentation_time_to_next_step
[ ] sensor.brewassistant_fermentation_schedule_age_days
[ ] sensor.brewassistant_fermentation_timeline
```

Tasks:

```text
[ ] Parse Brewfather fermentation step schedule
[ ] Support manual timed fermentation schedule fallback
[ ] Calculate current fermentation day/age
[ ] Resolve active stage and target temperature
[ ] Resolve next stage and time remaining
[ ] Expose fermentation timeline attributes
[ ] Provide chamber target recommendation
[ ] Keep apply-to-chamber as explicit/separate safe layer
```

---

# v4.7 YAML retirement

Goal: progressively remove backend logic from YAML packages.

Rules:

```text
YAML may render.
Python should decide.
```

Tasks:

```text
[ ] Identify calculation-only template sensors
[ ] Rebuild them in Python
[ ] Replace dashboard dependencies
[ ] Remove duplicated Jinja logic
[ ] Reduce helper dependency where practical
[ ] Remove compatibility layers after validation
[ ] Leave cards/dashboards intact
```

---

# v4.9 Runtime adapter architecture

Goal: normalize all runtime sources into BrewAssistant-native models.

Target flow:

```text
Brewfather
RAPT
Manual input
BrewZilla
Future APIs
↓
Python runtime adapters
↓
BrewAssistant entities
↓
Dashboards
```

Adapter priorities:

```text
[x] Brewfather Brew Tracker source adapter
[x] Manual Brewday source adapter
[x] BrewZilla read-only hardware skeleton
[ ] Timed Fermentation Runtime adapter
[ ] BrewZilla hardware capability adapter
[ ] RAPT-specific hardware/profile adapter
[ ] Future local/MQTT hardware adapter
```

---

# Long-term direction

BrewAssistant is evolving from:

```text
Home Assistant YAML package collection
```

into:

```text
Modular brewing platform for Home Assistant
```
