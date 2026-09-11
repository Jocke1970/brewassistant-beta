# BrewZilla Advice Control Profile

Status: active development / supervised hot-side testing  
Last synced: 2026-09-06

This document describes the current BrewAssistant BrewZilla control strategy used during supervised Brewfather Brew Tracker and Manual Brewday tests.

The design target is **supervised apply with bounded dedicated phase authority**, not unattended autopilot.

## Core principles

```text
BA reads Brewfather/Brewday intent.
BA resolves process and safety temperature roles.
BA sets BrewZilla target/utilization when current ownership allows it.
BrewZilla regulates locally against the target it has received.
BA actively refreshes RCL coordinator data during owned hot-side phases.
BA distinguishes report freshness from unchanged-value age.
Manual Brew may assign target, heat and pump ownership independently to the operator.
ABORT/hard safety always win.
```

If BrewZilla already has a valid active target, ordinary telemetry degradation must not silently starve local regulation of heat. Genuine data loss is fail-passive: no new BA writes while preserving the last valid local context.

## Control layers

Conceptual order:

1. Brewday Runtime resolver
2. BrewZilla orchestration snapshot
3. temperature-role resolution
4. Heatstrike / Mash-In dedicated controller
5. RCL report freshness + active coordinator refresh
6. target-trust/readback/local-regulation guards
7. Manual Brew operator ownership
8. generic Supervised Apply outside dedicated authority
9. direct-control apply
10. Equipment Learning evidence layer
11. outer fail-passive / ABORT boundaries as installed by the package chain

Exact wrapper order in `custom_components/brewassistant/brewzilla/__init__.py` is functional architecture and must be checked before reordering code.

## Base advice profile

The legacy/base advice profile is currently named:

```text
brewzilla_35l_small_batch_default
```

Its ramp/mash recommendations remain useful outside the dedicated Clean Heatstrike controller, but they must not be confused with the current Heatstrike phase contract.

Representative base heat profile:

```text
Ramp / step ramp:
  >20.0°C below target  -> 100 %
  10.0-20.0°C           -> 75 %
  5.0-10.0°C            -> 60 %
  3.0-5.0°C             -> 45 %
  1.0-3.0°C             -> 25 %
  0.3-1.0°C             -> 10 %
  <=0.3°C / over target -> 0 % base recommendation

Mash hold / recovery:
  >2.0°C below target   -> 75 %
  0.7-2.0°C             -> 50 %
  0.2-0.7°C             -> 25 %
  <=0.2°C / over target -> 0 % base recommendation
```

A 0 % recommendation is not permission for a stale-data guard to disable valid BrewZilla local regulation.

## Heatstrike and Mash-In handoff

Heatstrike is controlled by the dedicated pre-mash physical controller after Brewfather Play grants phase authority.

BrewAssistant writes the real strike target and uses:

```text
external MASH/process probe = readiness/process authority
BrewZilla internal/WORT     = limiter/safety context
```

### Gradient relief

```text
MASH/BLE still below strike
AND mash/wort gradient >= 1.5 °C
AND hottest-view overshoot > +0.5 °C
AND hottest-view overshoot <= +2.0 °C

=> heat authority cap 5 %
=> heater master available
=> pump 100 %
```

Above +2.0 °C hottest-view overshoot:

```text
heat 0 % / heater OFF hard stop
```

This is a narrow gradient exception only.

### Mash-In Started

```text
BA releases the latched strike target.
BA resolves the actual mash target from Brewday Runtime, e.g. 66.0 °C.
Pump OFF / utilization 0 % while malt is being mixed in.
The target is not held at strike merely because Brewfather is paused.
```

Expected markers include:

```yaml
mash_in_gate_state: mash_in_started
mash_in_started_hold_active: true
mash_in_started_set_target: 66.0
mash_in_started_set_pump_utilization: 0.0
```

### Automatic Mash-In Complete

Automatic completion requires an edge after Mash-In Started:

```text
post-start Brewfather PAUSED observed
THEN later Brewfather RUNNING / Continue
```

These do not count by themselves:

```text
BF already running when Started is pressed
active Brewfather target changing
normalized BA runtime remaining live/running
```

After completion, normal mash circulation may resume (typically 50 % requested by the current mash profile).

The manual Mash-In Complete path remains fallback if the external BF transition cannot be observed reliably.

## Mash circulation floor

After Mash-In Complete, BA should keep circulation alive during ramp/mash-hold stages unless a higher safety/gate/ABORT guard is active.

Conceptually:

```text
if mash_in_gate_state == mash_in_complete
and stage_kind is ramp or mash_hold:
  pump_on = true
  pump_utilization >= conservative floor
```

Normal profile may request more than the floor.

## Thermal mix modifier

Thermal mix handles stratification while preserving the distinction between mash/process and wort/internal temperatures.

Real-mash intent:

