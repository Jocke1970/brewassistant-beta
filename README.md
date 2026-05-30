# BrewAssistant v4

**BrewAssistant v4** is a modular Home Assistant brewing assistant for Brewday runtime intelligence, BrewZilla/RAPT hardware control/visualization, counterflow wort cooling, carbonation guidance, dynamic serving/climate supervision, fermentation tracking, dashboards and notifications.

The project is moving away from YAML-heavy Home Assistant packages toward a Python custom integration where business logic, runtime normalization, stage interpretation, calculations and hardware orchestration live in `custom_components/brewassistant/`.

```text
Python custom integration = logic, normalization, stage engine, calculations, control decisions
YAML/dashboard             = presentation and explicit operator actions
```

---

## Current status

```text
v1.4 Python Core
Brewday/BrewZilla MVP validated in supervised dry-run with audit logging
```

Validated in the active `feature/python-core-v0.1` branch:

```text
✅ Brewfather RAW Brew Tracker runtime resolver
✅ Human-friendly Brew Tracker step labels
✅ Paused Brewfather freeze-state handling
✅ BrewZilla runtime sensors
✅ BrewZilla target sync from runtime core
✅ BrewZilla heater/pump direct actions
✅ ABORT service for heater + pump
✅ Brewday audit backend, services, sensors and dashboard
✅ Smart Brewfather refresh policy
✅ Low-temperature BrewZilla water test: 30 → 35 → 40 → 45 → 50 → 55°C
✅ Dry-run mash profile target validation: 45 → 55 → 65 → 72 → 78°C
✅ BrewZilla Cockpit v3.4 collapsed dashboard example
✅ Brewday Card v3.5 RAW/runtime dashboard example
✅ Brewday Audit Card v1.1 dashboard example
✅ Brewfather RAW Timeline debug card
✅ Climate Supervisor backend and UI
✅ Carbonation Runtime backend, persistence and UI
✅ Counterflow Wort Cooling backend and UI
✅ Fermentation Cockpit scope guard and UI polish
```

Still pending validation:

```text
[ ] normal ingredient mash profile
[ ] boil-stage behavior
[ ] hop addition/event notifications
[ ] real counterflow chilling data
[ ] active fermentation and cold-crash validation
[ ] full carbonation/serving cooling-cycle validation
```

---

## Architecture layers

| Layer | Purpose |
| --- | --- |
| Python Core | Normalize source entities and expose dashboard-safe state. |
| Brewday Runtime | Resolve Brewfather RAW Brew Tracker and Manual Brewday sessions. |
| Stage Engine | Interpret runtime state plus BrewZilla telemetry into current brewday stage. |
| BrewZilla Orchestration | Apply target/heater/pump actions when allowed by runtime state. |
| Brewday Audit | Persist event snapshots for post-run analysis of runtime and BrewZilla actions. |
| Climate Supervisor | Calculate and apply dynamic kegerator/serving air targets through climate control. |
| Cooling Runtime | Track counterflow wort cooling status, pump requirement, heater guard, ETA and pitch readiness. |
| Carbonation Runtime | Track carbonation session state, inputs, calculations and serving guidance. |
| Fermentation Scope Guard | Keep fermentation warnings scoped to active fermentation/cold-crash context. |
| Dashboard | Visualize state and trigger explicit operator actions. |

---

## Brewday / BrewZilla direct flow

Current verified MVP flow:

```text
Brewfather RAW Brew Tracker
        ↓
BrewAssistant RAW runtime resolver
        ↓
BrewAssistant brewday runtime sensors
        ↓
BrewZilla orchestration helper
        ↓
BrewZilla target / heater / pump actions
        ↓
Brewday audit log
```

BrewAssistant does **not** trust `sensor.brewfather_brew_tracker_step` as the authoritative source for active Brewday control, because it may lag behind Brewfather's web UI.

Instead, BrewAssistant resolves the active step from:

```text
sensor.brewfather_brew_tracker_raw.attributes.data.stages
stage.remainingSeconds
step.time anchors
```

Useful runtime attributes:

```text
raw_step_index
resolved_step_index
raw_step_name
snapshot_age_seconds
timeline
```

Brewfather may create multiple internal tracker steps with the same recipe name. BrewAssistant exposes human-friendly labels such as:

