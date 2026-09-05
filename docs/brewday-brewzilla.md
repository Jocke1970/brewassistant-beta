# Brewday / BrewZilla Direct Flow

This document describes the current BrewAssistant hot-side control path from Brewfather Brew Tracker or Manual Brewday through BrewAssistant to BrewZilla/RAPT hardware.

Status: **supervised hot-side beta baseline synced after the 2026-09-05 Heatstrike/Mash-In field test**.

Latest physical evidence:

- [`physical-validation-2026-08-31.md`](physical-validation-2026-08-31.md)
- [`physical-validation-2026-09-05.md`](physical-validation-2026-09-05.md)

---

## Control philosophy

BrewAssistant separates runtime understanding from hardware authority.

```text
Brewfather Brew Tracker or Manual Brewday
        ↓
normalized Brewday Runtime
        ↓
BrewZilla orchestration + phase/safety guards
        ↓
physical target / heat / pump plan
        ↓
BrewZilla / RAPT hardware
        ↓
Flight Recorder + diagnostics + passive learning evidence
```

Safety ordering is authoritative:

```text
operator ABORT / hardware ABORT / hard safety
        > source ownership
        > dedicated phase authority
        > generic supervised positive control
        > local-regulation preservation
        > advice / learning / presentation
```

Risk-reducing safe-down actions do not wait for confirmation.

---

## Brewfather phase is not Brew Tracker start

A Brewfather batch may be in phase `Brewing` before Brew Tracker has actually started.

Typical pre-start evidence:

```text
batch phase: Brewing
tracker: paused
stage 0 / step 0
progress 0
remaining == duration
current step = Start / Starta mäsktimer
```

This is visible/ready but does not own BrewZilla hot-side control.

Ownership rules:

```text
Planning
  -> visible / ready
  -> no hot-side ownership

Brewing pre-start
  -> visible / ready
  -> no hot-side ownership

positive tracker-start evidence
  -> Brewfather owns normalized Brewday Runtime

later legitimate pause
  -> ownership stays latched to the same tracker/batch

Fermenting / completed / unrelated phase
  -> no BrewZilla hot-side ownership
```

`active: true` alone is not start evidence.

---

## Manual Brew ownership

Manual Brew and Brewfather are mutually exclusive runtime owners.

Manual Brew can also split hardware ownership by channel:

```text
Manual Target Override ON
  -> operator owns target

Allow Heater Control OFF
  -> operator owns heater + heat utilization

Allow Pump Control OFF
  -> operator owns pump + pump utilization
```

ABORT and hard safety always outrank Manual ownership.

---

## Dedicated Heatstrike / Mash-In phase authority

Current pre-mash control is deliberately not generic per-modulation confirmation.

`Brewfather Play` is treated as the operator authorization for the dedicated Heatstrike/Mash-In physical controller. While this controller owns the phase, BrewAssistant may modulate target, heat and pump inside the bounded phase contract without creating a fresh generic confirmation for every small internal adjustment.

Outside dedicated phase authority, positive automatic control continues through the generic Supervised Apply path where applicable.

This distinction prevents the operator from having to confirm every 25% -> 15% -> 25% Heatstrike adjustment while still keeping unrelated positive automation supervised.

---

## Target concepts

Do not conflate runtime intent with the physical RAPT target.

```text
sensor.brewassistant_brewzilla_runtime_target_temperature
  = Brewday runtime target

sensor.brewassistant_brewzilla_target_temperature
  = normalized/effective BA target

sensor.brewassistant_brewzilla_device_target_temperature
  = physical/raw BrewZilla/RAPT target
```

Flight Recorder keeps effective and device target separate.

`target_delta` means synchronization delta:

```text
requested_target - applied_target
```

not process temperature error.

---

## Temperature roles

The hot-side model uses two different physical views:

```text
MASH / external process probe
  = readiness and process authority during Heatstrike/Mash

BrewZilla internal / WORT
  = kettle context, limiter and safety view
```

The internal sensor must not silently replace the owned external process probe as target-reached authority while that external sensor is intentionally owned by hot-side control.

---

## Heatstrike target and local regulation

BrewAssistant uses the real strike target. It does not artificially boost the physical BrewZilla target to compensate for expected losses.

BrewZilla local temperature regulation should remain available while BrewAssistant limits the amount of heat authority.

The 2026-08-31 water test exposed a final-approach dead zone and drove PR #193: the heater master must not be disabled merely because the internal/WORT view is near target while the external process probe still needs energy.

---

## Heatstrike gradient relief — PR #197

The 2026-09-05 test reproduced a stronger temperature-gradient deadlock:

```text
strike target       ~71.8 °C
MASH/BLE             ~67.8 °C
BrewZilla internal   ~72.7 °C
```

The readiness probe still required energy, but the ordinary hottest-view overshoot rule could simultaneously request heat 0 / heater OFF.

Current rule:

```text
normal hottest-view overshoot > target +0.5 °C
  -> safe-down remains the default
```

Narrow pre-mash-in exception:

```text
MASH/BLE is still below strike
AND a real process/internal gradient exists
AND hottest-view overshoot > +0.5 °C
AND hottest-view overshoot <= +1.5 °C

=> heat authority cap = 15%
=> heater master remains available to local thermostat
=> pump utilization = 100% for equalization
```

