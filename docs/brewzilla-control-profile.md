# BrewZilla Advice Control Profile

Status: active development / test notes  
Last synced: 2026-07-05

This document describes the current BrewAssistant BrewZilla control strategy used during supervised Brewfather Brew Tracker tests.

## Control layers

BrewAssistant does not treat Brewday Advice as a standalone controller. The current design is layered:

1. BrewZilla base profile
2. Brewday Advice modifiers
3. Safety / guard modifiers
4. Direct-control apply

The base profile provides conservative default heat and pump levels. Brewday Advice then adjusts those values based on target delta, temperature rate, mash/wort separation and stage context.

## Base profile

The built-in profile is currently named:

```text
brewzilla_35l_small_batch_default
```

Current heat profile:

```text
Ramp:
  >5.0°C below target   -> 45 %
  3.0-5.0°C             -> 30 %
  2.0-3.0°C             -> 22 %
  1.0-2.0°C             -> 15 %
  0.5-1.0°C             -> 8 %
  0.2-0.5°C             -> 5 %
  <=0.2°C / over target -> 0 %

Mash hold:
  >2.0°C below target   -> 15 %
  0.7-2.0°C             -> 10 %
  0.2-0.7°C             -> 5 %
  <=0.2°C / over target -> 0 %
```

Current real-mash pump profile:

```text
Ramp:                 50 %
Mash hold:            50 %
Overshoot mix:        45 %
Thermal mix:          70 %
Mash circulation floor after mash-in: 40 %
```

Water-only tests may still use the stronger water-test pump profile:

```text
Ramp:                 70 %
Mash hold:            50 %
Overshoot mix:        50 %
Thermal mix:          80 %
```

The selected learning context controls which pump profile is used:

```text
select.brewassistant_brewzilla_learning_context = Water only -> water-test pump profile
select.brewassistant_brewzilla_learning_context = Real mash  -> real-mash pump profile
Unknown                                                   -> real-mash conservative profile
```

## Positive-control gate

Brewday Advice must not resurrect stale targets when Brewday Runtime is idle, inactive, completed or otherwise outside an active control state.

If positive control is blocked, BrewAssistant may only issue safe-down actions:

```text
target_sync_needed = false
desired_heat_utilization = 0 %
desired_pump_utilization = 0 %
desired_heater_on = false
desired_pump_on = false
```

Expected diagnostics when this gate catches stale runtime/advice state:

```yaml
advice_positive_control_blocked: true
advice_positive_control_blocked_reason: brewday_runtime_not_active
```

A stale Idle/Inactive runtime must not produce:

```yaml
actions:
  - set_target:...
  - set_heat_utilization:...
  - set_pump_utilization:...
```

## Mash-in gate

Before mash-in is confirmed, BrewAssistant may stop circulation and hold pump utilization at 0 %. This is intentional: it prevents automatic circulation before the operator confirms that grain has been added and the mash is safe to circulate.

After the operator confirms mash-in, BrewAssistant starts mash circulation and applies a 50 % pump utilization baseline.

Expected event-log markers:

```yaml
apply_result: mash_circulation_started
actions:
  - mash_in_complete
  - set_pump_utilization:50.0
  - pump_on
mash_in_gate_state: mash_in_complete
```

## Mash circulation floor

After mash-in is complete, BrewAssistant should keep a minimum pump utilization floor during ramp and mash-hold stages.

Current rule:

```text
If mash_in_gate_state == mash_in_complete
and stage_kind is ramp or mash_hold
and no safety/gate/abort guard is active:
  pump_on = true
  pump_utilization >= 40 %
```

Normal ramp/hold profile still requests 50 %. The 40 % floor only prevents the pump from dropping too low when another modifier would otherwise lower it. Thermal mix may temporarily raise pump utilization to 70 % during real mash or 80 % during water-only tests.

Expected diagnostics:

```yaml
advice_mash_circulation_floor_active: true
advice_mash_circulation_floor_utilization: 40
advice_desired_pump_on: true
desired_pump_utilization: 50
```

