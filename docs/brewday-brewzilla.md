# Brewday / BrewZilla Direct Flow

This document describes the current BrewAssistant hot-side control path from Brewfather Brew Tracker or Manual Brewday through BrewAssistant to BrewZilla/RAPT hardware.

Status: **supervised hot-side beta baseline after the 2026-08-29 physical Brewfather/Supervised Apply validation**.

BrewAssistant is intentionally an operator-supervised controller. Runtime progression and hardware execution are separate concerns: Brewday may understand the next process step without silently energizing hardware.

---

## Control philosophy

```text
Brewfather Brew Tracker or Manual Brewday
        ↓
normalized Brewday Runtime
        ↓
BrewZilla orchestration / safety guards
        ↓
Supervised Apply gate for positive physical actions
        ↓
BrewZilla target / utilization / heater / pump
        ↓
Brewday Event Log + diagnostics + learning evidence
```

Safety ordering is authoritative:

```text
operator ABORT / hardware ABORT / safe-down
        > source ownership
        > supervised positive control
        > normal orchestration / learning / UI intent
```

Positive physical actions must never bypass the explicit operator confirmation path. Risk-reducing safe-down actions do not wait for confirmation.

---

## Brewfather phase vs actual tracker start

Brewfather batch phase and Brew Tracker execution are separate concepts.

A batch may report:

```text
brew_tracker_batch_status: Brewing
active: true
status: paused
stage_index: 0
current stage step: 0
progress: 0
remainingSeconds == duration
current step: Start / Starta mäsktimer
```

This is **pre-start**, not hot-side ownership.

Current ownership rules:

```text
Planning
  -> visible / ready
  -> no Brewfather hot-side ownership

Brewing, parked on initial Start step
  -> visible / ready
  -> no Brewfather hot-side ownership

Brewing with positive start evidence
  -> Brewfather owns normalized hot-side runtime

Started tracker paused later
  -> ownership remains latched to the same tracker/batch

Fermenting / completed / unrelated phases
  -> no BrewZilla hot-side ownership
```

Positive start evidence includes running tracker status, advancing stage/step, non-zero progress, decreasing remaining stage time, or leaving the explicit Start step.

`active: true` alone is not start evidence.

Implementation:

```text
custom_components/brewassistant/brewday/brewfather_ownership.py
```

---

## Brewfather vs Manual Brew ownership

Brewfather and Manual Brew are mutually exclusive positive-control runtime owners.

When an actually started Brewfather tracker owns the hot side:

```text
- Brewfather is the authoritative normalized runtime source.
- Manual Brew positive start/next/direct-stage actions are not allowed to compete.
- An already active Manual Brew session is paused for the handoff.
- Manual Brew does not auto-resume when Brewfather later disappears.
- BrewAssistant does not silently stop or finish the external Brewfather session.
```

Manual Brew can still use channel-scoped operator ownership while it is the active runtime:

```text
Manual Target Override ON
  -> operator owns BrewZilla target

Allow Heater Control OFF
  -> operator owns heater + heat utilization

Allow Pump Control OFF
  -> operator owns pump + pump utilization
```

Safety and ABORT always outrank Manual ownership.

Relevant modules:

```text
custom_components/brewassistant/brewday/brewday_runtime.py
custom_components/brewassistant/brewday/manual_brewday_store.py
custom_components/brewassistant/brewzilla/brewzilla_manual_brew_control.py
```

---

## Supervised Apply

Automatic positive BrewZilla actions are gated by Supervised Apply.

Examples of positive actions:

```text
target increase
heat-utilization increase
pump-utilization increase
heater ON
pump ON
```

Expected flow:

```text
1. Runtime/orchestration builds the desired physical plan.
2. BA stores a pending plan and exposes it to the cockpit.
3. No positive hardware write occurs while pending.
4. Operator presses CONFIRM ACTION / BEKRÄFTA ÅTGÄRD.
5. BA rebuilds the live plan and validates source/stage/step/target/plan identity.
6. Only a still-valid matching plan is executed.
7. Event Log records supervised_confirmed and supervised_executed.
```

Rejecting a pending plan is **not** an emergency stop:

```text
REJECT ACTION / AVVISA ÅTGÄRD
  -> rejects and suppresses the current matching pending intention
  -> does not perform a physical ABORT
```

A rejected plan remains suppressed while the exact intent/context is unchanged. A meaningful runtime/context change may legitimately create a new pending plan.

Implementation:

```text
custom_components/brewassistant/supervised_apply.py
custom_components/brewassistant/brewzilla/brewzilla_orchestration.py
```

---

## Confirmed-plan RCL readback grace

RAPT Cloud Link can briefly publish an older configuration value after BA has successfully written a new target/utilization value.

A physical test reproduced this pattern after confirmation:

```text
heat utilization written 0 -> 100
later stale readback 100 -> 0
```

Without protection, that stale readback looked like a new positive action and reopened Supervised Apply for the same already-approved intent.

The confirmed-plan readback grace now remembers only the configuration increases that were explicitly confirmed and actually sent. For a short bounded window, the same source/stage/step/target may ignore a stale copy of those exact number writes without issuing a new write or a new pending plan.

Important limits:

```text
- grace is time-bounded (currently 240 s)
- it is scoped to the same confirmed runtime intention
- it covers confirmed target/heat/pump number increases only
- heater ON and pump ON are deliberately not silently re-energized
- ABORT invalidates the grace immediately
```

Implementation:

```text
custom_components/brewassistant/brewzilla/brewzilla_supervised_readback_grace.py
```

---

## Brewday operator ABORT

Brewday now distinguishes rejecting one pending action from aborting the hot-side session.

```text
REJECT / AVVISA
  = discard one pending Supervised Apply intention

ABORT BREWDAY / ABORT BRYGGDAG
  = physical BrewZilla safe-down
  + discard pending positive intent
  + reset Manual Brewday session to idle
  + latch BrewAssistant hot-side ownership OFF
```

The Brewday ABORT reuses the authoritative BrewZilla ABORT path. It therefore performs the same physical safe-down:

```text
heater OFF
pump OFF
heat utilization 0
pump utilization 0
BrewZilla positive-action ABORT lockout
```

In addition, Brewday stores a persistent operator-control latch. While active:

```text
sensor.brewassistant_brewday_runtime_state = aborted
sensor.brewassistant_brewday_operator_control_state = aborted
normalized Brewday source = None
Brewfather cannot automatically reclaim BA hot-side ownership
```

The latch is persisted through Home Assistant storage and is loaded before orchestration decisions. A Home Assistant restart must therefore not silently re-arm an aborted Brewday.

The operator must explicitly use:

```text
REARM CONTROL / ÅTERAKTIVERA STYRNING
```

to release the Brewday ownership latch. Rearming Brewday does **not** bypass BrewZilla's independent hardware ABORT lockout; that lockout remains authoritative until its own guard allows control again.

Implementation:

```text
custom_components/brewassistant/brewday/brewday_operator_abort.py
custom_components/brewassistant/button.py
custom_components/brewassistant/coordinator.py
custom_components/brewassistant/brewday/brewfather_ownership.py
```

---

## Target concepts

Do not conflate runtime intent with the physical RAPT target.

```text
sensor.brewassistant_brewzilla_runtime_target_temperature
  = Brewday runtime target

sensor.brewassistant_brewzilla_target_temperature
  = normalized/effective target; runtime-first while active

sensor.brewassistant_brewzilla_device_target_temperature
  = physical/raw BrewZilla/RAPT target normalized for BA
```

Flight Recorder therefore exposes both:

```text
brewzilla_effective_target
brewzilla_device_target
```

A runtime target change alone is not evidence of a physical target write.

---

## Target and output actions

Target sync and output actions are evaluated independently:

```text
target_sync_needed
heater_action_needed
heater_stop_needed
pump_action_needed
pump_stop_needed
heat_utilization_action_needed
pump_utilization_action_needed
```

`target_delta` means:

```text
requested_target - applied_target
```

It is not the process-temperature delta.

---

## Clean heat-strike model

The pre-mash-in model is physical-state dominant:

```text
Mash/BLE/control probe = readiness gate
BrewZilla internal/wort = safety view / overshoot limiter
BrewZilla target = real strike target
Pump = mixing/equalization tool
```

Current heat schedule from gate delta:

```text
>10°C below strike: 100%
8–10°C below strike: 75%
5–8°C below strike: 50%
3–5°C below strike: 25%
1–3°C below strike: 10%
<=1°C below strike / overshoot: 0%, heater off
```

The hottest safety view can cap heat below this gate request. Pump mixing is used to reduce thermal stratification.

Do not tune these thresholds casually; use Event Log evidence from real mash or controlled water tests.

---

## Extra process-temperature sensor ownership

The optional external process-temperature sensor, for example a RAPT BLE Thermometer, has phase-scoped ownership.

