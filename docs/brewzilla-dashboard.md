# BrewZilla Cockpit Dashboard

This document describes the current BrewZilla Cockpit dashboard direction after the verified Brewfather RAW → BrewAssistant → BrewZilla test.

The dashboard is an operator cockpit. Business logic belongs in the Python integration.

---

## Current cockpit

Current generated card:

```text
brewzilla_cockpit_v3_production_raw_runtime.yaml
```

Purpose:

```text
Brewday operator view
+ BrewZilla hardware status
+ direct control diagnostics
+ ABORT
+ compact RAW debug
```

The cockpit is intended for the current BrewZilla/RAPT hardware profile but should continue to read canonical BrewAssistant entities where possible.

---

## Layout

Recommended structure:

```text
Hero / operator summary
↓
Power + ABORT actions
↓
Brew Tracker Runtime
↓
BrewZilla Hardware
↓
Direct Control Diagnostics
↓
RAW Timeline Debug
```

---

## Hero card

The top card should show:

```text
runtime state / stage
current human-friendly step
current temp → tracker target
Delta
Power / Heater / Pump / Watts
Device target
orchestration mode
next step
remaining time
progress bar
RAW resolved index / raw index
control reason
```

Example runtime labels:

```text
Ramp to 55°C
Hold 55°C · 2 min
```

The hero card should not display the lagging `sensor.brewfather_brew_tracker_step` as the source of truth.

---

## Operator actions

The normal action row should contain:

```text
Power
ABORT
```

Power toggles:

```text
switch.brewzilla
```

ABORT calls:

```text
brewassistant.abort_brewzilla
```

The ABORT service turns off:

```text
switch.brewzilla_heater
switch.brewzilla_pump
```

Hold action fallback may still call `switch.turn_off` directly for heater/pump.

---

## Runtime section

Recommended entities:

```text
sensor.brewassistant_brewday_runtime_step
sensor.brewassistant_brewday_runtime_next_step
sensor.brewassistant_brewday_target_temperature
sensor.brewassistant_brewday_live_time_remaining_minutes
sensor.brewassistant_brewday_live_progress
sensor.brewassistant_brewday_snapshot_age_minutes
```

The runtime section should be simple and readable during brewing.

---

## Hardware section

Recommended entities:

```text
sensor.brewassistant_brewzilla_current_temperature
sensor.brewassistant_brewzilla_target_temperature
sensor.brewzilla_power
switch.brewzilla
switch.brewzilla_heater
switch.brewzilla_pump
sensor.brewzilla_connection
number.brewzilla_heat_utilization
number.brewzilla_pump_utilization
```

`switch.brewzilla` is main power only. It does not imply heater output.

Expected behavior:

```text
BrewZilla ON, heater OFF → low/idle watts
BrewZilla ON, heater ON  → high watts depending on heat utilization
```

---

## Direct control diagnostics

Recommended entities:

```text
sensor.brewassistant_brewzilla_requested_target
sensor.brewassistant_brewzilla_applied_target
sensor.brewassistant_brewzilla_target_delta
sensor.brewassistant_brewzilla_target_sync_needed
sensor.brewassistant_brewzilla_can_apply_target
sensor.brewassistant_brewzilla_orchestration_mode
sensor.brewassistant_brewzilla_control_reason
sensor.brewassistant_brewzilla_safety_state
```

Important distinction:

```text
target_sync_needed = target value must be changed
heater_action_needed = heater output must be changed
pump_action_needed = pump output must be changed
```

A target can already be synchronized while heater or pump still needs action.

---

## RAW timeline debug

Debug card:

```text
brewfather_raw_timeline_v2.yaml
```

RAW debug should show:

```text
Brewfather raw status
stage index
raw step index
resolved step index
raw_step_name
remainingSeconds
progressPercent
snapshot age
```

RAW debug should be visible during development and acceptance testing, but can later be moved behind an Advanced/Debug expander.

---

## Visual style

Preferred style:

```text
dark theme friendly
large current step
large current → target temperature line
clear status chips
big ABORT button
minimal normal-operation noise
RAW/debug separated from operator view
```

---

## Current status

```text
✅ BrewZilla Cockpit v3 generated
✅ Uses BrewAssistant runtime entities
✅ Shows RAW resolved index diagnostics
✅ Uses brewassistant.abort_brewzilla
✅ Matches verified low-temperature Brew Tracker test flow
```

Remaining dashboard validation:

```text
[ ] Re-test v3 cockpit after backend update/restart
[ ] Validate layout during a normal mash profile
[ ] Move RAW timeline to Advanced/Debug once the real-batch behavior is stable
[ ] Tune visual wording after first real brewday
```
