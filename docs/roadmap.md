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
BrewZilla heatstrike and mash-in confirmation validation
↓
BrewZilla mash-ramp and short boil-chain validation
↓
First full serious all-grain BrewZilla batch validation
↓
BrewZilla Equipment Learning BF timing/profile advisor
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
[x] BrewZilla Equipment Learning passive persistent evidence model
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

Planned near-term Python Core additions:

```text
[ ] BrewZilla BF timing/profile advisor based on planned-vs-actual segment data
[ ] BrewZilla learning segment detector: heatstrike, mash-in drop, mash ramp, mash-out, boil ramp, boil
[ ] BrewZilla learning report export: optional JSON/Markdown per supervised batch
[ ] Dashboard card section for BF timing suggestions and confidence
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
[ ] Confirm heatstrike holds the real strike target without boosted-target overshoot
[ ] Confirm heatstrike uses mash/BLE as readiness gate and wort/internal as overshoot safety cap
[ ] Confirm 66 -> 72°C ramp behavior with 9 min planned ramp time
[ ] Confirm 10 min boil-chain test once mash/ramp behavior is stable
[ ] Confirm equipment-learning observations and profile buckets are populated during supervised tests
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

Remaining:

```text
[ ] Validate Manual Brewday service flow in a real BrewZilla brewday
[ ] Add Manual timed-step auto-advance
[ ] Add Manual timed-step awaiting-confirm behavior at 0 seconds
[ ] Add Manual session persistence across Home Assistant restart
```

---

## Deferred: UI localization and translations

Full UI localization is intentionally deferred until BrewAssistant is a functionally complete and stable Home Assistant integration. Translation work must not delay BrewZilla, Brewday Runtime, fermentation, cooling, carbonation or installation validation.

### Architecture rules during ongoing development

```text
Backend code, entity IDs, unique IDs, attribute keys and internal states remain stable English.
Backend logic must never compare translated or user-facing text.
User-facing entity names, state labels, controls, actions and descriptions become translatable later.
Dashboard-specific hard-coded text remains a separate presentation-layer concern.
```

Each functional backend owns a dedicated translation-key namespace:

```text
core / shared          -> core_*, source_*, runtime_*
brewday/               -> brewday_*
brewzilla/             -> brewzilla_*
fermentation/          -> fermentation_*
kegerator/             -> kegerator_*
cooling/               -> cooling_*, counterflow_chiller_*
carbonation_backend/   -> carbonation_*
climate_backend/       -> climate_supervisor_*
```

Home Assistant still receives one complete translation file per language:

```text
custom_components/brewassistant/translations/en.json
custom_components/brewassistant/translations/sv.json
```

Separate per-backend source fragments may be introduced later and merged into the complete Home Assistant language files by a validation/build script.

Planned localization work:

```text
[ ] Inventory all user-facing text in Python entities, services/actions and config/options flows
[ ] Add stable translation_key values for sensors, binary sensors, switches, buttons, selects and numbers
[ ] Keep entity IDs, unique IDs and backend state values unchanged during UI-name migration
[ ] Normalize translatable select/state values to stable English snake_case machine values where needed
[ ] Add compatibility handling for previously restored English display-value states
[ ] Update and language-review complete English and Swedish translation files
[ ] Translate service/action names, descriptions and field labels
[ ] Add automated parity checks so en.json and sv.json contain matching keys
[ ] Add validation that new operator-facing entities do not introduce unnecessary hard-coded display names
[ ] Review dashboards separately and remove hard-coded names where the translated entity name should be used
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