# Fermentation Climate Supervisor

The Fermentation Climate Supervisor is the monitor-only bridge between the Fermentation Air Target Engine and the Home Assistant fermentation chamber climate entity.

Current version:

```text
monitor_only
```

It does not apply targets, call climate services, switch cooling or switch heating.

---

## Purpose

The Fermentation Air Target Engine answers:

```text
What chamber-air target would be suitable for this fermentation/cold-crash state?
```

The Fermentation Climate Supervisor answers:

```text
What would we do with climate.fermentation_chamber if apply-mode existed?
```

Current behavior is observation only.

---

## Current entity

```text
switch.brewassistant_fermentation_climate_supervisor_enabled
```

This is a switch because future versions may expose modes, but current behavior is monitor-only.

---

## Current backend module

```text
custom_components/brewassistant/fermentation_climate_supervisor.py
```

Registered through:

```text
custom_components/brewassistant/switch.py
```

---

## Inputs

```text
sensor.brewassistant_fermentation_effective_air_target
climate.fermentation_chamber
```

The supervisor reads the Air Target Engine snapshot and the current fermentation chamber climate state/target.

---

## Current attributes

Important attributes on `switch.brewassistant_fermentation_climate_supervisor_enabled`:

```text
enabled
mode
status
action
reason
ready
scope_active
test_mode_active
demand
recommended_air_target
air_target_sensor_state
raw_air_target
min_air_target
max_air_target
clamp_applied
clamp_reason
target_plausible_for_mode
controller_entity
controller_state
controller_target_temperature
target_delta
chamber_air_temperature
liquid_temperature
liquid_target_temperature
liquid_delta
last_evaluation
summary
source
mode_scope
```

---

## Status and action model

When disabled:

```text
status = disabled
action = none
reason = supervisor disabled
```

When enabled but no active fermentation/cold-crash scope exists:

```text
status = standby
action = none
reason = no active fermentation or cold-crash scope
```

When enabled and Air Target Engine is ready:

```text
status = demand from Air Target Engine
action = would_apply_target | hold_target | observe
```

Meaning:

```text
would_apply_target
→ recommended target differs from current climate target

hold_target
→ recommended target already matches current climate target

observe
→ not enough climate target context to calculate delta
```

No action performs a Home Assistant service call in the current version.

---

## Target delta

```text
target_delta = recommended_air_target - controller_target_temperature
```

Example:

```text
recommended_air_target = 0.5 °C
controller_target_temperature = 1.6 °C
target_delta = -1.1 °C
```

This means a future apply-mode would lower the chamber target by 1.1 °C.

---

## Validated snapshots

### Standby monitor

```text
Supervisor = on
Mode = standby
Status = standby
Action = none
Reason = no active fermentation or cold-crash scope
Ready = False
Scope = False
Test active = False
Recommended = None
Climate = climate.fermentation_chamber
Climate state = off
Climate target = 1.6
Target delta = None
Liquid = None
Liquid target = None
Liquid delta = None
Summary = standby · no active fermentation or cold-crash scope
Mode scope = monitor_only
```

### Cold-crash test monitor

```text
Supervisor = on
Mode = cold_crash
Status = strong_cooling
Action = would_apply_target
Reason = test mode: cold crash; liquid far above cold-crash target
Ready = True
Scope = True
Test active = True
Recommended = 0.5
Climate = climate.fermentation_chamber
Climate state = off
Climate target = 1.6
Target delta = -1.1
Liquid = 21.87
Liquid target = 1.0
Liquid delta = 20.87
Summary = strong_cooling · recommended 0.5 °C · test mode: cold crash; liquid far above cold-crash target
Mode scope = monitor_only
```

---

## Safety boundary

Current version intentionally does not include:

```text
climate.set_temperature
climate.set_hvac_mode
switch.turn_on
switch.turn_off
heater control
cooling control
```

It only reads states and exposes a snapshot.

---

## Future direction

Future modes may be introduced later:

```text
Off
Monitor only
Supervised apply
```

Supervised apply should require explicit user confirmation before changing the fermentation chamber target.

Important future rule:

```text
Air Target Engine calculates the desired chamber-air target.
Fermentation Climate Supervisor decides whether a climate target change would be appropriate.
Home Assistant climate integration handles heater/cooler switching and safety timing.
```
