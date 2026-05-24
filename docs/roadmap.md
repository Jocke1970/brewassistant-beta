# Roadmap

This document outlines the evolving BrewAssistant v4 roadmap.

The roadmap has shifted from:

```text
YAML packages with optional Python helpers
```

toward:

```text
Python integration as source of truth
YAML/dashboard as presentation layer only
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
[x] Python-owned process/status mirror entities
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
[x] BrewZilla runtime sensors
[x] BrewZilla orchestration safety switches
[x] BrewZilla Apply Target service
[x] Brewday Stage Engine v1
[x] Brewday Stage Engine v2 guidance fields
[x] Stage Engine v2 dashboard support sensors
[x] Python-only cleanup of legacy YAML process references
```

### Current architectural phase

```text
Python Core stabilization
↓
Brewday Runtime validation
↓
Stage Engine validation
↓
BrewZilla/RAPT reality testing
↓
BrewZilla UI + explicit-action orchestration
↓
Counterflow wort cooling support
↓
Timed Fermentation Runtime
↓
Full YAML retirement
↓
Future guarded automation/control
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
[x] Stop syncing Manual Brewday services to legacy YAML helpers
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
[x] BrewZilla runtime sensors
[x] BrewZilla UI stub
[x] BrewZilla premium runtime card
[x] Map current temperature source
[x] Map target temperature source
[x] Map power/heating source
[x] Map pump utilization source
[x] Map connected/availability source
[x] Expose normalized BrewAssistant BrewZilla sensors
[x] Add orchestration safety switches
[x] Add apply-target service with safety checks
[x] Integrate Stage Engine data into BrewZilla top card
[ ] Polish BrewZilla top-card power button state colors
[ ] Add Apply Target Now card/button gated by safety state
[ ] Confirm all runtime values against real brewday data
[ ] Add diagnostics for stale/disconnected RAPT/BrewZilla values
```

Safety rule:

```text
Read and visualize first.
Recommend second.
Explicit user action third.
Automate only after explicit design and validation.
```

---

# v4.5 Brewday Stage Engine

Goal: make BrewAssistant understand what is happening during the brewday, not just display raw runtime values.

Completed:

```text
[x] Create brewday_stage_engine.py
[x] Create brewday_stage_sensor.py
[x] Wire Stage Engine sensors into Brewday runtime factory
[x] Interpret runtime stage/step/next-step text
[x] Interpret BrewZilla temperature/target/delta/power/pump context
[x] Support Idle, Strike Water, Heating Strike, Mash In, Mash, Mash Out
[x] Support Heating To Boil, Boiling and Hop Addition
[x] Support Whirlpool and Hop Stand
[x] Support Wort Cooling / counterflow cooling detection
[x] Support Pitch Ready, Transfer and Completed
[x] Recognize Cleaning as an external housekeeping/wrap-up label only
[x] Expose stage reason/status/icon/progress/temperature/power sensors
[x] Add v2 fields: stage_group, stage_priority, suggested_action, control_hint
[x] Add Stage Engine v2 UI card
```

Cleaning boundary:

```text
Cleaning is not a BrewAssistant core workflow.
It may appear as a Stage Engine wrap-up label if a runtime/source reports it,
but no dedicated BrewAssistant cleaning module or UI is planned.
Cleaning remains a separate manual housekeeping process.
```

Current Stage Engine sensors:

```text
sensor.brewassistant_brewday_stage
sensor.brewassistant_brewday_stage_reason
sensor.brewassistant_brewday_stage_status_line
sensor.brewassistant_brewday_stage_icon
sensor.brewassistant_brewday_stage_group
sensor.brewassistant_brewday_stage_priority
sensor.brewassistant_brewday_stage_suggested_action
sensor.brewassistant_brewday_stage_control_hint
sensor.brewassistant_brewday_stage_remaining_minutes
sensor.brewassistant_brewday_stage_progress
sensor.brewassistant_brewday_stage_temperature
sensor.brewassistant_brewday_stage_target_temperature
sensor.brewassistant_brewday_stage_power
```

Remaining:

```text
[ ] Validate stage transitions during real BrewZilla brewday
[ ] Tune thresholds for Heating Strike / Mash / Boil / Cooling
[ ] Add estimated time-to-target where possible
[ ] Add cooling efficiency and pitch-ready prediction
[ ] Add event/notification hooks for attention stages
[ ] Add explicit Apply Target UI gated by control_hint and safety switches
```

---

# v4.6 Counterflow Wort Cooling

Goal: model wort cooling as a first-class post-boil process.

Initial scope:

```text
[ ] Detect Wort Cooling from Brew Tracker / Manual runtime text
[ ] Surface cooling stage in Stage Engine UI
[ ] Track BrewZilla temperature fall rate
[ ] Add optional counterflow output temperature source if available
[ ] Add estimated pitch-ready status
[ ] Add cooling efficiency indicator
[ ] Add transfer/pitch guidance once wort reaches target range
```

Safety note:

```text
Counterflow chilling requires manual sanitation and flow control verification.
BrewAssistant should guide and visualize before it controls anything.
```

---

# v4.7 Timed Fermentation Runtime

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

# v4.8 YAML retirement

Goal: remove backend logic from YAML packages and old helpers.

Rules:

```text
YAML may render.
Python should decide.
```

Completed:

```text
[x] Stop Manual Brewday services from syncing legacy helper mirrors
[x] Remove coordinator dependency on sensor.brew_process_status
[x] Remove YAML process attributes from Python process sensors
[x] Remove yaml_process_status from coordinator data model
[x] Allow old YAML stage sensor to be renamed locally while Python takes canonical stage entity
```

Remaining:

```text
[ ] Identify calculation-only template sensors still in local HA config
[ ] Rebuild required logic in Python
[ ] Replace dashboard dependencies with Python entities
[ ] Remove duplicated Jinja logic
[ ] Reduce helper dependency where practical
[ ] Remove compatibility layers after validation
[ ] Leave dashboard layout/cards intact where useful
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

# Next session checklist

```text
[ ] Patch BrewZilla runtime top-card power button color: red when switch.brewzilla is on
[ ] Keep lock condition based on actual power draw, not stored Heat/Pump percentages
[ ] Add Apply Target Now button/card gated by safety switches and control_hint
[ ] Validate Stage Engine v2 values during a real or simulated brewday
[ ] Start counterflow wort cooling UI/metrics design
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
