# Brewday / BrewZilla Direct Flow

This document describes the current BrewAssistant Brewday flow for Brewfather Brew Tracker → BrewAssistant → BrewZilla.

Status: **MVP validated in supervised Brewfather/BrewZilla dry-run with event logging**.

The first verified path is BrewZilla/RAPT hardware, but the architecture should remain as hardware-profile friendly as possible. BrewAssistant should expose canonical `sensor.brewassistant_brewday_*` and `sensor.brewassistant_brewzilla_*` entities to dashboards instead of making every card parse raw Brewfather data directly.

---

## Verified flow

The low-temperature water test and the follow-up dry-run mash profile verified the core technical chain:

```text
Brewfather Brew Tracker raw timeline
        ↓
BrewAssistant RAW runtime resolver
        ↓
BrewAssistant brewday runtime sensors
        ↓
BrewZilla orchestration helper
        ↓
BrewZilla target / heater / pump actions
        ↓
Brewday event log
```

Verified test sequences:

```text
Low-temperature water test:
30°C → 35°C → 40°C → 45°C → 50°C → 55°C

Dry-run mash profile:
45°C → 55°C → 65°C → 72°C → 78°C
```

Observed result:

```text
✅ Brewfather Brew Tracker was read
✅ BrewAssistant followed the RAW tracker timeline
✅ BrewAssistant ignored lagging convenience step sensors
✅ BrewAssistant can resolve active step ahead of RAW index using stage timing
✅ Paused Brewfather state remains stable as paused/freeze-state
✅ BrewZilla target changed through the full dry-run sequence
✅ Heater and pump actions were evaluated and logged
✅ ABORT remained available as a hard stop
✅ Event log captured runtime, target sync and orchestration events
⚠️ Remaining issues are primarily presentation/wording and full-process validation beyond mash
```

---

## Why RAW Brew Tracker is used

The convenience entity `sensor.brewfather_brew_tracker_step` may lag behind the Brewfather web UI.

BrewAssistant therefore resolves the active step from:

```text
sensor.brewfather_brew_tracker_raw.attributes.data.stages
stage.remainingSeconds
step.time anchors
```

This is handled in:

```text
custom_components/brewassistant/brewday_runtime_core.py
```

The runtime keeps both values for diagnostics:

```text
raw_step_index
resolved_step_index
raw_step_name
```

Dashboard cards may show these in debug sections, but normal operator UI should use the normalized runtime step and target.

`raw_step_index != resolved_step_index` is not automatically an error. It often means BrewAssistant has calculated the active step from the stage timeline while Brewfather/RAPT Cloud still exposes an older raw index.

---

## Runtime presentation

Brewfather may create several internal tracker steps with the same recipe name. For example, a ramp and a hold can both be named `Step 6 - 55C final low-temp sync`.

BrewAssistant now exposes human-friendly labels:

```text
Ramp to 55°C
Hold 55°C · 2 min
```

instead of displaying duplicated raw names as current and next step.

The original Brewfather name remains available as `raw_step_name` in attributes for debug use.

---

## Paused Brewfather behavior

When Brewfather status is paused, BrewAssistant treats the snapshot as a freeze-frame:

```text
runtime_state = paused
awaiting_snapshot = false
paused_freeze = true
live_timer_active = false
```

BrewAssistant keeps the current step and target instead of advancing into `awaiting_snapshot` just because remaining time reaches zero while paused.

---

## Target and output actions

Target sync and hardware output actions are separate decisions.

This is important because the BrewZilla target may already be correct while the heater or pump still needs to be started.

The orchestration layer evaluates:

```text
target_sync_needed
heater_action_needed
pump_action_needed
```

Therefore this case is valid and should trigger an action:

```text
Brew Tracker target = 30°C
BrewZilla target = 30°C
BrewZilla current = 25.6°C
heater = off

→ target_sync_needed = false
→ heater_action_needed = true
→ heater should turn on
```

Implemented in:

```text
custom_components/brewassistant/brewzilla_orchestration.py
```

`target_delta` means synchronization delta:

```text
requested_target - applied_target
```

It is not the same as temperature delta:

```text
current_temperature - target_temperature
```

---

## Refresh policy

BrewAssistant requests Brewfather entity refreshes through a smart refresh policy.

Implemented in:

```text
custom_components/brewassistant/brewday_refresh_policy.py
custom_components/brewassistant/brewday_refresh.py
```

Policy overview:

```text
Normal real batch:
- Mash / boil / other active stage: about every 5 minutes
- Chilling: about every 2 minutes
- Idle/setup/cleanup: about every 10 minutes

Test batch / short-step recipe:
- about every 30 seconds

Step ending soon:
- about every 15 seconds

Awaiting snapshot:
- about every 15 seconds with a bounded burst limit

Minimum cooldown:
- 10 seconds
```

Manual refresh is still available as a service, but normal operation should not require an Apply Target button.

---

## Event log

Brewday event log records post-run analysis data for runtime and BrewZilla orchestration.

Current service names are kept for compatibility:

```text
brewassistant.brewday_audit_start
brewassistant.brewday_audit_stop
brewassistant.brewday_audit_clear
brewassistant.brewday_audit_snapshot
```

Main sensor:

```text
sensor.brewassistant_brewday_event_log_summary
```

Detailed documentation:

```text
docs/brewday-audit.md
```

---

## Services

### Manual Brewfather refresh

```text
brewassistant.force_brewfather_refresh
```

Use for diagnostics or when the external Brewfather integration appears stale.

### Apply BrewZilla target/actions

```text
brewassistant.apply_brewzilla_target
```

Direct target/action application should only be used when the relevant BrewAssistant policy permits it.

### Abort BrewZilla

```text
brewassistant.abort_brewzilla
```

This is the hard stop path for BrewZilla orchestration.