```text
Ramp to 55°C
Hold 55°C · 2 min
```

instead of displaying duplicated raw Brewfather names in the operator UI.

Detailed documentation:

```text
docs/brewday-brewzilla.md
docs/brewday-audit.md
docs/brewfather.md
docs/brewzilla-dashboard.md
```

---

## Brewday runtime entities

Recommended dashboard entities:

```text
sensor.brewassistant_brewday_runtime_source
sensor.brewassistant_brewday_runtime_state
sensor.brewassistant_brewday_runtime_stage
sensor.brewassistant_brewday_runtime_step
sensor.brewassistant_brewday_runtime_next_step
sensor.brewassistant_brewday_runtime_summary
sensor.brewassistant_brewday_target_temperature
sensor.brewassistant_brewday_live_time_remaining_minutes
sensor.brewassistant_brewday_live_progress
sensor.brewassistant_brewday_snapshot_age_minutes
sensor.brewassistant_brewday_awaiting_snapshot
sensor.brewassistant_brewday_refresh_recommended
```

---

## Brewday audit entities and services

Audit sensors:

```text
sensor.brewassistant_brewday_audit_summary
sensor.brewassistant_brewday_audit_event_count
sensor.brewassistant_brewday_audit_last_event
sensor.brewassistant_brewday_audit_last_step
sensor.brewassistant_brewday_audit_last_target
```

Audit services:

```text
brewassistant.brewday_audit_start
brewassistant.brewday_audit_stop
brewassistant.brewday_audit_clear
brewassistant.brewday_audit_snapshot
```

The audit log is persisted in Home Assistant storage:

```text
.storage/brewassistant_brewday_audit_log
```

---

## BrewZilla entities and services

BrewZilla runtime/control entities:

```text
sensor.brewassistant_brewzilla_runtime_state
sensor.brewassistant_brewzilla_runtime_summary
sensor.brewassistant_brewzilla_current_temperature
sensor.brewassistant_brewzilla_target_temperature
sensor.brewassistant_brewzilla_requested_target
sensor.brewassistant_brewzilla_applied_target
sensor.brewassistant_brewzilla_target_delta
sensor.brewassistant_brewzilla_target_sync_needed
sensor.brewassistant_brewzilla_can_apply_target
sensor.brewassistant_brewzilla_orchestration_mode
sensor.brewassistant_brewzilla_control_reason
sensor.brewassistant_brewzilla_safety_state
```

Current BrewZilla hardware profile entities:

```text
switch.brewzilla
sensor.brewzilla_power
sensor.brewzilla_connection
sensor.brewzilla_temperature
number.brewzilla_target_temperature
switch.brewzilla_heater
switch.brewzilla_pump
number.brewzilla_heat_utilization
number.brewzilla_pump_utilization
```

Services:

```text
brewassistant.force_brewfather_refresh
brewassistant.apply_brewzilla_target
brewassistant.abort_brewzilla
```

`brewassistant.abort_brewzilla` turns off:

```text
switch.brewzilla_heater
switch.brewzilla_pump
```

---

## Dashboard examples

Dashboard snippets are stored in:

```text
dashboards/
```

Current BrewZilla/Brewday examples:

```text
dashboards/brewzilla_cockpit_v3_4_collapsed.yaml
dashboards/brewday_card_v3_5_raw_runtime_polish.yaml
dashboards/brewday_audit_card_v1_1.yaml
dashboards/brewfather_raw_timeline_v2.yaml
```

Dashboard rule:

```text
Python decides.
Dashboard displays.
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
brewday_refresh_policy.py
brewday_audit.py
brewday_audit_sensor.py
brewzilla_sensor.py
brewzilla_orchestration.py
brewzilla_orchestration_sensor.py
climate_supervisor.py
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

## Other active modules

### Climate Supervisor

Climate Supervisor is the active path for carbonation/serving kegerator target management. It applies dynamic target adjustments to `climate.kegerator_kylskap`, which remains the compressor owner.

### Carbonation Runtime

Carbonation has a Python-owned runtime/session with persistence, start/update/pause/reset services, pressure/target/start controls and Cockpit UI.

### Counterflow Wort Cooling

Counterflow cooling has backend sensors, pitch-ready detection, pump/heater guidance and UI.
