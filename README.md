# BrewAssistant v4

**BrewAssistant v4** is a modular Home Assistant brewing assistant for fermentation tracking, chamber control, manual batches, notifications, dashboards, and future hot-side/brew-day integrations.

The project is designed around a clean core with optional modules. It can be used for simple manual fermentation tracking, Brewfather-assisted recipe runtime data, RAPT/Pill readings, fermentation chamber automation, kegerator visualisation, and later BrewZilla/RAPT hot-side workflows.

---

## Project goals

BrewAssistant v4 aims to provide:

- A clean Home Assistant package and custom integration structure.
- Brewing workflows that survive Home Assistant restarts.
- A Swedish-friendly UI with English/core entity naming.
- Fermentation, cold crash, transfer, packaging, and storage workflow support.
- Optional integration with Brewfather, RAPT, BrewZilla and manual hydrometer readings.
- Premium dashboard cards that visualise the current batch state.
- A migration path away from older `fwk_*` helper/entity names.
- A migration path from heavy YAML/Jinja decision logic into Python.

---

## Current v4 philosophy

BrewAssistant v4 separates the brewing system into clear layers:

| Layer | Purpose |
| --- | --- |
| Python Core | Normalize source entities and expose dashboard-safe state. |
| Runtime | Normalize recipe, batch, Brewfather, Manual Brewday and sensor data. |
| Workflow | Decide current process state, next step and readiness. |
| Chamber | Apply and monitor fermentation chamber targets. |
| Manual Mode | Track batches and brew days without Brewfather/RAPT automation. |
| Hardware Layer | Normalize BrewZilla/RAPT hardware state before any future control. |
| Notifications | Alert when attention is needed. |
| Dashboard | Visualize and control the system without owning business logic. |

The dashboard should display and control the system, but should not contain hidden workflow logic that belongs in backend packages or the Python integration.

The long-term direction is:

```text
Python custom integration = logic, normalization, state machine, calculations
YAML packages/dashboard = UI, layout, manual presentation tweaks
```

---

## Brewday Runtime Engine

BrewAssistant contains a dedicated Brewday Runtime Engine for Brewfather Brew Tracker and Manual Brewday workflows.

Architecture:

```text
Brewfather Brew Tracker / Manual Brewday
        ↓
BrewAssistant Runtime Engine
        ↓
Normalized runtime sensors
        ↓
Timeline / Dashboard / Notifications
```

The Brewfather integration is intentionally treated as a generic read-only source.
All orchestration, normalization, live countdown logic and process visualization is handled by BrewAssistant.

### Runtime features

```text
✅ Brewfather Brew Tracker support
✅ Manual Brewday mode
✅ Manual Brewday Python engine
✅ Manual Brewday persistent session in hass.data
✅ Manual Brewday services
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

### Brewfather refresh compensation

Brewfather Brew Tracker snapshots are normally updated on a scheduled polling interval.

BrewAssistant compensates for this by:

```text
1. Running a local live countdown.
2. Separating current-step remaining time from full-stage remaining time.
3. Detecting when the active step reaches 0.
4. Triggering guarded update_entity refreshes.
5. Resolving the next Brewfather snapshot immediately when available.
```

This gives BrewAssistant near realtime Brewday transitions without modifying Brewfather itself.

Manual refresh is also exposed through:

```text
service: brewassistant.force_brewfather_refresh
```

The manual service uses a 15 minute cooldown to avoid excessive polling.

### Manual Brewday services

Manual Brewday can now be controlled through Python services:

```text
brewassistant.manual_brewday_prepare
brewassistant.manual_brewday_start
brewassistant.manual_brewday_pause
brewassistant.manual_brewday_next
brewassistant.manual_brewday_finish
brewassistant.manual_brewday_reset
```

These services operate on the persistent Manual Brewday runtime session and are intended to replace older helper-script driven manual controls.

### Brewday Runtime entities

Examples:

```text
sensor.brewassistant_brewday_runtime_source
sensor.brewassistant_brewday_runtime_state
sensor.brewassistant_brewday_runtime_status
sensor.brewassistant_brewday_runtime_stage
sensor.brewassistant_brewday_runtime_step
sensor.brewassistant_brewday_runtime_next_step
sensor.brewassistant_brewday_runtime_summary
sensor.brewassistant_brewday_live_progress
sensor.brewassistant_brewday_live_time_remaining_minutes
sensor.brewassistant_brewday_snapshot_age_minutes
sensor.brewassistant_brewday_awaiting_snapshot
sensor.brewassistant_brewday_refresh_recommended
```

The runtime summary attributes also expose timeline data and diagnostics such as:

```text
stage_remaining_seconds
stage_remaining_minutes
current_step_remaining_seconds
current_step_remaining_minutes
current_step_description
next_step_description
```

### Runtime internals

Core runtime modules:

```text
brewday_runtime_core.py
brewday_runtime.py
brewday_runtime_sensor.py
brewday_refresh.py
manual_brewday_runtime.py
manual_brewday_adapter.py
manual_brewday_store.py
```

---

## BrewZilla hardware skeleton

BrewAssistant includes an early BrewZilla runtime skeleton.

Current intent:

```text
✅ read-only hardware normalization
✅ connected/power/temp/target abstractions
✅ safe UI/debug foundation
❌ no automatic hardware control yet
```

Next phase is reality testing against RAPT/HA-exposed BrewZilla entities and patching the mapping layer accordingly.

---

## Python Core v1.1

`custom_components/brewassistant/` contains the BrewAssistant Home Assistant custom integration.

Current milestone:

```text
BrewAssistant Python Core v1.1 · Runtime Engine + Read-only Core
```

Current scope:

- Read existing Home Assistant entities.
- Normalize liquid temperature, chamber fallback temperature, effective target temperature and gravity.
- Use cold crash target when cold crash is active.
- Mirror process state and next process step from existing workflow/YAML signals.
- Expose smart fermentation recommendations without controlling hardware.
- Detect Pill stale/fresh status.
- Expose source health diagnostics for configured entities.
- Normalize Brewfather/runtime recipe name, status, targets and target FG.
- Expose one compact next recommended action sensor for dashboards and notifications.
- Normalize Brewday Runtime state, Brewfather Brew Tracker state and Manual Brewday state.
- Run beside the existing YAML packages without controlling hardware.

Safety boundary:

```text
Python Core v1.1 is mostly read-only.
Manual Brewday services only update BrewAssistant's own runtime session and legacy helper mirrors.
No climate, switch, fan, heater, fridge, relay, compressor or BrewZilla hardware actions are performed by Python Core.
```

---

## Status

BrewAssistant v4 is actively evolving.

Current Python Core status:

```text
v1.1 Runtime Engine + Read-only Core
```

Current Brewday Runtime status:

```text
✅ Runtime normalization
✅ Timeline engine
✅ Brewfather compensation hook
✅ Manual refresh service
✅ Manual Brewday engine/services
✅ Premium runtime dashboard support
🔜 Manual timed-step auto-advance
🔜 Manual session persistence across HA restart
🔜 BrewZilla hardware reality mapping
🔜 Timed Fermentation Runtime
```

---

## Disclaimer

This project is intended for hobby brewing automation and process tracking. Always verify sanitation, pressure limits, electrical safety, and fermentation decisions manually when needed.
