# BrewZilla Backend

Status: active development / supervised hot-side beta  
Last synced: 2026-08-29

This document describes the backend responsibilities for BrewAssistant's BrewZilla/RAPT hot-side control path.

For detailed heat/pump tuning, see [`../brewzilla-control-profile.md`](../brewzilla-control-profile.md). For equipment learning, see [`../brewzilla-equipment-learning.md`](../brewzilla-equipment-learning.md). For the end-to-end operator flow, see [`../brewday-brewzilla.md`](../brewday-brewzilla.md).

---

## Purpose

The BrewZilla backend connects normalized Brewday Runtime intent to physical BrewZilla/RAPT state.

Responsibilities:

```text
- read normalized source/stage/step/target intent
- read BrewZilla target, temperature, heater, pump and utilization state
- resolve mash/control/wort temperature context
- decide whether to monitor, block, request confirmation, recover telemetry or apply
- preserve BrewZilla local regulation when an already-valid local target exists
- preserve Manual Brew operator-owned channels during normal orchestration
- enforce Supervised Apply for automatic positive physical actions
- enforce ABORT/safe-down above all normal ownership or advice
- record enough evidence to reconstruct decisions in Flight Recorder
- feed passive equipment-learning evidence without making learning a control source
```

The backend is not unattended autopilot.

---

## High-level control path

```text
Brewday source resolver
  -> Brewfather actual-start ownership / Manual ownership
  -> normalized Brewday Runtime
  -> BrewZilla orchestration snapshot
  -> Brewday Advice / heat-strike / mash / thermal-mix layers
  -> freshness / target-trust / local-regulation guards
  -> Manual channel-ownership gate
  -> Supervised Apply gate for positive AUTO actions
  -> physical executor after explicit confirmation
  -> Brewday Event Log
```

Independent emergency path:

```text
hardware BrewZilla ABORT
  -> heater OFF
  -> pump OFF
  -> heat utilization 0
  -> pump utilization 0
  -> positive-action lockout
```

Brewday operator ABORT wraps this physical path and also latches BrewAssistant hot-side ownership OFF until explicit rearm.

---

## Important backend files

| File | Responsibility |
| --- | --- |
| `brewzilla_orchestration.py` | Core snapshot and physical apply path for target/utilization/heater/pump. |
| `brewzilla_supervised_runtime_guard.py` | Converts automatic positive plans into Supervised Apply pending state. |
| `brewzilla_supervised_readback_grace.py` | Narrow grace for stale RCL number-readback after confirmed writes. |
| `brewzilla_no_positive_gate.py` | Blocks positive control when runtime is not trusted/active. |
| `brewzilla_execution_guard.py` | Final execution-state protection. |
| `brewzilla_target_trust_guard.py` | Prevents unsafe/stale target rewinds. |
| `brewzilla_advice_control.py` | Converts stage/delta/rate context into desired heat/pump profile. |
| `brewzilla_heat_strike_profile.py` | Pre-mash-in strike target/profile logic. |
| `brewzilla_temperature.py` | BrewZilla/internal/external process temperature resolution. |
| `brewzilla_mash_in_gate.py` | Mash-in operator transition state. |
| `brewzilla_mash_in_target_patch.py` | Releases strike target to active mash target. |
| `brewzilla_mash_in_complete_safe_down_guard.py` | Safe transition into mash circulation. |
| `brewzilla_mash_priority_thermal_mix_guard.py` | Mash-priority heat floor + wort/internal limiter. |
| `brewzilla_local_regulation_heat_guard.py` | Preserves valid BrewZilla local regulation during degraded telemetry. |
| `brewzilla_freshness_guard.py` | RAPT/RCL freshness diagnostics. |
| `brewzilla_rcl_value_recovery_guard.py` | Telemetry refresh/recovery without control rewrites. |
| `brewzilla_active_rcl_recovery_guard.py` | Active hot-side RCL recovery policy. |
| `brewzilla_paused_guard.py` | Paused-state safe-down / narrow mash-hold behavior. |
| `brewzilla_manual_brew_control.py` | Final channel-scoped Manual Brew ownership gate. |
| `brewzilla_learning.py` | Live advisory/learning context. |
| `brewzilla_equipment_learning.py` | Persistent passive equipment evidence. |

Brewday-side ownership/safety files that directly affect this backend:

```text
custom_components/brewassistant/brewday/brewfather_ownership.py
custom_components/brewassistant/brewday/brewday_operator_abort.py
custom_components/brewassistant/brewday/brewday_runtime.py
custom_components/brewassistant/supervised_apply.py
```

---

## Brewfather ownership: batch phase is not enough

Brewfather does not own the hot side merely because the batch says `Brewing` or because its payload contains `active: true`.

A Brewing tracker parked at its initial Start step remains ready-only when it still shows:

```text
status paused
stage 0 / step 0
progress 0
remaining == duration
current step Start / Starta mäsktimer
```

Ownership starts only after positive evidence that the tracker actually started, such as:

```text
running/active tracker status
advanced stage/step
progress > 0
remaining time decreased
current step no longer the Start marker
```

Once started, ownership is latched to that tracker/batch so a later legitimate pause does not throw away authority.

An active Brewday operator ABORT latch overrides this started latch and forces Brewfather hot-side ownership false until the operator rearms control.

---

## Manual Brew channel ownership

Manual Brew can assign target, heat and pump independently between operator and BA.

```text
Manual Target Override ON
  -> operator owns target

Allow Heater Control ON
  -> BA owns heater + heat utilization
Allow Heater Control OFF
  -> operator owns heater + heat utilization

Allow Pump Control ON
  -> BA owns pump + pump utilization
Allow Pump Control OFF
  -> operator owns pump + pump utilization
```

Mixed ownership is intentional.

The Manual ownership gate suppresses **normal** BA reassert for operator-owned channels. It does not rewrite or override an already blocked safety/ABORT snapshot.

Safety order:

```text
normal Advice / control intent
  -> safety / freshness / ABORT guards
  -> Manual channel ownership suppression
```

If safety has already blocked positive control, operator ownership cannot turn it back into a positive automatic action.

---

## Supervised Apply

Automatic positive physical actions require explicit operator confirmation.

Positive examples:

```text
target increase
heat-utilization increase
pump-utilization increase
heater ON
pump ON
```

Safe-down examples may execute directly when risk-reducing:

```text
heater OFF
pump OFF
utilization decrease/zero required by safety or ABORT
```

Expected positive flow:

```text
orchestration computes plan
  -> pending_confirmation
  -> operator CONFIRM
  -> live plan rebuilt and identity/safety checked
  -> physical executor writes only the still-valid plan
  -> supervised_executed
```

The executor must not be callable as a generic automatic coordinator shortcut.

Rejecting the plan is different from ABORT:

```text
REJECT / AVVISA
  -> cancel/suppress exact pending intention
  -> runtime may continue
  -> no physical emergency safe-down implied
```

---

## Confirmed-plan RCL readback grace

RAPT Cloud Link may replay an older target/utilization value after a successful write.

Physically reproduced example:

```text
BA confirms heat utilization 0 -> 100
RCL later republishes stale 100 -> 0
```

Without a grace rule, this looks like a fresh positive need and can create duplicate confirmation.

Current protection:

```text
- remember number increases that were explicitly confirmed and actually sent
- same source/stage/step/target context only
- bounded window: 240 s
- stale copy may be ignored without new write and without new pending plan
- heater/pump ON are excluded from silent reassert
- ABORT invalidates grace immediately
```

This is a readback-consistency guard, not permission to hide a persistent real hardware fault.

---

## Target concepts

Three target views matter:

```text
runtime target
  sensor.brewassistant_brewzilla_runtime_target_temperature

effective BA target
  sensor.brewassistant_brewzilla_target_temperature

physical device/RAPT target
  sensor.brewassistant_brewzilla_device_target_temperature
```

The effective target may move with runtime intent before any physical target write is permitted. Flight Recorder therefore keeps `brewzilla_effective_target` separate from `brewzilla_device_target`.

`target_delta` is synchronization delta:

```text
requested_target - applied_target
```

not temperature error.

---

## Read-only vs direct action modes

Typical orchestration modes:

```text
monitor        -> observe; no physical action required
local-control  -> BrewZilla already regulates against a valid local target
manual-control -> operator owns one or more channels
direct-control -> an action is desired; positive AUTO work still passes Supervised Apply
blocked        -> safety/ownership/freshness/ABORT prevents positive execution
```

Equipment learning/advice is never itself a control mode.

---

## Local BrewZilla regulation preservation

Once BA has given BrewZilla a valid active target, BrewZilla regulates locally against that target.

Telemetry degradation should therefore not casually result in:

```text
heat utilization 0
heater OFF
```

merely because RCL is stale.

Recovery may refresh/reload telemetry, but must preserve the local target/control state unless an explicit safety/completed/ABORT context requires safe-down.

---

## RCL freshness and recovery

Expected recovery behavior:

```text
active hot-side + stale/degraded RCL
  -> request update_entity when useful
  -> optionally request guarded/throttled config-entry reload
  -> expose recovery/freshness diagnostics
  -> preserve valid local BrewZilla target
  -> do not modify target/heat/pump merely as a recovery side effect
```

Fresh live temperature/power can suppress an unnecessary full reload even when older configuration entities look stale.

Source quality should later influence learning confidence separately from control safety.

---

## Clean heat-strike model

Before mash-in:

```text
Mash/BLE/control probe = readiness gate
BrewZilla internal/wort = safety/overshoot view
BrewZilla target = actual strike target
Pump = thermal mixing/equalization
```