## Thermal mix modifier

Thermal mix is active when BrewAssistant has separate mash and wort/internal temperatures and the values indicate stratification.

Current trigger intent:

```text
wort/internal temperature is above target
mash temperature is still below target
mash and wort/internal are meaningfully different
```

There is also an earlier approach trigger:

```text
wort/internal temperature is within 1.0°C below target
mash temperature is at least 1.5°C below target
mash and wort/internal are meaningfully different
```

This lets BrewAssistant cap heat before the wort/internal side overshoots while the mash is still lagging.

Current real-mash effect:

```text
heat utilization capped to 5 % or 0 %
pump utilization raised to 70 %
```

Water-only thermal mix may still raise pump utilization to 80 %.

Expected event-log markers:

```yaml
advice_thermal_mix_active: true
advice_heat_profile_phase: thermal_mix_heat_cap
advice_thermal_mix_reason: wort_near_target_mash_lagging
```

or after the wort/internal side has passed target:

```yaml
advice_thermal_mix_active: true
advice_heat_profile_phase: thermal_mix_heat_cap
advice_thermal_mix_reason: wort_above_target_mash_lagging
```

## Paused mash-hold maintenance

Brewfather Brew Tracker can report a mash hold as paused while the brewer still expects the current target to be maintained. BrewAssistant now allows narrow positive control during paused mash-hold states, but only when the target is already synced and the requested action is a limited hold-maintenance action.

Current limits:

```text
max paused hold heat utilization: 15 %
max paused hold pump utilization: 80 %
max positive heat below target window: 6.0°C
```

Expected event-log markers:

```yaml
apply_result: paused_hold_maintenance_applied
actions:
  - paused_hold_set_heat_utilization:10.0
  - paused_hold_set_pump_utilization:50.0
```

or during thermal mix:

```yaml
apply_result: paused_hold_maintenance_applied
actions:
  - paused_hold_set_heat_utilization:0.0
  - paused_hold_set_pump_utilization:70.0
```

## Local-control lease

The local-control lease is a short passive observation window after BrewAssistant changes the BrewZilla target. It exists because BrewZilla regulates temperature locally once target and utilization have been applied.

Current behavior:

```text
passive observe window: 45 seconds
lease is created only after set_target
```

The lease is broken early when Brewday Advice sees risk or meaningful profile changes.

Break reasons include:

```text
thermal_mix_active
advice_phase:thermal_mix_heat_cap
advice_phase:fast_rise_near_target
advice_phase:moderate_rise_final_approach
near_target_taper_zone
heat_profile_changed
pump_profile_changed
utilization_action_needed
observe_window_elapsed
```

Expected event-log marker:

```yaml
local_control_lease_break_reason: thermal_mix_active
```

or:

```yaml
local_control_lease_break_reason: near_target_taper_zone
```

## Recommended Brewfather test recipe settings

For BrewAssistant/BrewZilla control testing, short 2-minute ramps are useful as stress tests but can make the integration look unstable because target transitions happen before temperatures and telemetry have settled.

Recommended test settings:

```text
Ramp between targets: 5 min
Hold/stable time: unchanged
```

Interpretation:

```text
Ramp 66 -> 72°C: 5 min
Hold 72°C: 30 min
Total elapsed for that transition: 35 min
```

The ramp is not dead time; mash enzymes still work during the ramp. However, a recipe hold time should be interpreted as time at or near the target temperature after the ramp step.

## What to check in event logs

For the next supervised test, check for:

```yaml
apply_result: paused_hold_maintenance_applied
advice_mash_circulation_floor_active: true
advice_thermal_mix_active: true
advice_thermal_mix_reason: wort_near_target_mash_lagging
advice_positive_control_blocked: true   # only after runtime goes idle/inactive
local_control_lease_break_reason: thermal_mix_active
local_control_lease_break_reason: near_target_taper_zone
```

Also watch that long stretches of:

```text
BrewZilla local-control lease active; BA observes while BrewZilla regulates locally.
```

are limited to short periods after target changes and do not hide needed heat/pump corrections.
