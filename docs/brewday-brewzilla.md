# Brewday / BrewZilla Direct Flow

This document describes the current BrewAssistant hot-side control path from Brewfather Brew Tracker or Manual Brewday through BrewAssistant to BrewZilla/RAPT hardware.

Status: **supervised hot-side beta baseline synced after the 2026-09-06 field runs**.

Latest evidence:

- [`physical-validation-2026-08-31.md`](physical-validation-2026-08-31.md)
- [`physical-validation-2026-09-05.md`](physical-validation-2026-09-05.md)
- [`physical-validation-2026-09-06.md`](physical-validation-2026-09-06.md)

---

## Control philosophy

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

Safety ordering:

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

Ownership begins only after positive tracker-start evidence. A later legitimate pause retains ownership for the same started tracker/batch.

`active: true` alone is not start evidence.

---

## Manual Brew ownership

Manual Brew and Brewfather are mutually exclusive runtime owners.

Manual Brew can split hardware ownership by channel:

```text
Manual Target Override ON
  -> operator owns target

Allow Heater Control OFF
  -> operator owns heater + heat utilization

Allow Pump Control OFF
  -> operator owns pump + pump utilization
```

ABORT and hard safety outrank Manual ownership.

---

## Dedicated Heatstrike / Mash-In phase authority

`Brewfather Play` authorizes the dedicated Heatstrike/Mash-In physical controller. While this controller owns the phase, BrewAssistant may modulate target, heat and pump inside the bounded phase contract without creating a new generic confirmation for every small adjustment.

Outside this phase, positive automatic control continues through generic Supervised Apply where applicable.

---

## Target concepts

```text
sensor.brewassistant_brewzilla_runtime_target_temperature
  = Brewday runtime intent

sensor.brewassistant_brewzilla_target_temperature
  = normalized/effective BA target

sensor.brewassistant_brewzilla_device_target_temperature
  = physical/raw BrewZilla/RAPT target
```

Flight Recorder keeps effective and device target separate.

`target_delta` means requested target minus applied target, not process-temperature error.

---

## Temperature roles

```text
MASH / external process probe
  = readiness and process authority during Heatstrike/Mash

BrewZilla internal / WORT
  = kettle context, limiter and safety view
```

The internal sensor must not silently replace the owned external process probe as target-reached authority.

---

## Heatstrike target and local regulation

BrewAssistant uses the real strike target. It does not artificially boost the physical BrewZilla target to compensate for expected losses.

BrewZilla local temperature regulation remains available while BrewAssistant limits heat authority.

### Gradient relief — PR #197 + 2026-09-06 refinement

Physical evidence:

```text
strike target        71.8 °C
MASH/BLE              69.1 °C
BrewZilla internal    73.36 °C
internal overshoot    +1.56 °C
```

Current narrow exception:

```text
MASH/BLE is still below strike
AND mash/wort gradient >= 1.5 °C
AND hottest-view overshoot > +0.5 °C
AND hottest-view overshoot <= +2.0 °C

=> heat authority cap = 5 %
=> heater master remains available
=> pump utilization = 100 %
```

Above +2.0 °C hottest-view overshoot, explicit heat 0 / heater OFF remains authoritative.

This does not widen Mash-In READY.

---

## Mash-In readiness

Automatic Mash-In READY requires fresh canonical external process temperature within the readiness band.

A stale locked process value may remain visible diagnostically but must not create automatic READY.

A bounded operator strike-acceptance path exists for a physically verified plausible near-strike state. That acknowledgement only latches readiness; it does not itself change target, heater, pump or utilization.

---

## Mash-In physical state machine

```text
ready_for_mash_in
  -> Mash-In Started
  -> target releases toward actual mash target
  -> pump OFF
  -> pump utilization 0 %
  -> grain addition / stirring
  -> BA observes Brewfather PAUSED after Mash-In Started
  -> later Brewfather RUNNING / Continue
  -> Mash-In Complete
  -> normal mash circulation resumes
```

A stale or late event must never move completed Mash-In backwards.

### Strict Brewfather completion evidence

Automatic completion requires:

```text
Mash-In Started boundary
  -> BF PAUSED observed after that boundary
  -> later BF RUNNING
  -> Mash-In Complete
```

If the exact adjacent `paused -> running` sample is missed, a later `running` may be accepted only when BA has already recorded the post-start paused state for the same gate.

Not sufficient by themselves:

```text
BF already running when Mash-In Started is pressed
active Brewfather mash target changing
BA normalized runtime remaining live/running
```

Until completion:

```text
mash_in_gate_state = mash_in_started
pump OFF
pump utilization 0 %
```

The explicit manual Mash-In Complete path remains fallback if the BF transition cannot be observed.

### 2026-09-06 second-run result

Flight Recorder confirms that the backend did complete the handoff correctly:

```text
Mash-In Started
-> post-start BF PAUSED observed
-> BF RUNNING observed
-> mash_in_complete
-> target 66.0 °C
-> pump utilization 50 %
-> pump ON
```

The operator ABORT followed roughly 25 seconds later. The remaining defect from that observation is presentation: completion was not visually obvious enough.

---

## Physical mash hold / ramp timing (#157)

The timing layer is read-only and must not participate in hardware control.

```text
Ramp
  -> begins when physical ramp is observed
  -> completes when selected process temperature reaches target band

Mash hold
  -> does not start merely because Brewfather entered the source step
  -> starts when selected process temperature reaches ±0.3 °C target band
  -> first hold also waits for Mash-In Complete

PAUSE
  -> freezes physical process elapsed time

ABORT
  -> stops timing without issuing hardware commands
```

The timing history records duration, wall time, pause time, ΔT, °C/min, source, context and heat/pump utilization evidence.

---

## RCL report freshness and active refresh

The 2026-09-06 second run exposed that BrewAssistant had mixed two clocks:

```text
report freshness
  = when HA last received/reported the entity

value age
  = when state/attributes last actually changed
```

A stable target or temperature could therefore appear falsely stale. One value-stagnation guard also replaced canonical process-temperature freshness, allowing fail-passive after 90 seconds simply because the value had not changed enough.

Current contract:

```text
control/report freshness
  -> last_reported, fallback last_updated

value stagnation
  -> last_updated + explicit change tracking
  -> diagnostics only

active hot-side refresh
  -> every 30 seconds
  -> one BrewZilla CoordinatorEntity
  -> homeassistant.update_entity
  -> DataUpdateCoordinator.async_request_refresh()
```

Only one trigger entity is used because multiple entities may share the same coordinator.

Hard `reload_config_entry` remains separate, reserved for hard connection loss/extreme report staleness and throttled to a 15-minute minimum interval.

This means a stable temperature is not stale merely because it is stable. Fail-passive should react to missing report traffic, not lack of numeric movement.

---

## Fail-passive telemetry loss

Ordinary genuine report degradation:

```text
no new BA writes
preserve valid local target/output state
request/indicate telemetry recovery
```

Telemetry recovery is not permission to rewrite target/heat/pump.

---

## Supervised Apply outside dedicated phase authority

Generic positive actions outside the dedicated Heatstrike/Mash-In controller remain supervised where applicable:

```text
target increase
heat-utilization increase
pump-utilization increase
heater ON
pump ON
```

Flow:

```text
orchestration builds pending plan
  -> operator CONFIRM ACTION
  -> BA rebuilds/validates live plan
  -> only still-valid matching plan executes
  -> Flight Recorder records confirmation/execution
```

`REJECT ACTION` rejects one pending intention. It is not emergency ABORT.

---

## Brewday operator ABORT

`ABORT BREWDAY` performs physical safe-down and adds a persistent Brewday ownership latch:

```text
heater OFF
pump OFF
heat utilization 0
pump utilization 0
clear pending positive intent
persistent Brewday ownership state = aborted
```

`REARM CONTROL` releases only the Brewday ownership latch and does not bypass BrewZilla's separate hardware ABORT lockout.

---

## External process-sensor ownership

```text
Heat strike -> Mash -> Mash out -> Sparge -> Pre-boil
  owner = Brewday/BrewZilla hot-side

Boil
  hot-side releases external process sensor

Chill -> Transfer
  Cooling/CFC acquires it when the configured method requires it
```

BrewZilla internal remains kettle context throughout.

---

## Next physical checkpoint

```text
active hot-side run
-> confirm 30 s RCL coordinator refresh and bounded report age
-> Heatstrike final approach
-> READY
-> Mash-In Started
-> pump OFF / 0 %
-> post-start BF PAUSED
-> BF Continue / RUNNING
-> Mash-In Complete
-> target = actual mash target
-> normal mash circulation
-> continue into real 66 °C hold / 66 -> 72 °C ramp when practical
```

Use Flight Recorder evidence rather than UI appearance alone when deciding whether backend state actually transitioned.
