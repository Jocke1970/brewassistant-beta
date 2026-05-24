# BrewAssistant v4

**BrewAssistant v4** is a modular Home Assistant brewing assistant for fermentation tracking, Brewday runtime intelligence, BrewZilla/RAPT hardware visualization, counterflow wort cooling, carbonation guidance, dashboards, notifications, and future safe orchestration.

The project is moving away from YAML-heavy Home Assistant packages toward a Python custom integration where business logic, runtime normalization, stage interpretation, calculations and safety checks live in `custom_components/brewassistant/`.

---

## Project goals

BrewAssistant v4 aims to provide:

- A clean Home Assistant custom integration with optional dashboard cards.
- Brewing workflows that can be reasoned about from Python-owned state.
- A Swedish-friendly UI with English/core entity naming.
- Fermentation, cold crash, transfer, packaging, carbonation and serving workflow support.
- Optional integration with Brewfather, RAPT, BrewZilla and manual brewing workflows.
- Premium dashboard cards that visualize the current batch or brewday state.
- A migration path away from older `fwk_*`, `brew_process_*` and helper-driven workflow logic.
- A migration path away from heavy YAML/Jinja decision logic into Python.
- Explicit safety boundaries before any hardware control is allowed.

---

## Current v4 philosophy

BrewAssistant v4 separates the brewing system into clear layers:

| Layer | Purpose |
| --- | --- |
| Python Core | Normalize source entities and expose dashboard-safe state. |
| Runtime | Normalize Brewfather Brew Tracker, Manual Brewday and sensor data. |
| Stage Engine | Interpret planned/runtime state plus hardware telemetry into a current brewday stage. |
| Cooling Runtime | Track counterflow wort cooling status, pump requirement, heater guard, ETA and pitch readiness. |
| Carbonation Runtime | Track carbonation session state, inputs, calculations and serving guidance. |
| Fermentation Scope Guard | Keep fermentation warnings scoped to active fermentation/cold-crash context. |
| Orchestration Safety | Decide whether a user-requested hardware action is safe to apply. |
| Hardware Layer | Normalize BrewZilla/RAPT hardware state before any future control. |
| Notifications | Alert when attention is needed. |
| Dashboard | Visualize and trigger explicit user actions without owning business logic. |

The dashboard should display and control the system, but should not contain hidden workflow logic that belongs in the Python integration.

```text
Python custom integration = logic, normalization, stage engine, calculations, safety checks
YAML/dashboard = presentation only
```

---

## Python-only cut-over status

The active Python branch no longer treats YAML process helpers as the backend source of truth.

Recent cleanup:

```text
✅ Manual Brewday services no longer sync legacy input_boolean/input_select helpers
✅ Manual Brewday Runtime is Python-owned and selected before external sources when active
✅ Manual Brewday can restart cleanly after completed state
✅ Brewday Runtime Core now resolves Brewfather Brew Tracker or None only
✅ Manual Brewday Adapter no longer reads old helper mirrors
✅ Python process mirror no longer reads sensor.brew_process_status
✅ YAML process attributes were removed from Python process sensors
✅ Legacy yaml_process_status field was removed from the coordinator data model
✅ Stage Engine is Python-owned and exposed through canonical BrewAssistant sensors
✅ Stage Engine has an explicit Prepare stage before Strike Water
✅ Carbonation Runtime is Python-owned and no longer uses legacy helper pressure as fallback
✅ Fermentation Cockpit scope guard ignores stale cold-crash helper state when no batch/fermentation context is active
```

`services.yaml` remains intentionally because Home Assistant uses it as service metadata for the custom integration. It is not workflow/business logic.

---

## Brewday Runtime Engine

BrewAssistant contains a dedicated Brewday Runtime Engine for Brewfather Brew Tracker and Manual Brewday workflows.

Architecture:

```text
Brewfather Brew Tracker / Python Manual Brewday
        ↓
BrewAssistant Runtime Engine
        ↓
Normalized runtime sensors
        ↓
Stage Engine / Dashboard / Notifications / Orchestration Safety
```

The Brewfather integration is treated as a read-only recipe/timeline source. BrewAssistant handles normalization, live countdown logic, process visualization and future orchestration boundaries.

### Runtime features

