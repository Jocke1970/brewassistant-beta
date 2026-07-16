# BrewZilla Advice Control Profile

Status: active development / supervised hot-side testing  
Last synced: 2026-07-16

This document describes the current BrewAssistant BrewZilla control strategy used during supervised Brewfather Brew Tracker tests.

The design target is **supervised apply**, not unattended autopilot. BrewAssistant may set targets, heat utilization and pump utilization when the current runtime and safety context allow it, but the brewer remains the operator.

## Core principles

```text
BA reads Brewfather/Brewday intent.
BA sets BrewZilla target/utilization when allowed.
BrewZilla regulates locally against the target it has received.
BA observes, refreshes stale telemetry, and corrects only when a trusted rule says it should.
```

Important control philosophy:

```text
If BrewZilla already has a valid active target,
BA must not kill heat merely because RCL telemetry is stale/degraded.

RCL trouble should trigger refresh/reload diagnostics and warnings,
not silent heat starvation.
```

Explicit ABORT, runtime completed, and manual emergency stop still win and may safe-down heat/pump.

## Control layers

The current BrewZilla path is layered:

1. Brewday Runtime resolver
2. BrewZilla orchestration snapshot
3. Brewday Advice control profile
4. Heat-strike / mash-in / thermal-mix guards
5. Freshness / RCL recovery / execution / target-trust guards
6. Local BrewZilla regulation preservation
7. Direct-control apply
8. Equipment learning evidence layer

## Base profile

The built-in profile is currently named:

```text
brewzilla_35l_small_batch_default
```

Current base heat profile:

```text
Ramp / strike / step ramp:
  >20.0°C below target  -> 100 %
  10.0-20.0°C           -> 75 %
  5.0-10.0°C            -> 60 %
  3.0-5.0°C             -> 45 %
  1.0-3.0°C             -> 25 %
  0.3-1.0°C             -> 10 %
  <=0.3°C / over target -> 0 % base profile

Mash hold / recovery:
  >2.0°C below target   -> 75 %
  0.7-2.0°C             -> 50 %
  0.2-0.7°C             -> 25 %
  <=0.2°C / over target -> 0 % base profile
```

The 0% rows are profile recommendations, not a license for stale/RCL guards to turn off BrewZilla local regulation after BA has already given BZ a valid target.

Current real-mash pump profile:

```text
Ramp:                         50 %
Mash hold:                    50 %
Overshoot mix:                45 %
Thermal mix:                  70 %
Mash circulation floor:       40 % after mash-in complete
```

Water-only tests may still use stronger circulation because there is no malt bed:

```text
Ramp:                         70 %
Mash hold:                    50 %
Overshoot mix:                50 %
Thermal mix:                  80 %
```

The selected learning context controls pump profile selection:

```text
select.brewassistant_brewzilla_learning_context = Water only -> water-test pump profile
select.brewassistant_brewzilla_learning_context = Real mash  -> real-mash pump profile
Unknown                                                   -> real-mash conservative profile
```

## Heat-strike and mash-in handoff

Heat-strike and mash-in are deliberately split from normal mash control.

During pre-mash-in strike heating, BA may hold a strike-water target higher than the upcoming mash target. The goal is to account for grain addition drop.

At the Brewfather Hold/mash-addition transition, BA should avoid holding boosted heat-strike targets too long when wort/internal is already near or above strike. The heat-strike transition guard may refresh RCL and brake the transition profile.

When **Mash-In Started** is pressed:

```text
BA releases the latched strike target.
BA resolves the active Brewfather mash target directly from Brewday Runtime.
BZ target should become the real mash target, for example 66.0°C.
Pump remains OFF while malt is being mixed in.
Heat is not forcibly killed; BZ keeps regulating locally.
```

Expected markers:

```yaml
mash_in_gate_state: mash_in_started
mash_in_started_hold_active: true
mash_in_complete_visible: true
mash_in_started_set_target: 66.0
mash_in_started_set_pump_utilization: 0.0
```

When **Mash-In Complete** is pressed:

```text
BA starts mash circulation.
BA keeps/safely downs target to the active mash target.
BA requests fresh RCL readback around the mash-control handoff.
```

Expected markers:

```yaml
apply_result: mash_circulation_started_safe_down_applied
actions:
  - mash_in_complete
  - set_pump_utilization:50.0
  - pump_on
  - mash_in_complete_safe_down_set_target:66.0
mash_in_gate_state: mash_in_complete
```

## Mash circulation floor

After mash-in is complete, BA should keep circulation alive during ramp and mash-hold stages unless a higher safety/gate/abort guard is active.

```text
If mash_in_gate_state == mash_in_complete
and stage_kind is ramp or mash_hold:
  pump_on = true
  pump_utilization >= 40 %
```

Normal ramp/hold profile still requests 50%. The 40% floor only prevents another modifier from dropping circulation too low.

## Thermal mix modifier

Thermal mix is the stratification guard. It is active when BA has separate mash and wort/internal temperatures and the values indicate uneven temperature distribution.

Trigger intent:

```text
wort/internal temperature is above target while mash still lags, or
wort/internal is near target while mash is still significantly below target.
```

