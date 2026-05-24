# Roadmap

This document outlines the BrewAssistant v4 roadmap.

BrewAssistant is moving from YAML package logic toward a Python custom integration where runtime state, stage interpretation, calculations and safety checks live in `custom_components/brewassistant/`.

```text
Python integration as source of truth
YAML/dashboard as presentation layer only
```

---

## Current project status

### Working in Python Core

```text
[x] Custom integration skeleton
[x] Config flow
[x] Read-only coordinator
[x] Runtime normalization
[x] Source health engine
[x] Next recommended action engine
[x] Dashboard support entities
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
[x] Manual Brewday stage shortcut services
[x] BrewZilla runtime sensors
[x] BrewZilla orchestration safety switches
[x] BrewZilla Apply Target service
[x] Brewday Stage Engine v2 guidance fields
[x] Stage Engine v2 dashboard support sensors
[x] Counterflow Wort Cooling backend
[x] Counterflow Wort Cooling cockpit UI
[x] Python-owned Carbonation Runtime/session
[x] Carbonation start/update/pause/reset services
[x] Carbonation number/select controls
[x] Carbonation Cockpit v3.1 UI
[x] Fermentation Cockpit scope guard
[x] Fermentation Cockpit v2.1 UI
```

### Current phase

```text
Python Core stabilization
↓
Brewday Runtime validation
↓
Stage Engine validation
↓
BrewZilla/RAPT reality testing
↓
Counterflow wort cooling validation
↓
Carbonation runtime validation
↓
Fermentation cockpit validation
↓
Timed Fermentation Runtime
↓
Full YAML retirement
↓
Future guarded automation/control
```

---

# v4.3 Brewday Runtime Stabilization

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
[x] Manual Brewday stage shortcut services
[x] Manual Brewday Control / Brewday Actions UI
[x] Stop syncing Manual Brewday services to older YAML/input-helper mirrors
[x] Remove old manual source selection from Brewday Runtime Core
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
[x] Add Mash target quick-select UI
[x] Add Brewday Actions UI with stage shortcut buttons
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

Completed:

```text
[x] Create brewday_stage_engine.py
[x] Create brewday_stage_sensor.py
[x] Wire Stage Engine sensors into Brewday runtime factory
[x] Interpret active runtime stage/step text
[x] Keep next_step from triggering current stage
[x] Interpret BrewZilla temperature/target/delta/power/pump context
[x] Support Idle, Strike Water, Heating Strike, Mash In, Mash, Mash Out
[x] Support Heating To Boil, Boiling and Hop Addition
[x] Support Whirlpool and Hop Stand
[x] Support Wort Cooling / counterflow cooling detection
[x] Support Pitch Ready, Transfer and Completed
[x] Recognize Cleaning as external housekeeping/wrap-up label only
[x] Expose stage reason/status/icon/progress/temperature/power sensors
[x] Add v2 fields: stage_group, stage_priority, suggested_action, control_hint
[x] Add Stage Engine v2 UI card
```

Remaining:

```text
[ ] Validate stage transitions during real BrewZilla brewday
[ ] Tune thresholds for Heating Strike / Mash / Boil / Cooling
[ ] Add estimated time-to-target where possible
[ ] Add event/notification hooks for attention stages
[ ] Add explicit Apply Target UI gated by control_hint and safety switches
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
[x] Carbonation start/update/pause/reset services
[x] Carbonation pressure/target/start number controls
[x] Carbonation method select control
[x] Cooler/kegerator temperature source defaults to sensor.kyl_temperatur_4
[x] Legacy helper pressure is no longer used as backend fallback
[x] Carbonation Cockpit v3.1 UI with inputs, controls, estimated/equilibrium/recommended values
```

Remaining:

```text
[ ] Validate estimated volumes over time during real set-and-forget carbonation
[ ] Decide whether progress_percent should remain level-percent or split into level/process progress
[ ] Add optional pressure/temp source mapping in config flow/options
[ ] Add smarter start_volumes estimate from max fermentation temperature or spunding pressure
```

---

# v4.9 YAML retirement

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

# v4.10 Runtime adapter architecture

Adapter priorities:

```text
[x] Brewfather Brew Tracker source adapter
[x] Manual Brewday source adapter
[x] BrewZilla read-only hardware skeleton
[x] Counterflow wort cooling runtime helper
[x] Python-owned Carbonation Runtime adapter
[ ] Timed Fermentation Runtime adapter
[ ] BrewZilla hardware capability adapter
[ ] RAPT-specific hardware/profile adapter
[ ] Future local/MQTT hardware adapter
```

---

# Next session checklist

```text
[ ] Polish BrewZilla/Brewday top cards
[ ] Validate Fermentation Cockpit v2.1 standby/completed UI
[ ] Validate Carbonation Cockpit v3.1 with real carbonation inputs
[ ] Verify Whirlpool shortcut: Stage = Whirlpool and Cooling = standby
[ ] Verify Cooling shortcut: Stage = Wort Cooling and Cooling = pump_on_required when pump is off
[ ] Add Apply Target Now button/card gated by safety switches and control_hint
```

---

# Long-term direction

BrewAssistant is evolving from a Home Assistant YAML package collection into a modular brewing platform for Home Assistant.
