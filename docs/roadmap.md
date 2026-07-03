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
Safe Advice Beta / beta.7
↓
BrewZilla mash-in confirmation and circulation validation
↓
First full serious all-grain BrewZilla batch validation
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
[x] BrewZilla mash-in heat strategy: ramp far, approach, mash-in ready and overshoot
[x] BrewZilla mash-in confirmation gate pending binary sensor
[x] BrewZilla Mash-In Complete button entity
[x] BrewZilla Start Mash Circulation button entity
[x] BrewZilla Mash-In Complete action starts circulation using pump utilization plus pump switch
[x] BrewZilla Learning uses normalized runtime for Brewfather and Manual Brewday
[x] BrewZilla ABORT service
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

---

## Current beta.7 validation focus

```text
[ ] Confirm button.brewassistant_brewzilla_mash_in_complete exists after HA restart
[ ] Confirm button.brewassistant_brewzilla_start_mash_circulation exists after HA restart
[ ] Confirm binary_sensor.brewassistant_brewzilla_mash_in_gate_pending turns on at mash-in target
[ ] Confirm Mash-In Complete logs mash_in_confirmed
[ ] Confirm Mash-In Complete sets pump utilization before pump ON
[ ] Confirm fallback Start Mash Circulation button sets pump utilization before pump ON
[ ] Confirm Brewfather pause/resume order does not bypass BrewAssistant mash-in state
[ ] Confirm Brewday Event Log captures mash-in confirmation and circulation actions
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

Remaining:

```text
[ ] Validate Manual Brewday service flow in a real BrewZilla brewday
[ ] Add Manual timed-step auto-advance
[ ] Add Manual timed-step awaiting-confirm behavior at 0 seconds
[ ] Add Manual session persistence across Home Assistant restart
```

---

## Later cleanup backlog

```text
[ ] Consolidate temporary fix branches into main/dev workflow
[ ] Remove or archive historical beta5/baseline docs once beta.7 is validated
[ ] Keep backend action paths single-purpose: button entities for operator actions, no parallel workaround services
[ ] Continue Python module cleanup to avoid fragmented implementation files
[ ] Retire legacy YAML package logic after Python coverage is complete
```
