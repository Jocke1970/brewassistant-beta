# Roadmap

This document outlines the BrewAssistant v4 roadmap.

BrewAssistant is moving from YAML package logic toward a Python custom integration where runtime state, stage interpretation, calculations and hardware decisions live in `custom_components/brewassistant/`.

```text
Python integration as source of truth
YAML/dashboard as presentation layer only
```

---

## Current project status

### Current phase

```text
Python Core stabilization
↓
Brewday/BrewZilla MVP validated with audit dry-run
↓
Boil / hop / cooling validation
↓
Climate Supervisor full-cycle validation
↓
Carbonation runtime validation
↓
Fermentation cockpit validation
↓
Timed Fermentation Runtime
↓
Full YAML retirement
```

### Working in Python Core

```text
[x] Custom integration skeleton
[x] Config flow
[x] Coordinator update loop
[x] Runtime normalization
[x] Dashboard support entities
[x] Brewfather RAW Brew Tracker runtime resolver
[x] Human-friendly Brew Tracker ramp/hold labels
[x] Smart Brewfather refresh policy
[x] Manual Brewfather refresh service
[x] Brewday Runtime Engine
[x] Brewday current-step timer resolver
[x] Brewday stage timer resolver
[x] Brewday timeline generation
[x] Brewfather paused freeze-state handling
[x] Brewday audit backend
[x] Brewday audit services
[x] Brewday audit sensors
[x] Brewday audit dashboard
[x] Manual Brewday Python engine
[x] Manual Brewday source adapter
[x] Manual Brewday services
[x] Manual Brewday restart after completed state
[x] Brewday Stage Engine v2
[x] Brewday Stage Engine explicit Prepare stage
[x] BrewZilla runtime sensors
[x] BrewZilla target sync from runtime core
[x] BrewZilla heater/pump direct action helper
[x] BrewZilla ABORT service
[x] BrewZilla Cockpit v3.4 dashboard example
[x] Brewday Card v3.5 RAW/runtime dashboard example
[x] Brewfather RAW Timeline debug card
[x] Counterflow Wort Cooling backend
[x] Counterflow Wort Cooling cockpit UI
[x] Python-owned Carbonation Runtime/session
[x] Carbonation runtime persistence across HA restart
[x] Carbonation services and controls
[x] Carbonation Cockpit v3.1 UI
[x] Climate Supervisor backend for dynamic kegerator targets
[x] Climate Supervisor UI card v1.0
[x] Fermentation Cockpit scope guard
[x] Fermentation Cockpit v2.1 UI
```

---

# v4.3 Brewday Runtime Stabilization

Completed:

```text
[x] Brewfather Brew Tracker source adapter
[x] Brewfather RAW timeline resolver
[x] Ignore lagging sensor.brewfather_brew_tracker_step as source of truth
[x] Resolve active step from raw stage.remainingSeconds and step.time anchors
[x] Human-friendly runtime labels: Ramp to X°C / Hold X°C · N min
[x] Paused Brewfather freeze-state handling
[x] Manual Brewday source adapter
[x] Runtime state normalization
[x] Current/next step resolver
[x] Timeline generation
[x] Snapshot age tracking
[x] Live countdown between Brewfather snapshots
[x] Separate current-step remaining from stage remaining
[x] Awaiting snapshot state
[x] Smart automatic refresh around step boundaries
[x] Manual Brewfather refresh service
[x] Manual Brewday Runtime engine
[x] Manual Brewday services
[x] Manual Brewday stage shortcut services
[x] Stop syncing Manual Brewday services to older YAML/input-helper mirrors
[x] Remove old manual source selection from Brewday Runtime Core
[x] Allow clean new run after completed state
[x] Validate Manual Brewday service flow across stages in UI
[x] Validate Prepare/Idle sanity after Home Assistant reload
[x] Validate Brewfather paused behavior during dry-run
```

Remaining:

```text
[ ] Validate Manual Brewday service flow in a real BrewZilla brewday
[ ] Add Manual timed-step auto-advance
[ ] Add Manual timed-step awaiting-confirm behavior at 0 seconds
[ ] Add Manual session persistence across Home Assistant restart
[ ] Add optional Manual plan import/building from Brewfather recipe data
[ ] Add optional Manual plan editing/profile selection
[ ] Add service documentation and dashboard examples
```

---

# v4.4 BrewZilla/RAPT hardware reality mapping

Current status:

```text
[x] BrewZilla read-only runtime skeleton
[x] BrewZilla runtime sensors
[x] Map current temperature source
[x] Map target temperature source
[x] Map power/heating source
[x] Map heat utilization source
[x] Map pump utilization source
[x] Map connected/availability source
[x] Expose normalized BrewAssistant BrewZilla sensors
[x] Add orchestration mode and reason sensors
[x] Add apply-target/direct-action service
[x] Separate target_sync_needed from heater_action_needed and pump_action_needed
[x] Add ABORT service for heater + pump
[x] Integrate Stage Engine data into BrewZilla UI
[x] Add BrewZilla Cockpit v3.4 dashboard example
[x] Add Brewday Card v3.5 dashboard example
[x] Add Brewday Audit Card v1.1 dashboard example
[x] Add RAW Timeline debug card
[x] Low-temperature water test verified 30 → 35 → 40 → 45 → 50 → 55°C
[x] Dry-run mash profile verified 45 → 55 → 65 → 72 → 78°C target flow
[x] Brewday audit log captured runtime and BrewZilla orchestration actions
[x] Store dashboard examples in repo under dashboards/
```

Current acceptance status:

```text
MVP validated for supervised Brewfather/BrewZilla dry-run mash testing
```

Remaining validation:

```text
[ ] Validate against normal ingredient mash profile
[ ] Validate boil-stage behavior
[ ] Validate hop addition/event notification behavior
[ ] Validate stale/disconnected RAPT/BrewZilla diagnostics during real use
[ ] Validate RAPT Cloud/Brewfather poll cadence during real ramping
[ ] Tune dashboard wording after first real brewday
```

---

# v4.5 Brewday Stage Engine

Completed:

```text
[x] Create brewday_stage_engine.py
[x] Create brewday_stage_sensor.py
[x] Wire Stage Engine sensors into Brewday runtime factory
[x] Interpret active runtime stage/step text
[x] Keep next_step from triggering current stage
[x] Add explicit Prepare stage before Strike Water
[x] Interpret BrewZilla temperature/target/delta/power/pump context
[x] Support Idle, Prepare, Strike Water, Heating Strike, Mash In, Mash, Mash Out
[x] Support Heating To Boil, Boiling and Hop Addition
[x] Support Whirlpool and Hop Stand
[x] Support Wort Cooling / counterflow cooling detection
[x] Support Pitch Ready, Transfer and Completed
[x] Recognize Cleaning as external housekeeping/wrap-up label only
[x] Expose stage reason/status/icon/progress/temperature/power sensors
[x] Add v2 fields: stage_group, stage_priority, suggested_action, control_hint
[x] Add Stage Engine v2 UI card
[x] Validate Idle sanity after reload
[x] Validate Manual Brewday stages and processes without unexpected behavior
```

Remaining:

```text
[ ] Validate stage transitions during real BrewZilla brewday
[ ] Tune thresholds for Heating Strike / Mash / Boil / Cooling
[ ] Add estimated time-to-target where possible
[ ] Add event/notification hooks for attention stages
```

---

# v4.6 Counterflow Wort Cooling

Completed:

```text
[x] Detect Wort Cooling from Brew Tracker / Manual runtime current stage or step
[x] Keep cooling in standby until Stage Engine enters cooling/pitch state
[x] Surface cooling stage in Stage Engine UI
[x] Track BrewZilla/kettle reference temperature
[x] Track temperature fall rate when trend data exists
[x] Add optional counterflow output temperature source if available
[x] Add estimated pitch-ready status
[x] Add ETA when cooling trend is available
[x] Require BrewZilla pump during counterflow cooling
[x] Guard against heater being on during cooling
[x] Add Counterflow Cooling Cockpit UI
```

Remaining:

```text
[ ] Validate cooling rate/ETA during real counterflow chilling
[ ] Tune pitch-ready tolerance if needed
[ ] Add cooling efficiency indicator
[ ] Add transfer/pitch notification hooks once wort reaches target range
[ ] Add optional dedicated output temperature sensor mapping in config flow/options
```

---

# v4.7 Fermentation cockpit/runtime cleanup

Completed:

```text
[x] Add Fermentation Cockpit scope guard
[x] Ignore stale cold-crash helper when no fermentation/batch context is active
[x] Show neutral standby/completed when no fermentation process is active
[x] Hide smart recommendations in the UI when fermentation is out of scope
[x] Add Fermentation Cockpit v2.1 UI polish
```

Remaining:

```text
[ ] Validate against an active fermentation batch
[ ] Validate against active cold crash
[ ] Later: build Python-owned Timed Fermentation Runtime
[ ] Later: replace legacy helper/process sources where practical
```

---

# v4.8 Carbonation runtime cleanup

Completed:

```text
[x] Carbonation calculation module exists
[x] Carbonation sensors are registered
[x] Carbonation runtime session is Python-owned
[x] Carbonation persistence across Home Assistant restart
[x] Carbonation service set: start/update/pause/reset
[x] Carbonation UI controls and recommended pressure display
```

Remaining:

```text
[ ] Validate carbonation estimates against a real keg session
[ ] Add optional history/trend tracking
[ ] Add notification hooks when estimated carbonation reaches target
```
