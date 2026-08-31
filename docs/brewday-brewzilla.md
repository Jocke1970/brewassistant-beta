# Brewday / BrewZilla Direct Flow

This document describes the current BrewAssistant hot-side control path from Brewfather Brew Tracker or Manual Brewday through BrewAssistant to BrewZilla/RAPT hardware.

Status: **supervised hot-side beta baseline after the 2026-08-29 ownership/ABORT validation and 2026-08-31 Heatstrike/Mash-In water validation**.

BrewAssistant is intentionally an operator-supervised controller. Runtime progression and hardware execution are separate concerns: Brewday may understand the next process step without silently energizing hardware.

For the latest physical near-strike findings and contracts, see [`physical-validation-2026-08-31.md`](physical-validation-2026-08-31.md).

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

## Heat safe-down and local-regulation precedence

The 2026-08-29 water-only run exposed an ordering bug: an explicit process/safety zero-heat request could be suppressed by local-target preservation. PR #173 fixed that precedence for real safe-down contexts.

The 2026-08-31 water test then showed the opposite edge case: an ordinary near-strike final coast could disable the BrewZilla heater master too early while the external process probe was still below strike. PR #193 fixed that final-approach dead zone.

Current distinction:

```text
true explicit safety / overshoot / ABORT zero-heat request
  > ordinary local-target heat preservation

normal Heatstrike final approach while process probe is still below strike
  -> preserve BrewZilla local thermostat/heater enable
  -> bound utilization instead of forcing ordinary 0% coast
```

A true hottest-view overshoot above approximately target +0.5°C may still produce explicit heat 0 / heater OFF. ABORT and hard safety remain authoritative.

Implementation:

```text
custom_components/brewassistant/brewzilla/brewzilla_local_regulation_heat_guard.py
```

---

## Clean heat-strike model

The pre-mash-in model is physical-state dominant:

```text
MASH/external process probe = readiness authority
BrewZilla internal/WORT     = safety view / overshoot limiter
BrewZilla target            = real strike target
Pump                         = mixing/equalization tool
```

Far from target, BrewAssistant progressively reduces requested heat authority as the process closes on strike.

### Final approach after PR #193

The 2026-08-31 water test reproduced the dead zone at approximately:

```text
strike target       71.8 °C
MASH/process probe   69.6 °C
WORT/internal        71.5 °C
```

The process probe still needed energy, but the old logic could disable the heater master because the internal safety view was already close to target.

Current final-approach contract:

```text
process <=3 °C below strike
  -> keep positive local-regulation authority

safety headroom <=0.3 °C
  -> bounded positive authority, typically 25%

safety headroom <=3 °C
  -> bounded positive authority, typically up to 50%

true hottest-view overshoot > target +0.5 °C
  -> explicit heat 0 / heater OFF allowed
```

The purpose is to leave BrewZilla's local thermostat active against the written strike target while BrewAssistant limits authority and observes both the external readiness probe and internal safety view.

Pump mixing is used to reduce thermal stratification. Pump-utilization increases remain positive physical actions and may require a new Supervised Apply confirmation.

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
  owner: Cooling/CFC backend
  role: CFC outlet / wort-out temperature when using CFC
```

BrewZilla's internal temperature remains Brewday Runtime's primary kettle temperature throughout the hot-side process. The external sensor handoff prevents Brewday and Cooling/CFC from competing for the same physical measurement role.

The water-only runs have not yet validated the Boil release / Chill acquisition handoff.

---

## Mash-In readiness and state machine

Mash-In is a supervised one-way transition:

```text
ready_for_mash_in
  -> Mash-In Started
  -> grain addition / pump paused
  -> Brewfather Continue
  -> Mash-In Complete
  -> circulation resumes
```

A late/stale Mash-In Started action must not move an already completed mash-in backwards.

### Automatic readiness after PR #194

Automatic Mash-In READY now requires:

```text
fresh canonical external MASH/process temperature
within strike target ±1.0 °C
```

A stale locked process value is retained only for diagnostics, including its age. It must never create automatic READY.

### Bounded operator strike acceptance

When RAPT Cloud process telemetry is stale or lagging but the vessel is physically near strike, the operator may use the bounded readiness action up to:

```text
strike target ±2.0 °C
```

The fallback is only physically plausible when BrewZilla's local target and internal/WORT state independently show a near-strike vessel condition.

The operator action only latches `ready_for_mash_in`; it does **not** change target, heater, pump or utilization.

The intended physical contract during `mash_in_started` remains:

```text
pump OFF
pump utilization 0%
```

The 2026-08-29 water-only run left this checkpoint ambiguous. The next continuous regression must stop at Mash-In Started and verify gate state, timestamp and physical pump state before Brewfather Continue.

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

The UI is now presented as part of the consolidated Brewday Runtime flow rather than a competing hardware cockpit.

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

For Mash-In readiness specifically, stale external process temperature is diagnostic-only. It cannot satisfy automatic READY.

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

The Mash-In Started physical pump-off checkpoint remained ambiguous and must still be retested explicitly.

---

## Physical findings 2026-08-31

Observed and isolated:

```text
✅ Heatstrike final-approach dead zone reproduced at 71.8 / 69.6 / 71.5 °C
✅ PR #193 merged with local-regulation final-approach contract
✅ stale RAPT Cloud MASH/process telemetry reproduced near Mash-In
✅ PR #194 merged with fresh-only automatic READY and bounded operator acceptance
```

These fixes are covered by regression tests/CI, but the complete merged chain still needs one continuous physical water regression before the first real-mash run.

---

## Dashboard controls

General Brewday cockpit:

```text
dashboard/cards/brewassistant_brewday.yaml
dashboard/cards/brewassistant_brewday_sv.yaml
```

Consolidated Brewday Runtime process flow:

```text
dashboard/cards/brewassistant_brewday_runtime_flow.yaml
dashboard/cards/brewassistant_brewday_runtime_flow_sv.yaml
```

The runtime flow keeps physical timing and the Mash-In process handoff with Brewday, while generic pending/ABORT controls remain owned by the main Brewday cockpit. It must not become a second direct BrewZilla hardware cockpit.

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
[ ] Continuous water regression: Heatstrike closes the final few degrees without the pre-#193 dead zone
[ ] BrewZilla local regulation stays active through final approach / READY
[ ] Automatic Mash-In READY only from fresh canonical process telemetry within ±1.0 °C
[ ] Stale external process telemetry remains diagnostic-only
[ ] Bounded operator strike acceptance behaves correctly when intentionally needed
[ ] Explicit Mash-In Started checkpoint with pump OFF / utilization 0 before Continue
[ ] #157: physical 66°C hold timer starts only on target reach
[ ] #157: PAUSE freezes hold/ramp timing
[ ] #157: 66 -> 72°C physical ramp is logged separately with ΔT / °C/min
[ ] Brewsteps follows the BrewTracker-owned physical phase
[ ] First real-mash heat-strike and mash-in thermal behavior
[ ] Full boil ramp/boil flow
[ ] Boil release of the external process sensor
[ ] Cooling/CFC Chill/Transfer acquisition of that external sensor
[ ] Continue Equipment Learning planned-vs-actual timing validation
```
