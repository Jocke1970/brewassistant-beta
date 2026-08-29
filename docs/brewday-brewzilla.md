# Brewday / BrewZilla Direct Flow

This document describes the current BrewAssistant hot-side control path from Brewfather Brew Tracker or Manual Brewday through BrewAssistant to BrewZilla/RAPT hardware.

Status: **supervised hot-side beta baseline after the 2026-08-29 physical Brewfather/Supervised Apply and water-only validation**.

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
operator ABORT / hardware ABORT / explicit safe-down
        > source ownership
        > supervised positive control
        > local-target preservation
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

---

## Confirmed-plan RCL readback grace

RAPT Cloud Link can briefly publish an older configuration value after BA has successfully written a new target/utilization/switch state.

The confirmed-plan readback grace remembers configuration increases that were explicitly confirmed and actually sent. For a bounded window, the same source/stage/step/target may ignore a stale copy of those exact writes without issuing a new write or a new pending plan.

Important limits:

```text
- number-write grace is time-bounded
- switch-echo grace is shorter and observe-only
- grace is scoped to the same confirmed runtime intention
- heater/pump are never silently re-energized because of the grace
- persistent mismatch requires a fresh supervised decision
- ABORT invalidates the grace immediately
```

The 2026-08-29 water-only run gave a natural physical PASS for the intended no-duplicate-confirmation behavior after the initial confirmed Heatstrike plan.

---

## Brewday operator ABORT

Brewday distinguishes rejecting one pending action from aborting the hot-side session.

```text
REJECT / AVVISA
  = discard one pending Supervised Apply intention

ABORT BREWDAY / ABORT BRYGGDAG
  = physical BrewZilla safe-down
  + discard pending positive intent
  + reset Manual Brewday session to idle
  + latch BrewAssistant hot-side ownership OFF
```

The Brewday ABORT reuses the authoritative BrewZilla ABORT path and performs:

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

The latch is persisted through Home Assistant storage and loaded before orchestration decisions. Physical testing on 2026-08-29 verified that a Home Assistant restart does not silently re-arm an aborted Brewday.

The operator must explicitly use:

```text
REARM CONTROL / ÅTERAKTIVERA STYRNING
```

to release the Brewday ownership latch. Rearming Brewday does **not** bypass BrewZilla's independent hardware ABORT lockout.

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

## Explicit heat safe-down precedence

The 2026-08-29 water-only run exposed an ordering bug: Clean Heatstrike correctly calculated 0% heat / heater OFF near strike, but a later local-target-preservation guard suppressed the safe-down because a valid BrewZilla target existed. The same pattern appeared after the target was lowered from 71.8°C to 66.0°C while the process was still above 70°C.

PR #173 fixes the precedence rule.

Current invariant:

```text
explicit process/safety zero-heat request
  > ordinary local-target heat preservation
```

In particular:

```text
Clean Heatstrike final coast / hottest-view safety zero
  -> 0% heat / heater OFF may be applied

Mash-In Started explicit zero request
  -> 0% heat / heater OFF may be applied

process temperature > active requested target + 0.3°C
  -> local-target preservation must not resurrect positive heat
```

This does not remove local BrewZilla thermostat preservation for ordinary stale/passive telemetry interpretation; it only prevents that preservation layer from overriding an intentional process/safety safe-down.

Implementation:

```text
custom_components/brewassistant/brewzilla/brewzilla_local_regulation_heat_guard.py
```

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

Pump-utilization increases remain positive physical actions and may require a new Supervised Apply confirmation even when the underlying Heatstrike strategy asks for stronger mixing near target.

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

The water-only run was aborted before Boil, so the release/acquisition handoff remains physically unverified.

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

The intended physical contract during `mash_in_started` is:

```text
pump OFF
pump utilization 0%
```

The 2026-08-29 water-only run showed pump ON / 50% in live UI around this transition, while the reviewed Flight Recorder sequence did not retain an unambiguous `mash_in_started` event before `mash_in_complete`. Do not infer a backend failure from that ambiguity alone. The next physical run must stop at Mash-In Started and verify gate state, timestamp and physical pump state before Brewfather Continue.