Current gate heat schedule:

```text
>10°C below target: 100%
8–10°C: 75%
5–8°C: 50%
3–5°C: 25%
1–3°C: 10%
<=1°C / overshoot: 0%, heater off
```

The safety view may cap this lower. Pump mixing protects against stratification and helps make the mash/BLE readiness reading meaningful.

---

## Mash-in state machine

Mash-in is a supervised one-way transition.

```text
ready_for_mash_in
  -> Mash-In Started
  -> target released toward real mash target
  -> pump OFF while grain is added
  -> Brewfather Continue / fallback completion
  -> Mash-In Complete
  -> circulation starts
```

A stale late Mash-In Started request must not move the state backwards after `mash_in_complete`.

After mash-in, a circulation floor prevents normal mash/ramp logic from accidentally reducing pump flow too far.

---

## Thermal mix and mash-priority control

During real mash:

```text
mash/BLE temperature = primary ramp/hold process signal
wort/internal temperature = limiter/safety view
```

Thermal-mix logic becomes relevant when the internal/wort view approaches or exceeds target while the mash probe still lags. It should reduce overshoot without collapsing useful heat merely because the internal sensor is warmer than the grain-bed/process measurement.

---

## External process-temperature sensor ownership

The optional external sensor, e.g. RAPT BLE Thermometer, is phase-owned.

Fixed architecture:

```text
Heat strike -> Mash -> Mash out -> Sparge -> Pre-boil
  owner = Brewday/BrewZilla hot-side backend

Boil starts
  Brewday releases external sensor ownership

Chill -> Transfer
  owner = CFC backend
  role = CFC outlet / wort-out temperature
```

BrewZilla internal temperature remains the primary kettle temperature for Brewday hot-side context.

This handoff must eventually be represented explicitly enough that two backends cannot both treat the external sensor as their owned process measurement at the same time.

---

## Hardware ABORT

The authoritative BrewZilla ABORT path performs:

```text
heater OFF
pump OFF
heat utilization 0
pump utilization 0
positive-action ABORT lockout
```

No normal orchestration, Manual ownership, Advice or learning path may re-enable positive hardware during the lockout.

The 2026-08-29 physical test verified the complete safe-down and subsequent lockout blocking.

---

## Brewday operator ABORT

Brewday-level ABORT adds source/ownership semantics around the same physical safe-down.

```text
button.brewassistant_abort_brewday
  -> persist Brewday operator latch = aborted
  -> discard pending Supervised Apply plan
  -> reset Manual Brewday to idle
  -> call authoritative BrewZilla ABORT
  -> normalized Brewday runtime becomes aborted/source None
```

Brewfather cannot reclaim hot-side ownership while that operator latch is active, even if its external tracker continues running.

Latch state:

```text
sensor.brewassistant_brewday_operator_control_state
  armed | aborted
```

Release:

```text
button.brewassistant_rearm_brewday_control
```

Rearm releases only Brewday ownership. The independent BrewZilla hardware lockout remains authoritative.

The latch is stored persistently and loaded before coordinator/orchestration actions, preventing a Home Assistant restart from silently rearming an aborted brewday.

---

## Flight Recorder evidence baseline

The 2026-08-29 Brewfather test verified:

```text
Planning               -> no hot-side ownership
Brewing pre-start      -> no ownership despite active:true
Play / paused->running -> Brewfather ownership
same Flight Recorder started_at across the whole transition
pending confirmation   -> heater/pump remain OFF
operator confirm       -> heat 100, pump util 70, heater ON, pump ON
supervised_executed    -> complete confirmed plan recorded
hardware ABORT         -> OFF/OFF/0/0 + lockout
```

The next dedicated physical regression is the new Brewday operator ABORT/rearm persistence path.

---

## Equipment learning

Learning remains passive evidence.

```text
Brewday/Flight Recorder observations
  -> equipment/context buckets
  -> planned-vs-actual segment analysis
  -> operator-facing timing/profile suggestions
```

It must not:

```text
- silently change Brewfather
- alter live target/heat/pump because a recommendation exists
- mix water-only evidence with real-mash evidence without context
```

Planned segment types include heatstrike, mash-in drop, mash ramp, mash hold, mash-out, boil ramp and boil.

---

## Next validation

```text
[ ] Brewday ABORT button: physical safe-down + runtime_state aborted
[ ] Brewfather remains non-owner while operator latch aborted
[ ] HA restart preserves operator latch
[ ] explicit rearm restores eligibility but not hardware lockout bypass
[ ] real-mash heat-strike/mash-in behavior
[ ] real-mash 66°C hold and 66 -> 72°C ramp
[ ] full boil ramp / boil
[ ] Brewday external-sensor release at Boil
[ ] CFC external-sensor acquisition during Chill/Transfer
[ ] equipment-learning planned-vs-actual timing evidence
```
