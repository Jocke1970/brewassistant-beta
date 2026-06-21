# Roadmap

This document outlines the BrewAssistant beta roadmap.

BrewAssistant is moving from YAML package logic toward a Python custom integration where runtime state, stage interpretation, calculations and hardware decisions live in `custom_components/brewassistant/`.

```text
Python integration as source of truth
YAML/dashboard as presentation layer only
```

---

## Current project status

### Current phase

```text
Clean Baseline Beta
↓
Home Assistant log validation after async watchdog cleanup
↓
First full serious all-grain BrewZilla batch validation
↓
Boil / hop / cooling validation
↓
CFC Chill / Transfer Assistant design
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
[x] BrewZilla Learning uses normalized runtime for Brewfather and Manual Brewday
[x] BrewZilla ABORT service
[x] BrewZilla operator dashboard card
[x] BrewZilla Learning dashboard card
[x] Brewday Runtime dashboard card
[x] Manual Brewday dashboard card
[x] Source Health dashboard card
[x] Brewfather Feed dashboard card
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
[x] Add direct heat utilization and pump utilization actions
[x] Add staged heating-to-mash-in orchestration strategy
[x] Add ABORT service for heater + pump
[x] Integrate Stage Engine data into BrewZilla UI
[x] Add BrewZilla operator dashboard card
[x] Add BrewZilla Learning dashboard card
[x] Add Brewday Runtime dashboard card
[x] Add Brewday Event Log dashboard card
[x] Low-temperature water test verified 30 → 35 → 40 → 45 → 50 → 55°C
[x] Dry-run mash profile verified 45 → 55 → 65 → 72 → 78°C target flow
[x] Brewday Event Log captured runtime and BrewZilla orchestration actions
[x] Store dashboard examples in repo under dashboard/
```

Current acceptance status:

```text
MVP validated for supervised Brewfather/BrewZilla dry-run mash testing
Mash-in heat strategy implemented and ready for water/first-batch validation
```

Remaining validation:

```text
[ ] Validate mash-in heat strategy in a water test to 66°C
[ ] Validate mash-hold strategy after Mash in / Saccharification rest
[ ] Validate against normal ingredient mash profile
[ ] Validate boil-stage behavior
[ ] Validate hop addition/event notification behavior
[ ] Validate stale/disconnected RAPT/BrewZilla diagnostics during real use
[ ] Validate RAPT Cloud/Brewfather poll cadence during real ramping
[ ] Tune dashboard wording after first real brewday
```

Future backend tracks:

```text
[ ] Investigate RAPT Cloud Link profile orchestration as an alternative BrewZilla control backend
[ ] Model BrewZilla profile execution as a separate control strategy from direct target/heater/pump actions
[ ] Decide how BrewAssistant should create/select/start RAPT/BrewZilla profiles safely
[ ] Add source arbitration between Brewfather runtime, Manual Brewday runtime and RAPT/BrewZilla profile execution
[ ] Keep operator confirmation/ABORT semantics for any RAPT Cloud Link profile-control path
```

---

# v4.4.1 CFC Chill / Transfer Assistant

Current status:

```text
[x] Counter Flow Chiller backend store
[x] CFC enabled switch
[x] CFC sanitize minutes number
[x] CFC pump utilization number
[x] CFC Ready button for hot-side sanitation/circulation
[x] CFC dashboard card baseline
```

Planned backend/UI work:

```text
[ ] Split CFC behavior into Sanitize / Chill / Transfer modes
[ ] Add configurable cold_water_pump switch entity separate from BrewZilla wort pump
[ ] Add CFC wort temperature source selector
[ ] Support RAPT BLE Thermometer as wort-out / pitch-temperature source
[ ] Add normalized CFC wort-out temperature sensor
[ ] Add pitch target temperature number/input
[ ] Add delta-to-pitch-target and pitch-ready status sensors
[ ] Add CFC chill guidance: adjust wort flow, cold-water flow or wait
[ ] Add CFC abort/stop behavior for cold water pump and BrewZilla pump according to mode
[ ] Keep sanitize flow separate from chill/transfer flow: cold water pump should normally be off during sanitize
[ ] Update CFC dashboard card after backend entities exist
```

Design notes:

```text
- BrewZilla pump moves wort.
- cold_water_pump moves cooling water.
- RAPT BLE Thermometer should preferably measure wort-out temperature near the fermenter.
- CFC Ready remains the sanitation/connected action.
- Chill / Transfer should become a supervised assistant, not unattended autopilot.
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
BrewAssistant skarp driftmodell

Processkälla:
Brewfather Brew Tracker / Manual Brew
→ BrewAssistant Runtime
→ BrewZilla Executor
→ BrewZilla/RCL

BA ska:
- övervaka och visualisera processen
- visa aktivt steg, nästa steg och runtime target tydligt
- ge advice när processen drar åt fel håll
- exekvera temperatur/target mot BrewZilla via runtime när policy tillåter
- aldrig låta BF/Manual prata direkt med BrewZilla
- blocka osäker action, men först försöka självläka där det är rimligt

Inlagt idag:
#32 RCL refresh before blocking
#33 BrewZilla temperature resolver guard
#34 Live Brewfather batch context priority
#35 Resolver diagnostics exposed

Verifierat:
- #32/#33/#34/#35 laddade efter restart
- Mash/Wort faller tillbaka till sensor.brewzilla_temperature när BLE/control telemetry inte är giltig extern mash-källa
- Batch-context diagnostics synliga
- RCL refresh diagnostics synliga
- Idle-läge safe: ingen refresh/block i idle

Nästa test:
- Starta test-BeerXML via Brewfather BrewTracker
- Bekräfta runtime target → requested_target
- Bekräfta stale RCL → refresh requested
- Bekräfta fresh RCL → target sync till BrewZilla
- Bekräfta Brewfather context → live_brewfather_first
- Bekräfta manual context endast används som fallback

Kvar:
- Advice UI måste bli mycket tydligare/mer omissbar
- RCL polling/refresh behöver valideras i aktiv runtime
- Fortsatt BZ supervised runtime-test med lågtempsteg