This architecture is fixed:

```text
Heat strike -> Mash -> Mash out -> Sparge -> Pre-boil
  owner: Brewday Runtime / hot-side BrewZilla control
  role: extra process/mash temperature input

Boil starts
  Brewday Runtime releases the external sensor

Chill -> Transfer
  owner: CFC backend
  role: CFC outlet / wort-out temperature
```

BrewZilla's internal temperature remains Brewday Runtime's primary kettle temperature throughout the hot-side process. The external sensor handoff prevents Brewday and CFC from competing for the same physical measurement role.

---

## Mash-in state machine

Mash-in is a supervised one-way transition:

```text
ready_for_mash_in
  -> Mash-In Started
  -> grain addition / pump paused
  -> Brewfather Continue
  -> Mash-In Complete
  -> circulation resumes
```

A late/stale Mash-In Started action must not move an already completed mash-in backwards.

Relevant modules:

```text
custom_components/brewassistant/brewzilla/brewzilla_mash_in_gate.py
custom_components/brewassistant/brewzilla/brewzilla_mash_in_complete_safe_down_guard.py
custom_components/brewassistant/brewzilla/brewzilla_mash_in_state_guard.py
```

---

## RCL freshness and local regulation

Once BrewZilla has a valid local target, BA should preserve BrewZilla's local temperature regulation during telemetry degradation.

RCL recovery may:

```text
request homeassistant.update_entity
request a guarded/throttled config-entry reload where appropriate
mark freshness/recovery diagnostics
```

RCL recovery itself must not change target, heat utilization, pump utilization, heater or pump.

A true explicit ABORT/completed/safe-down context is different and remains authoritative.

---

## Flight Recorder / one brewday = one log

Brewday Event Log starts early enough to capture Planning, but a single Brewfather batch must remain one recorder session through actual start.

Expected continuity:

```text
Planning
  -> Brewing pre-start
  -> Play / tracker starts
  -> running hot-side Brewday

same started_at
same Flight Recorder session
```

The deterministic session-boundary latch, not a transient `idle`/no-owner pre-start snapshot, decides whether the next runtime activation belongs to a new brewday.

A physical 2026-08-29 test verified that `started_at` remained unchanged across `paused -> running` / Play.

---

## Physically verified 2026-08-29 chain

The current Brewfather/BrewZilla system test verified:

```text
✅ Planning starts/keeps Flight Recorder while hot-side remains non-owning
✅ Brewing pre-start with active:true does not take hot-side ownership
✅ Play provides positive start evidence and Brewfather becomes runtime owner
✅ Flight Recorder does not rotate at Play
✅ positive heat/pump plan waits for explicit confirmation
✅ explicit confirmation writes heat utilization, pump utilization, heater ON and pump ON
✅ supervised_executed is recorded after the complete plan
✅ normal follow-up ticks do not repeat already-satisfied writes
✅ BrewZilla ABORT turns heater/pump OFF and both utilizations to 0
✅ BrewZilla ABORT lockout blocks delayed/recreated positive actions
```

The new Brewday-level operator ABORT/rearm UI and persistent ownership latch should receive a short dedicated regression test after installation.

---

## Dashboard controls

General Brewday cockpit:

```text
dashboard/cards/brewassistant_brewday.yaml
dashboard/cards/brewassistant_brewday_sv.yaml
```

The operator controls are intentionally distinct:

```text
CONFIRM ACTION / BEKRÄFTA ÅTGÄRD
REJECT ACTION / AVVISA ÅTGÄRD
ABORT BREWDAY / ABORT BRYGGDAG
REARM CONTROL / ÅTERAKTIVERA STYRNING   # visible after Brewday ABORT
```

The CONFIRM button is visually pending-driven. ABORT is a separate red safety control and must never be confused with rejection of a pending plan.

---

## Remaining validation

Recommended next checks:

```text
[ ] Physical Brewday ABORT: one press produces safe-down + runtime_state aborted
[ ] Confirm Brewfather cannot reclaim ownership while operator_control_state is aborted
[ ] Confirm HA restart preserves the operator ABORT latch
[ ] Explicit REARM restores ownership eligibility but does not bypass hardware ABORT lockout
[ ] Validate real-mash heat-strike and mash-in thermal behavior
[ ] Validate full boil ramp/boil flow
[ ] Validate Boil release of the external process sensor
[ ] Validate CFC Chill/Transfer acquisition of that external sensor
[ ] Continue Equipment Learning planned-vs-actual timing validation
```