Current real-mash behavior is mash-priority with wort/internal as limiter:

```text
Mash/BLE temperature is the primary ramp/hold control signal.
Wort/internal remains a safety limiter.
```

Thermal mix no longer treats large mash lag as a reason to collapse real-mash ramp heat to 5% by default.

Current real-mash cap behavior:

```text
approach thermal mix:       heat cap 15 %, pump 70 %
active thermal mix:         heat cap 10 %, pump 70 %
high/extreme thermal mix:   heat cap 5 %,  pump 70 %

real mash ramp, mash >=2°C below target,
wort/internal < target + 5°C:
  heat cap floor 45 %, pump 70 %

real mash hold, mash >=2°C below target,
wort/internal < target + 5°C:
  heat cap floor 30 %, pump 70 %
```

This keeps warm wort/internal readings as a limiter, but lets the actual mash reach target instead of stalling several degrees low.

Expected diagnostics:

```yaml
advice_thermal_mix_active: true
advice_heat_profile_phase: thermal_mix_heat_cap
advice_thermal_mix_reason: wort_above_target_mash_lagging
advice_mash_priority_thermal_mix_active: true
advice_mash_priority_thermal_mix_floor: 45.0
```

## RCL freshness and stale value recovery

RAPT Cloud Link can sometimes report or refresh an entity without changing the actual temperature value. BA therefore treats value freshness as important, not only report traffic.

During active heat-strike/ramp/mash control, stale RCL values should trigger:

```text
homeassistant.update_entity on relevant RCL/BrewZilla entities
possible guarded config-entry reload
clear diagnostic/audit fields
```

But stale RCL must not automatically mean:

```text
set_heat_utilization:0
heater_off
```

when BZ already has a valid active target.

Expected diagnostics may include:

```yaml
rcl_value_stale_guard_active: true
rcl_value_stale_guard_refresh_requested: true
rcl_value_stale_guard_reload_requested: true
local_regulation_heat_guard_active: true
```

## Local-control lease

The local-control lease is a short passive observation window after BA changes the BrewZilla target. It exists because BrewZilla regulates locally once target and utilization have been applied.

Current behavior:

```text
passive observe window: 45 seconds
lease is created only after set_target
```

The lease is broken early when Advice sees risk or meaningful profile changes.

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

## Positive-control gate

Brewday Advice must not resurrect stale targets when Brewday Runtime is idle, inactive, completed or otherwise outside an active control state.

If positive control is blocked, BA may only issue safe-down actions when there is no valid active BrewZilla target that should be preserved by local regulation.

Expected diagnostics:

```yaml
advice_positive_control_blocked: true
advice_positive_control_blocked_reason: brewday_runtime_not_active
```

## Equipment learning layer

The BrewZilla equipment learning layer is separate from the live advice/control profile.

```text
Analysis / Advice:
  What is happening right now?

Equipment Learning:
  What has this specific BrewZilla repeatedly shown over time?

Profile Suggestion:
  What profile adjustment should be proposed for operator review later?
```

The learning model records evidence and creates candidate suggestions. It does not auto-apply learned changes.

Current v1 suggestion target:

```text
Real mash + thermal mix active
mash >=2°C below target
profile heat cap <=10 %
wort/internal only moderately above target

Candidate profile suggestion:
  thermal_mix.ramp_mash_priority_floor -> 45 %
  thermal_mix.mash_hold_mash_priority_floor -> 30 %
```

See [`brewzilla-equipment-learning.md`](brewzilla-equipment-learning.md) for model details.

## Recommended Brewfather test recipe settings

For BrewAssistant/BrewZilla control testing, short 2-minute ramps are useful stress tests but can make the integration look unstable because target transitions happen before temperatures and telemetry have settled.

Recommended test settings:

```text
Ramp between targets: 5 min
Hold/stable time: unchanged
```

For a realistic mash-in test:

```text
Strike / mash-in target: 69-72°C depending on recipe and grain temperature
Mash target after grain: real first mash rest target, for example 66°C
```

BA should show **Mash-In Started** at strike readiness, then use the active Brewfather mash target as effective control target after the button is pressed.

## What to check in event logs

For the next supervised test, check for:

```yaml
mash_in_gate_state: ready_for_mash_in
mash_in_started_visible: true
event_type: mash_in_started
mash_in_started_hold_active: true
mash_in_started_set_target: 66.0
apply_result: mash_in_started_hold_applied
event_type: mash_in_confirmed
apply_result: mash_circulation_started_safe_down_applied
advice_mash_circulation_floor_active: true
advice_thermal_mix_active: true
advice_mash_priority_thermal_mix_active: true
rcl_value_stale_guard_refresh_requested: true   # only if RCL value actually stalls
local_regulation_heat_guard_active: true        # only when a stale/guard layer tries to kill heat despite valid target
brewzilla_equipment_learning_observations: ...
brewzilla_equipment_learning_suggestion: ...    # optional candidate, not auto-applied
```

Also verify that long stretches of:

```text
BrewZilla local-control lease active; BA observes while BrewZilla regulates locally.
```

are limited to short periods after target changes and do not hide needed heat/pump corrections.
