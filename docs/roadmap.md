# Roadmap

This document outlines the BrewAssistant beta roadmap.

BrewAssistant is moving from YAML package logic toward a Python custom integration where runtime state, stage interpretation, calculations and hardware decisions live in `custom_components/brewassistant/`.

```text
Python integration as source of truth
YAML/dashboard as presentation and explicit operator-action layer only
```

---

## Current project status

### Current phase

```text
BrewZilla hot-side supervised-control baseline / beta.8
↓
First supervised real-mash BrewZilla validation
↓
BrewZilla Equipment Learning BF timing/profile advisor evidence pass
↓
Boil / hop / cooling validation
↓
CFC Chill / Transfer Assistant validation
↓
RAPT Cloud Link profile-orchestration investigation
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

### Current branch policy

```text
main = installable/stable beta baseline
dev  = active development and test integration work
feature/fix branches = short-lived only; delete after merge or close
```

Old fix/test branches should not become permanent project structure.

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
[x] Brewday Event Log backend
[x] Brewday Event Log services
[x] Brewday Event Log sensors
[x] Brewday Event Log dashboard example
[x] Brewday Event Log uses normalized runtime for Brewfather and Manual Brewday
[x] Runtime-based Brewday Event Log autostart
[x] Manual Brewday Python engine
[x] Manual Brewday source adapter
[x] Manual Brewday services
[x] Manual Brewday restart after completed state
[x] Brewday Stage Engine v2
[x] Brewday Stage Engine explicit Prepare stage
[x] BrewZilla runtime sensors
[x] BrewZilla target sync from normalized runtime
[x] BrewZilla heater/pump direct action helper
[x] BrewZilla heat/pump utilization direct action helper
[x] BrewZilla clean heatstrike model: Mash/BLE readiness gate and wort/internal safety cap
[x] BrewZilla heatstrike target clamp to real strike target
[x] BrewZilla heatstrike pump mixing/equalization
[x] BrewZilla Mash-In Started target release to active Brewfather mash target
[x] BrewZilla Mash-In Started pump stop during malt addition/stirring
[x] Brewfather resume auto-completes Mash-In Complete and resumes circulation
[x] BrewZilla one-way mash-in state machine
[x] BrewZilla mash-in confirmation gate pending binary sensor
[x] BrewZilla Mash-In Complete button entity
[x] BrewZilla Start Mash Circulation button entity
[x] BrewZilla Learning uses normalized runtime for Brewfather and Manual Brewday
[x] BrewZilla Equipment Learning passive persistent evidence model
[x] BrewZilla active hot-side RCL recovery policy
[x] BrewZilla RCL reload suppression while live temp/power telemetry is fresh
[x] BrewZilla legacy RCL value-stale guard update-only
[x] BrewZilla ABORT service
[x] BrewZilla ABORT final low-level positive-action lockout
[x] BrewZilla operator dashboard card
[x] BrewZilla mash-in confirmation dashboard card
[x] BrewZilla Learning dashboard card
[x] Brewday Runtime dashboard card
[x] Manual Brewday dashboard card
[x] Source Health dashboard card
[x] Brewfather Feed dashboard card
[x] BrewTracker Runtime card includes batch status
[x] Counterflow Wort Cooling backend
[x] Counterflow Wort Cooling cockpit UI
[x] Python-owned Carbonation Runtime/session
[x] Carbonation runtime persistence across HA restart
[x] Carbonation services and controls
[x] Carbonation Cockpit UI
[x] Climate Supervisor backend for dynamic kegerator targets
[x] Climate Supervisor UI card
[x] Kegerator fan mode controls: Off / Always on / Afterrun
[x] Kegerator fan auto tick async-safety cleanup
[x] Kegerator guard watchdog async-safety cleanup
[x] Clean Home Assistant entity baseline without `bryggeriet_` BrewAssistant prefix
[x] Integration brand assets under custom component brand directory
[x] Fermentation Cockpit scope guard
[x] Fermentation Cockpit UI
```

Planned near-term Python Core additions:

```text
[ ] BrewZilla real-mash validation report from beta.8 run
[ ] BrewZilla BF timing/profile advisor based on planned-vs-actual segment data
[ ] BrewZilla learning segment detector: heatstrike, mash-in drop, mash ramp, mash-out, boil ramp, boil
[ ] BrewZilla learning report export: optional JSON/Markdown per supervised batch
[ ] Dashboard card section for BF timing suggestions and confidence
```

---

## Current beta.8 validation focus

```text
[ ] Confirm value-stale RCL guard logs update_entity only and reload suppressed from that guard
[ ] Confirm live BrewZilla temperature/power telemetry suppresses active RCL reload
[ ] Confirm Event Log autostarts from active Brewfather/Brewday Runtime
[ ] Confirm clean_heat_strike_active is true during pre-mash-in heatstrike
[ ] Confirm heatstrike uses mash/BLE as readiness gate and wort/internal as overshoot safety cap
[ ] Confirm heatstrike holds the real strike target without boosted-target overshoot
[ ] Confirm Mash-In Started releases target to active Brewfather mash target
[ ] Confirm Mash-In Started stops pump for malt addition/stirring
[ ] Confirm Brewfather resume auto-completes mash-in and starts circulation
[ ] Confirm mash-in state remains mash_in_complete through later mash/ramp steps
[ ] Confirm ABORT produces heater off, pump off, heat utilization 0 and pump utilization 0
[ ] Confirm no delayed pump_on/heater_on/positive number actions after ABORT
[ ] Validate mash-in temperature drop with real grain
[ ] Validate 66°C hold behavior with real grain bed
[ ] Validate 66 -> 72°C ramp behavior with real mash inertia
[ ] Validate pump flow without stuck/channeled bed symptoms
[ ] Confirm equipment-learning Real mash observations and profile buckets are populated
```

---

## BrewZilla Equipment Learning / BF timing advisor

Current status:

```text
[x] Passive equipment-learning storage model
[x] Rolling segment/profile buckets by equipment/context/volume/grain/stage
[x] Existing sensors expose equipment-learning summary, observations, segments, profile key and suggestion
[ ] Planned-vs-actual timing segment detector
[ ] Brewfather timing suggestions for heatstrike, mash ramps, mash-out and boil ramp
[ ] Confidence model using observation count, context match and RCL/source quality
[ ] Optional JSON/Markdown batch learning report export
```

Design rules:

```text
- learning is evidence only
- suggestions are for operator review
- no silent Brewfather recipe/profile rewrites
- no live target/heat/pump changes from learning
- water-only evidence must not be treated as real-mash evidence
- environment context should be recorded when HA sensors are available
```

Initial advisor outputs:

```text
Heatstrike time suggestion
Mash ramp time suggestion, e.g. 66 -> 72°C
Mash-out ramp time suggestion
Boil-ramp time suggestion
Batch report summary with planned vs actual timings
```

---

## v4.3 Brewday Runtime Stabilization

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