Required checkpoint:

```text
mash_in_started
started_at != null
pump OFF
pump utilization 0%
```

---

## Physical mash-hold and ramp timing (#157)

#157 is implemented as a strictly read-only telemetry layer. It must not participate in target, heat, pump or ownership decisions.

Physical timing rules:

```text
Ramp
  -> timer starts when the physical ramp is observed
  -> completes when selected process temperature reaches target tolerance

Mash hold
  -> does not start merely because Brewfather entered the step
  -> starts when selected process temperature reaches target band ±0.3°C
  -> first hold also waits for Mash-In Complete when that gate exists

PAUSE
  -> freezes active process elapsed time

ABORT
  -> stops timing without issuing a hardware command
```

If Brewfather/source schedule advances ahead of the physical process, telemetry preserves the physical timer and exposes a source-schedule mismatch. It does not rewrite the runtime or control path.

Current-brew history records ramp/hold duration, wall duration, pause duration, ΔT, average °C/min, process-temperature source, learning context and heat/pump utilization at start/end.

Initial UI:

```text
dashboard/cards/brewday_physical_timing.yaml
dashboard/cards/brewday_physical_timing_sv.yaml
```

The first implementation is volatile across Home Assistant restart until field validation justifies persistence work.

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

A true explicit ABORT/completed/process-safety safe-down context is different and remains authoritative.

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

A physical 2026-08-29 test verified that `started_at` remained unchanged across Planning / pre-start / Play.

---

## Physically verified 2026-08-29 chain

Verified:

```text
✅ Planning starts/keeps Flight Recorder while hot-side remains non-owning
✅ Brewing pre-start with active:true does not take hot-side ownership
✅ Play provides positive start evidence and Brewfather becomes runtime owner
✅ Flight Recorder does not rotate at Play
✅ positive heat/pump plan waits for explicit confirmation
✅ explicit confirmation writes heat utilization, pump utilization, heater ON and pump ON
✅ supervised_executed is recorded after the complete plan
✅ confirmed stale switch echo did not reopen the same confirmation in the observed run
✅ BrewZilla ABORT turns heater/pump OFF and both utilizations to 0
✅ BrewZilla ABORT lockout blocks delayed/recreated positive actions
✅ Brewday operator ABORT performs physical safe-down and ownership lock
✅ HA restart preserves Brewday operator ABORT
✅ explicit rearm restores eligibility without creating a positive action
✅ Bryggråd APPLY executed a 100% -> 95% heat-utilization recommendation
```

Observed failures/ambiguities from the water-only run:

```text
❌ pre-#173 local-target preservation suppressed Heatstrike final zero-heat safe-down
❌ pre-#173 local-target preservation could keep positive heat after 71.8 -> 66.0°C target downshift
? Mash-In Started physical pump-off evidence was ambiguous and must be retested explicitly
```

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
REARM CONTROL / ÅTERAKTIVERA STYRNING
```

The CONFIRM button is visually pending-driven. ABORT is a separate red safety control and must never be confused with rejection of a pending plan.

Known compatibility-UI cleanup:

```text
`Starta mäskcirkulation` must only be offered after Mash-In Complete when circulation still needs to start and the pump is actually off.
```

---

## Remaining validation

Recommended next checks:

```text
[ ] Water-only regression: Heatstrike final coast physically applies heat 0% / heater OFF
[ ] Water-only regression: 71.8 -> 66.0°C target downshift suppresses positive heat while above target
[ ] Explicit Mash-In Started checkpoint with pump OFF / utilization 0 before Continue
[ ] #157: physical 66°C hold timer starts only on target reach
[ ] #157: PAUSE freezes hold/ramp timing
[ ] #157: 66 -> 72°C physical ramp is logged separately with ΔT / °C/min
[ ] Brewsteps follows the BrewTracker-owned physical phase
[ ] First real-mash heat-strike and mash-in thermal behavior
[ ] Full boil ramp/boil flow
[ ] Boil release of the external process sensor
[ ] CFC Chill/Transfer acquisition of that external sensor
[ ] Continue Equipment Learning planned-vs-actual timing validation
```