Hard boundary:

```text
hottest-view overshoot > +1.5 °C
  -> explicit heat 0 / heater OFF remains authoritative
```

The gradient exception is not a general relaxation of overshoot safety. It only prevents the observed BLE-low/internal-high deadlock during pre-mash-in equalization.

---

## Mash-In readiness

Automatic Mash-In READY requires fresh canonical external process temperature within the readiness band.

Current automatic contract:

```text
fresh MASH/process temperature
within strike target ±1.0 °C
```

A stale locked process value may remain visible for diagnostics but must not create automatic READY.

A bounded operator strike-acceptance path exists up to:

```text
strike target ±2.0 °C
```

when the operator has physically verified a plausible near-strike condition and BrewZilla local/internal context independently supports it.

This operator action only latches readiness. It does not itself change target, heater, pump or utilization.

---

## Mash-In physical state machine

Mash-In is a one-way physical handoff:

```text
ready_for_mash_in
  -> Mash-In Started
  -> target releases toward actual mash target
  -> pump OFF
  -> pump utilization 0%
  -> grain addition / stirring window
  -> observe Brewfather PAUSED after Mash-In Started
  -> later Brewfather RUNNING / Continue
  -> Mash-In Complete
  -> normal mash circulation resumes
```

A stale or late `Mash-In Started` action must never move a completed Mash-In backwards.

---

## Brewfather progression after Mash-In — PR #202 follow-up

The 2026-09-05 accelerated test exposed an edge case in the first progression guard: if Brewfather was already in `running`/Play while Mash-In Started was pressed, an already-advanced mash target could make BA complete the handoff immediately.

The completion contract is therefore intentionally edge-triggered and uses the live Brewfather Brew Tracker status sensor:

```text
Mash-In Started
  -> BA must observe BF status = paused after that boundary
  -> later BF status = running
  -> Mash-In Complete may auto-complete
```

If polling misses the exact adjacent `paused -> running` sample, a later `running` is accepted only when BA has already recorded a post-start paused state for the same Mash-In gate.

The following are **not** completion evidence by themselves:

```text
BF was already running when Mash-In Started was pressed
active Brewfather mash target changed
BA normalized runtime remained live/running
```

Until a post-start pause and subsequent resume have been observed:

```text
mash_in_gate_state = mash_in_started
pump OFF
pump utilization 0%
```

Only after completion may normal mash circulation restart. The explicit Mash-In Complete/manual circulation path remains the fallback if the Brewfather transition cannot be observed reliably.

---

## Mash-In status UI

The yellow Mash-In waiting/status box must reflect live gate/orchestration state rather than stale button attributes.

Expected visibility:

```text
ready_for_mash_in / mash_in_started
  -> visible

mash_in_complete
  -> hidden
```

PR #202 updates EN/SV runtime-flow cards to prefer live state.

---

## Physical mash hold / ramp timing (#157)

The timing layer is read-only and must not participate in hardware control.

Rules:

```text
Ramp
  -> begins when physical ramp is observed
  -> completes when selected process temperature reaches target band

Mash hold
  -> does not start merely because Brewfather entered the source step
  -> starts when selected process temperature reaches ±0.3 °C target band
  -> first hold also waits for Mash-In Complete when the gate exists

PAUSE
  -> freezes physical process elapsed time

ABORT
  -> stops timing without issuing hardware commands
```

The timing history records duration, wall time, pause time, ΔT, °C/min, source, learning context and heat/pump utilization context.

Current limitation: first field implementation remains volatile across Home Assistant restart.

---

## Supervised Apply outside dedicated phase authority

Generic automatic positive actions outside the dedicated Heatstrike/Mash-In controller still use Supervised Apply where applicable.

Examples:

```text
target increase
heat-utilization increase
pump-utilization increase
heater ON
pump ON
```

Expected flow:

```text
orchestration builds pending plan
  -> operator CONFIRM ACTION
  -> BA rebuilds and validates live plan
  -> only still-valid matching plan executes
  -> Flight Recorder records confirmation/execution
```

`REJECT ACTION` rejects one pending intention. It is not an emergency ABORT.

---

## RCL readback grace and fail-passive recovery

RAPT Cloud Link may briefly replay an old value after a successful write.

BrewAssistant keeps a bounded confirmed-write grace so an old target/utilization readback does not immediately recreate the same positive request.

Important limits:

```text
- grace is bounded
- same runtime intention/context only
- heater/pump are not silently re-energized
- persistent mismatch requires a new decision
- ABORT invalidates grace
```

Ordinary telemetry degradation is fail-passive:

```text
no new BA writes
preserve valid local target/output state
request/indicate telemetry recovery
```

Telemetry recovery itself is not permission to rewrite target/heat/pump.

---

## Brewday operator ABORT

`ABORT BREWDAY` is distinct from rejecting one pending action.

Expected safe-down:

```text
heater OFF
pump OFF
heat utilization 0
pump utilization 0
clear pending positive intent
persistent Brewday ownership latch = aborted
```

While latched, Brewfather cannot automatically reclaim BA hot-side ownership even if its external tracker continues running.

`REARM CONTROL` releases only the Brewday ownership latch. It does not bypass BrewZilla's separate hardware ABORT lockout.

The operator ABORT latch survives Home Assistant restart.

---