```text
Mash/BLE = primary ramp/hold signal
Wort/internal = limiter/safety context
```

Representative real-mash behavior:

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

These later-mash modifiers are separate from the pre-mash 5 % / 100 % gradient-relief rule.

## RCL report freshness and value stagnation

RAPT Cloud Link may repeatedly report the same physical value. Therefore BrewAssistant now separates:

```text
report freshness
  -> state.last_reported
  -> fallback state.last_updated
  -> trust clock for orchestration/fail-passive

value age / stagnation
  -> state.last_updated + explicit temperature-change tracking
  -> diagnostic signal only
```

A stable target or temperature is not stale merely because its value does not change.

### Active hot-side coordinator refresh

While Brewday owns an active hot-side phase:

```text
every 30 seconds
  -> homeassistant.update_entity
  -> one BrewZilla CoordinatorEntity only
  -> DataUpdateCoordinator.async_request_refresh()
```

One trigger entity avoids several identical refresh requests to a shared coordinator.

Expected diagnostics include:

```yaml
rcl_active_hot_side_polling_active: true
rcl_active_hot_side_poll_interval_seconds: 30
rcl_active_hot_side_poll_requested: true|false
rcl_active_hot_side_poll_last_requested_at: ...
rcl_active_hot_side_poll_entity_ids:
  - sensor.brewzilla_temperature
```

### Value-stagnation diagnostics

A suspiciously unchanged Heatstrike temperature may still produce:

```yaml
rcl_value_stale_guard_active: true
rcl_value_stale_guard_refresh_delegated: true
```

This does **not** redefine canonical temperature freshness and does not independently fan out refresh requests.

### Hard recovery

`reload_config_entry` remains reserved for hard connection loss/extreme **report** staleness and is throttled to a minimum 15-minute interval.

## Fail-passive behavior

Genuine report loss during active control:

```text
no new BA writes
preserve valid local target/output state
request/indicate recovery
```

Fail-passive must not be triggered simply because a temperature stays stable for 90 seconds.

ABORT, hard safety and explicit process safe-down remain authoritative.

## Confirmed readback grace

RCL may replay an older target/utilization immediately after a successful write. BrewAssistant keeps bounded confirmed-write grace for the same runtime intent.

Limits:

```text
bounded time
same runtime/source/stage/step/target intent
no silent heater/pump re-energization
persistent mismatch requires a new decision
ABORT invalidates grace
```

## Manual Brew operator ownership

```text
manual target override ON
  -> operator owns target

allow heater control ON
  -> BA owns heater + heat utilization
allow heater control OFF
  -> operator owns heater + heat utilization

allow pump control ON
  -> BA owns pump + pump utilization
allow pump control OFF
  -> operator owns pump + pump utilization
```

Mixed ownership is valid. Normal BA reassert logic must not silently reclaim an operator-owned channel.

## Brewfather / Manual Brew mutual exclusion

Brewfather ownership begins only after positive Brew Tracker start evidence, not merely because a batch phase says Brewing.

A started Brewfather tracker retains ownership through legitimate pause. Manual Brew must not compete for the same hot-side channels while that ownership is active.

## Positive-control gate

Brewday Advice must not resurrect stale targets when normalized Brewday Runtime is idle, inactive, completed or otherwise outside active control.

Risk-reducing actions may still occur through the appropriate safety/ABORT path.

## Equipment learning layer

Equipment Learning is separate from live control:

```text
Analysis / Advice
  -> what is happening now?

Equipment Learning
  -> what has this BrewZilla repeatedly shown?

Profile Suggestion
  -> what adjustment should be proposed for operator review?
```

Learning records evidence and may create candidate suggestions. It does not auto-apply learned changes.

## Recommended next physical test

Use a realistic Brewfather sequence rather than an artificially rapid target schedule.

Checkpoint:

```text
Heatstrike
-> verify 30 s RCL report refresh
-> READY
-> Mash-In Started
-> target becomes actual mash target (e.g. 66 °C)
-> pump OFF / 0 %
-> BF PAUSED observed after Started
-> BF Continue / RUNNING
-> Mash-In Complete
-> normal mash circulation
-> continue through 66 °C hold / 66 -> 72 °C ramp when practical
```

## Event/diagnostic evidence to capture

```yaml
mash_in_gate_state: ready_for_mash_in|mash_in_started|mash_in_complete
mash_in_started_set_target: 66.0
mash_in_started_set_pump_utilization: 0.0
seen_paused_after_mash_in_started: true
rcl_active_hot_side_polling_active: true
rcl_active_hot_side_poll_interval_seconds: 30
rcl_active_hot_side_poll_last_requested_at: ...
rcl_active_hot_side_recovery_active: true|false
rcl_value_stale_guard_active: true|false
fail_passive_mode: ...
apply_result: ...
actions: ...
```

Use Flight Recorder state to decide whether the backend transitioned even if the dashboard presentation appears delayed or ambiguous.
