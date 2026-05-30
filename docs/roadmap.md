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
Brewday/BrewZilla MVP validation
↓
Climate Supervisor full-cycle validation
↓
Carbonation runtime validation
↓
Counterflow wort cooling validation
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
[x] Manual Brewday Python engine
[x] Manual Brewday source adapter
[x] Manual Brewday services
[x] Manual Brewday restart after completed state
[x] Brewday Stage Engine v2
[x] Brewday Stage Engine explicit Prepare stage
[x] BrewZilla runtime sensors
[x] BrewZilla target sync
[x] BrewZilla heater/pump direct action helper
[x] BrewZilla ABORT service
[x] BrewZilla Cockpit v3.1 dashboard example
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
[x] Map pump utilization source
[x] Map connected/availability source
[x] Expose normalized BrewAssistant BrewZilla sensors
[x] Add orchestration mode and reason sensors
[x] Add apply-target/direct-action service
[x] Separate target_sync_needed from heater_action_needed and pump_action_needed
[x] Add ABORT service for heater + pump
[x] Integrate Stage Engine data into BrewZilla UI
[x] Add BrewZilla Cockpit v3.1 dashboard example
[x] Add RAW Timeline debug card
[x] Low-temperature water test verified 30 → 35 → 40 → 45 → 50 → 55°C
[x] Store dashboard examples in repo under dashboards/
```

Current acceptance status:

```text
MVP ready for controlled real-world testing
```

Remaining validation:

```text
[ ] Validate against normal-temperature real mash profile
[ ] Validate Brewfather pauseBefore/event behavior in a normal recipe
[ ] Validate boil-stage behavior
[ ] Validate hop addition/event notification behavior
[ ] Validate stale/disconnected RAPT/BrewZilla diagnostics during real use
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
[x] Python-owned carbonation runtime/session in hass.data
[x] Carbonation runtime persisted through HA storage
[x] Carbonation started_at / age_days survive Home Assistant restart
[x] Carbonation start/update/pause/reset services
[x] Carbonation pressure/target/start number controls
[x] Carbonation method select control
[x] Cooler/kegerator temperature source defaults to sensor.kyl_temperatur_4
[x] Legacy helper pressure is no longer used as backend fallback
[x] Carbonation Cockpit v3.1 UI with inputs, controls, estimated/equilibrium/recommended values
[x] Validate started_at = 2026-05-24T08:20:00+00:00 and age_days/progress after restart
```

Remaining:

```text
[ ] Validate estimated volumes over time during real set-and-forget carbonation
[ ] Decide whether progress_percent should remain level-percent or split into level/process progress
[ ] Add optional pressure/temp source mapping in config flow/options
[ ] Add smarter start_volumes estimate from max fermentation temperature or spunding pressure
```

---

# v4.9 Climate Supervisor / Kegerator control

Completed:

```text
[x] Identify direct switch control as wrong abstraction for kegerator compressor
[x] Deprecate Kegerator Guard as active control path
[x] Add Climate Supervisor backend
[x] Add Climate Supervisor enable switch
[x] Climate Supervisor applies dynamic target to climate.kegerator_kylskap
[x] Coordinator update loop applies Climate Supervisor reliably
[x] Validate cooling case: air above target → effective target 3.6 °C → climate target applied
[x] Validate relax case: air below target → effective target 4.4 °C → thermostat releases compressor
[x] Add Climate Supervisor UI card v1.0
[x] Add docs/climate-supervisor.md
```

Current operating rule:

```text
switch.brewassistant_kegerator_guard_enabled = off
switch.brewassistant_climate_supervisor_enabled = on when carbonation/serving target supervision is desired
climate.kegerator_kylskap = cool
climate.kegerator_kylskap owns switch.kegerator
```

Remaining:

```text
[ ] Continue one full carbonation/serving cooling-cycle validation
[ ] Tune dynamic target offsets if needed
[ ] Consider config/options for base target and min/max effective target
[ ] Remove or fully hide deprecated Kegerator Guard after further validation
[ ] Extend supervisor concept to fermentation/cold-crash liquid-aware air target later
```

---

# v4.10 YAML retirement

Rules:

```text
YAML may render.
Python should decide.
```

Completed:

```text
[x] Stop Manual Brewday services from syncing legacy helper mirrors
[x] Remove old manual selection from Brewday Runtime Core
[x] Remove coordinator dependency on sensor.brew_process_status
[x] Remove YAML process attributes from Python process sensors
[x] Remove yaml_process_status from coordinator data model
[x] Allow old YAML stage sensor to be renamed locally while Python takes canonical stage entity
[x] Remove carbonation pressure helper as backend dependency
[x] Scope stale cold-crash helper so it cannot keep Fermentation Cockpit in warning state alone
[x] Move kegerator dynamic target logic into Python Climate Supervisor instead of local dashboard/automation YAML
[x] Store BrewZilla/Brewfather dashboard snippets as examples, not backend logic
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

# v4.11 Runtime adapter architecture

Adapter priorities:

```text
[x] Brewfather Brew Tracker source adapter
[x] Brewfather RAW timeline resolver
[x] Manual Brewday source adapter
[x] BrewZilla hardware skeleton
[x] Counterflow wort cooling runtime helper
[x] Python-owned Carbonation Runtime adapter
[x] Climate Supervisor adapter for kegerator/carbonation serving target
[ ] Timed Fermentation Runtime adapter
[ ] BrewZilla hardware capability adapter
[ ] RAPT-specific hardware/profile adapter
[ ] Future local/MQTT hardware adapter
```

---

# Next session checklist

```text
[ ] Pull latest feature/python-core-v0.1 into Home Assistant
[ ] Restart/reload BrewAssistant integration
[ ] Verify dashboards/brewzilla_cockpit_v3_1.yaml in HA
[ ] Verify dashboards/brewfather_raw_timeline_v2.yaml in HA
[ ] Run short BrewZilla/Brewfather regression test if desired
[ ] Continue Climate Supervisor full-cycle validation
[ ] Continue Carbonation Runtime validation
```
