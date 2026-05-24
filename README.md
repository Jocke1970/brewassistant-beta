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
| Carbonation Runtime | Provide carbonation calculations and serving guidance. |
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
✅ Brewday Runtime Core now resolves Brewfather Brew Tracker or None only
✅ Manual Brewday Adapter no longer reads old helper mirrors
✅ Python process mirror no longer reads sensor.brew_process_status
✅ YAML process attributes were removed from Python process sensors
✅ Legacy yaml_process_status field was removed from the coordinator data model
✅ Stage Engine is Python-owned and exposed through canonical BrewAssistant sensors
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

Stage Engine v2 exposes:

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

Important current behavior:

```text
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
✅ Brewday Actions UI with stage shortcut buttons
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

Counterflow wort cooling is now modeled as a dedicated post-boil cockpit.

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

Key cooling behavior:

```text
Stage is not cooling/pitch
→ status: standby
→ cooling_guard: standby

Heater ON during cooling
→ status: heater_off_required
→ cooling_guard: heater_off_required

Pump OFF and wort above target
→ status: pump_on_required
→ cooling_guard: pump_on_required

Pump ON and wort above target
→ status: cooling_needed or cooling

Within pitch tolerance
→ status: pitch_ready
```

---

## Carbonation Cockpit

Carbonation calculations and sensors still exist and the clean dashboard now has a dedicated read-only Carbonation Cockpit card.

Current status:

```text
✅ Carbonation calculation module exists
✅ Carbonation sensors are registered
✅ Carbonation Cockpit UI restored in clean dashboard
⚠️ Carbonation backend is still legacy-helper backed
🔜 Python-owned Carbonation Runtime/session services
```

Current known limitation: carbonation process state still reads local helper-style entities in `carbonation.py`. That is planned as the next backend cleanup after the current brewday/cooling validation pass.

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
switch.py
```

---

## Current status

BrewAssistant v4 is actively evolving.

Current Python Core status:

```text
v1.3 Python Core · Manual Runtime shortcuts + Stage Engine v2 + Counterflow Cooling Cockpit
```

Current near-term focus:

```text
✅ Python-only cleanup of legacy Manual Brewday helper dependencies
✅ Stage Engine v2 backend
✅ Stage Engine v2 UI
✅ BrewZilla runtime card with Stage Engine intelligence
✅ Counterflow wort cooling backend and UI
✅ Brewday Actions stage shortcut UI
✅ Carbonation Cockpit UI restored
🔜 Fermentation Cockpit scope guard
🔜 Python-owned Carbonation Runtime/session backend
🔜 Manual timed-step auto-advance
🔜 Manual session persistence across HA restart
🔜 Timed Fermentation Runtime
```

---

## Disclaimer

This project is intended for hobby brewing automation and process tracking. Always verify sanitation, pressure limits, electrical safety, hot-side safety, electrical switching, CO2 pressure, and fermentation decisions manually when needed.