```text
✅ Brewfather Brew Tracker support
✅ Manual Brewday mode
✅ Manual Brewday Python engine
✅ Manual Brewday persistent session in hass.data
✅ Manual Brewday services
✅ Manual Brewday stage shortcut services
✅ Manual Brewday restart after completed state
✅ Live countdown between Brewfather snapshots
✅ Current-step remaining timer
✅ Stage remaining timer
✅ Snapshot age tracking
✅ Runtime state normalization
✅ Timeline generation
✅ Current/next step resolver
✅ Awaiting snapshot state
✅ Refresh compensation hook
✅ Manual Brewfather refresh service with 15 minute cooldown
✅ Dashboard-safe normalized entities
```

### Runtime states

```text
idle
prepared
running
live
paused
awaiting_confirm
awaiting_snapshot
completed
```

### Manual Brewday services

Manual Brewday can be controlled through Python services:

```text
brewassistant.manual_brewday_prepare
brewassistant.manual_brewday_start
brewassistant.manual_brewday_pause
brewassistant.manual_brewday_next
brewassistant.manual_brewday_start_mash
brewassistant.manual_brewday_start_boil
brewassistant.manual_brewday_start_whirlpool
brewassistant.manual_brewday_start_cooling
brewassistant.manual_brewday_finish
brewassistant.manual_brewday_reset
```

These services operate on the Python Manual Brewday runtime session and replace older helper-script driven manual controls.

Current restart behavior:

```text
Finish → Start
= new run from Setup / Prepare equipment

Finish → Reset → Prepare/Start
= clean new Manual Brewday session
```

---

## Brewday Stage Engine v2

The Brewday Stage Engine interprets both planned runtime data and real BrewZilla telemetry.

Purpose:

```text
active Brewfather/Manual stage and step
+
actual BrewZilla state, temperature, target, power and pump context
↓
interpreted current brewday stage
```

Supported interpreted stages:

```text
Idle
Prepare
Strike Water
Heating Strike
Mash In
Mash
Mash Out
Heating To Boil
Boiling
Hop Addition
Whirlpool
Wort Cooling
Pitch Ready
Transfer
Cleaning
Completed
```

Important current behavior:

```text
✅ Stage Engine has explicit Prepare stage for prepared/setup/manual equipment checks.
✅ Prepare does not wake Strike Water early.
✅ Stage Engine recognizes wort cooling / counterflow chilling terms.
✅ Stage Engine recognizes Whirlpool / Hop Stand as post-boil, not cooling.
✅ next_step does not trigger the current stage anymore.
✅ Cooling cockpit wakes only when the current stage/group is cooling or pitch-related.
```

The Stage Engine is currently read-only. It does not control BrewZilla hardware.

---

## BrewZilla runtime and orchestration safety

BrewAssistant includes a BrewZilla runtime layer and guarded orchestration safety layer.

Current status:

```text
✅ BrewZilla runtime sensors
✅ BrewZilla connection/runtime/temperature/target/power normalization
✅ BrewZilla heat/pump utilization visualization
✅ BrewZilla orchestration mode sensor
✅ BrewZilla safety switches
✅ Apply BrewZilla target service
✅ Safety validation before target sync
✅ Premium BrewZilla dashboard cards
✅ Stage Engine data integrated into BrewZilla UI
✅ Mash target quick-select UI
✅ BrewZilla/Brewday top-section polish v2.2
✅ Brewday Actions / Runtime Controls UI v2.2
```

Safety switches:

```text
switch.brewassistant_brewzilla_orchestration_enabled
switch.brewassistant_brewzilla_apply_target_temp
switch.brewassistant_brewzilla_allow_heater_control
switch.brewassistant_brewzilla_allow_pump_control
switch.brewassistant_brewzilla_allow_boil_mode
switch.brewassistant_brewzilla_safe_mode
```

Apply target service:

```text
service: brewassistant.apply_brewzilla_target
```

Current safety boundary:

```text
Read and visualize first.
Explicit user action second.
Hardware automation only after separate design, validation and safety review.
```

---

## Counterflow Wort Cooling

Counterflow wort cooling is modeled as a dedicated post-boil cockpit.

Current status:

```text
✅ Wort cooling sensors
✅ Cooling standby until Stage Engine enters cooling/pitch stage
✅ Pump required when wort is above target and BrewZilla pump is off
✅ Heater must be off during wort cooling
✅ Cooling guard state
✅ Cooling rate and ETA when trend data exists
✅ Pitch-ready detection within tolerance
✅ Counterflow Cooling UI v3
```

---

## Carbonation Cockpit

Carbonation now has a Python-owned runtime/session plus dashboard controls.

Current status:

```text
✅ Python-owned carbonation runtime in hass.data
✅ Carbonation start/update/pause/reset services
✅ Carbonation method select entity
✅ Carbonation pressure/target/start number entities
✅ Cooler/kegerator temperature defaults to sensor.kyl_temperatur_4
✅ Legacy helper pressure is not used as backend fallback
✅ Carbonation Cockpit v3.1 UI with inputs, controls and estimated/equilibrium/recommended values
```

Current model:

```text
Target vol + current cooler temp
→ recommended pressure

Actual pressure + current cooler temp
→ equilibrium volumes

Start volumes + time toward equilibrium
→ estimated volumes
```

Open validation item:

```text
Decide whether progress_percent should represent carbonation level percent or be split into level/process progress.
```

---

## Fermentation Cockpit

Fermentation currently uses the normalized coordinator/process sensors and older smart recommendation sensors while a future Timed Fermentation Runtime matures.

Current status:

```text
✅ Fermentation Cockpit scope guard
✅ Stale cold-crash helper cannot keep cockpit in warning state by itself
✅ Idle/none process shows Standby + ok severity/problem
✅ Fermentation Cockpit v2.1 UI hides stale delta/SG from the alert view
✅ Smart recommendation card is hidden/neutral when fermentation is out of scope
```

Current behavior:

```text
No active fermentation/batch context
→ Process: Idle
→ Stage: none
→ Temp status: Standby
→ Severity: ok
→ Problem: ok
```

---

## Runtime internals

Core runtime modules include:

```text
brewday_runtime_core.py
brewday_runtime.py
brewday_runtime_sensor.py
brewday_stage_engine.py
brewday_stage_sensor.py
brewday_refresh.py
brewzilla_sensor.py
brewzilla_orchestration.py
brewzilla_orchestration_sensor.py
manual_brewday_runtime.py
manual_brewday_adapter.py
manual_brewday_store.py
wort_cooling.py
wort_cooling_sensor.py
carbonation.py
carbonation_runtime.py
number.py
select.py
switch.py
```

---

## Current status

BrewAssistant v4 is actively evolving.

Current Python Core status:

```text
v1.3 Python Core · Manual Runtime restart + Stage Engine Prepare + Counterflow Cooling + Carbonation Runtime + Fermentation Cockpit Scope Guard
```

Current near-term focus:

```text
✅ Python-only cleanup of legacy Manual Brewday helper dependencies
✅ Stage Engine v2 backend
✅ Stage Engine explicit Prepare stage
✅ Stage Engine v2 UI
✅ BrewZilla runtime card with Stage Engine intelligence
✅ Counterflow wort cooling backend and UI
✅ Brewday Actions / Runtime Controls v2.2
✅ Carbonation runtime backend and UI
✅ Fermentation Cockpit scope guard and UI polish
🔜 Validate Manual Brewday restart/Prepare flow after Home Assistant reload
🔜 Validate BrewZilla/Brewday top cards during real brewday
🔜 Manual timed-step auto-advance
🔜 Manual session persistence across HA restart
🔜 Timed Fermentation Runtime
```

---

## Acknowledgements

BrewAssistant's Brewfather-aware runtime builds on the Home Assistant Brewfather ecosystem and treats the upstream Brewfather integration as a read-only source of recipe, batch and Brew Tracker data.

Special thanks to **mvddonk**, creator/maintainer of the Brewfather Integration for Home Assistant, for the upstream integration that makes Brewfather data available inside Home Assistant.

BrewAssistant is a separate companion/orchestration project and is not affiliated with Brewfather.

---

## Disclaimer

This project is intended for hobby brewing automation and process tracking. Always verify sanitation, pressure limits, electrical safety, hot-side safety, electrical switching, CO2 pressure, and fermentation decisions manually when needed.
