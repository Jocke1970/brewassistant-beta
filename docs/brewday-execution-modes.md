# Brewday execution ownership modes

Status: architecture decision + field evidence  
Last synced: 2026-09-11

This document separates three concepts that must not be conflated in BrewAssistant:

```text
recipe/profile source
runtime/timer owner
physical BrewZilla control policy
```

A recipe may come from Brewfather while BrewAssistant owns the runtime. Likewise, an external runtime such as Brewfather Brew Tracker or a RAPT profile may own step/timer progression while BrewAssistant still owns the physical target/heat/pump decisions.

The hot-side actuation policy is orthogonal to runtime ownership:

```text
monitor/read-only
supervised apply
future direct/unattended apply
```

Changing who owns the runtime must never silently weaken ABORT, freshness, thermal or hardware safety guards.

---

## 1. Brewfather / Brew Tracker supervised execution

In this mode Brewfather/Brew Tracker owns the process timeline and timer.

```text
Brewfather recipe + Brew Tracker
        ↓
current Brew Tracker stage / step / target / timer
        ↓
normalized Brewday Runtime
        ↓
BrewAssistant physical interpretation
        ↓
BrewZilla target / heat / pump control
```

BrewAssistant follows the current Brew Tracker checkpoint but does not treat Brewfather's schedule clock as proof that the physical process has reached a target temperature.

### Verified 0-minute PAUS checkpoint

The 2026-09-11 water test verified that a 0-minute mash-profile step named `PAUS` can be used as a hard Brewfather/Brew Tracker checkpoint between a ramp and the following hold.

Observed contract:

```text
Brew Tracker status       -> paused
raw step name             -> PAUS
time remaining            -> 0
stage/progress position   -> frozen while paused
Resume in Brewfather      -> tracker returns to running and proceeds
```

This gives Brewfather-owned execution a practical way to avoid letting the following rest timer run while BrewAssistant/BrewZilla is still working toward the next physical target.

Recommended recipe shape when this behavior is desired:

```text
previous rest
  -> ramp toward next target
  -> 0 min PAUS at that target
  -> next timed rest
```

### Paused-target contract

A Brew Tracker pause is a freeze of source progression, not permission to pre-actuate the next target.

Required BrewAssistant behavior:

```text
tracker paused
  -> keep the current tracker target latched
  -> continue only the physical work needed to reach/hold that current target
  -> do not use next_step as a hardware target
  -> do not advance BrewZilla toward the following rest
  -> when target is physically ready, notify the operator
  -> operator resumes Brewfather
  -> only after running/new-step evidence may BA accept the next tracker target
```

The 2026-09-11 Flight Recorder exposed a bug against this contract: while the tracker was paused at 40 °C, orchestration could request 45 °C; while paused at 45 °C, the BrewZilla device target could move to 55 °C. This must be fixed before the 0-minute checkpoint pattern is considered production-ready.

The current BrewTracker integration is read-only toward tracker progression. BrewAssistant can detect physical target readiness and notify, but the operator must use Brewfather's Play/Resume action to release the checkpoint.

---

## 2. BrewAssistant-owned recipe execution

This is the future fully automated BrewAssistant path for a Brewfather recipe without using Brew Tracker as the runtime clock/state machine.

```text
Brewfather recipe/profile data
        ↓
BrewAssistant recipe adapter
        ↓
Python-owned Brewday plan/runtime
        ↓
physical ramp to target
        ↓
actual target-reach gate
        ↓
BA starts the hold timer
        ↓
BA advances to the next step
        ↓
BrewZilla control
```

In this mode Brewfather is a recipe source, not the active runtime authority.

Core rules:

```text
- BA owns stage, step, timer and progression.
- A timed rest begins only after the selected physical process temperature reaches its target band.
- Ramp duration is measured/learned from the real system; it is not a schedule deadline that forces progression.
- BrewTracker state is optional diagnostic context and must not drive progression.
- The Python runtime must persist/recover enough state to avoid silent step jumps after Home Assistant restart.
- External process-temperature ownership and Boil -> Chill handoff rules remain unchanged.
```

The existing Python-owned Manual Brewday runtime is the natural implementation foundation: instead of only using a default/manual BIAB plan, a future recipe adapter can populate the same normalized runtime model from Brewfather recipe/profile data.

"Fully automated progression" and "direct hardware apply" are separate decisions. The BA-owned runtime can initially run under Supervised Apply while step progression is automatic. A future direct-control policy may remove confirmation only after that path has its own explicit safety and field-validation baseline.

---

## 3. RAPT profile execution

RAPT profile execution is another external-runtime-owner path and remains distinct from both BrewTracker-owned execution and BA-owned recipe execution.

```text
RAPT profile runner
  -> owns local profile step/timer progression

BrewAssistant
  -> interprets current RAPT process/target intent
  -> owns BrewZilla target/heat/pump policy
  -> keeps ABORT and safety authority
```

RAPT profiles already model target-driven progression and timed holds more directly than Brew Tracker, so they do not require the Brewfather 0-minute PAUS workaround.

---

## Ownership matrix

| Execution model | Recipe/profile source | Runtime/timer owner | Step progression | Physical BrewZilla policy |
| --- | --- | --- | --- | --- |
| Brewfather/BrewTracker supervised | Brewfather | Brew Tracker | Brewfather + operator checkpoints | BrewAssistant |
| BrewAssistant recipe runtime | Brewfather | BrewAssistant | BrewAssistant | BrewAssistant |
| RAPT profile runtime | RAPT profile | RAPT profile runner | RAPT/manual profile checkpoints | BrewAssistant |
| Manual Brewday | BrewAssistant/manual plan | BrewAssistant | Operator/BA manual runtime | BrewAssistant |

All models remain below Brewday operator ABORT and hardware safety.

---

## Source selection vs execution ownership

Do not overload the word `Auto`.

The current RAPT-profile work has discussed a source selector such as:

```text
Auto / RAPT / Brewfather / Manual
```

Here `Auto` means automatic source arbitration. The future BrewAssistant-owned recipe runtime described above is a different concept: BA itself owns the imported-recipe timeline.

Before exposing the recipe-owned mode in UI, choose names that make these concepts unambiguous. Possible internal terminology:

```text
source selection: auto-select / rapt / brewfather / manual
execution owner: external tracker / external profile / ba_recipe / manual
```

No UI naming is locked by this document.

---

## Immediate implementation / validation sequence

```text
[ ] Fix paused-target hold: paused BrewTracker must never pre-actuate next_step target.
[ ] Add regression coverage for current-target latch across 0-minute PAUS.
[ ] Re-run the water profile and verify device target remains at the paused checkpoint target.
[ ] Verify stage/progress/time remain frozen for a longer pause.
[ ] Add target-ready operator notification suitable for "Resume Brewfather".
[ ] Verify Resume changes source state before BA accepts the following target.
[ ] Keep physical timing ledger independent enough to measure actual ramp/hold behavior around the checkpoint.
[ ] Define Brewfather recipe -> Python Brewday plan adapter for BA-owned execution.
[ ] Reuse/generalize Manual Brewday persistence/runtime primitives where practical.
[ ] Define restart recovery and step identity for BA-owned imported-recipe execution.
[ ] Decide UI terminology without colliding with automatic source selection.
```

The 0-minute checkpoint is therefore a useful Brewfather/BrewTracker operating mode, not the long-term mechanism required by fully automated BrewAssistant execution.
