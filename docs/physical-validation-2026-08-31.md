# Physical Validation — 2026-08-31

This note records the supervised Brewday/BrewZilla water-test findings and the resulting backend/UI contracts merged on 2026-08-31.

Status: **current physical-test evidence for the Heatstrike final approach and Mash-In readiness path**.

---

## Scope

The test focused on the Brewfather-owned Brewday Runtime path around:

```text
Heatstrike
  -> final approach to strike temperature
  -> Mash-In readiness
  -> operator handoff into Mash-In
```

The run used the current supervised-control architecture: BrewAssistant interprets runtime and process state, BrewZilla regulates locally against its written target, and positive physical actions remain operator-supervised.

---

## Finding 1 — Heatstrike final-approach dead zone

A deterministic dead zone was reproduced with approximately:

```text
strike target       71.8 °C
MASH/process probe   69.6 °C
WORT/internal        71.5 °C
```

The external process probe was still about 2.2 °C below strike while the internal safety view was already close to target. The previous logic allowed the safety layer to cap requested heat to 0%, which disabled the BrewZilla heater master even though the process probe still needed energy to reach strike temperature.

The result was safe but stalled.

### Contract after PR #193

Heatstrike final approach now keeps BrewZilla local regulation active instead of using an ordinary 0% coast near target.

```text
process final approach <= 3 °C below target
  -> retain positive local-regulation authority

very small internal/safety headroom
  -> reduce authority with bounded utilization
  -> do not disable the heater master merely because internal temperature is near target

true hottest-view overshoot > target + 0.5 °C
  -> explicit BA heat 0 / heater OFF is allowed

ABORT / hard safety
  -> remains authoritative
```

The implemented final-approach profile uses positive bounded utilization near target, including 25% and 50% authority bands, while preserving the MASH/process probe as readiness authority and the internal/WORT view as the safety limiter.

This preserves the hybrid design:

```text
fresh telemetry
  -> BA optimizes heat/pump behavior

valid BrewZilla target
  -> BrewZilla local thermostat remains active

telemetry degradation
  -> local BrewZilla regulation remains the fallback
```

---

## Finding 2 — RAPT Cloud process temperature can become stale near Mash-In

During the water test, the canonical MASH/process temperature from RAPT Cloud stopped updating for several minutes while BrewZilla still had a valid local target and continued regulating locally.

A stale locked process value must not silently become automatic proof that Mash-In is ready.

### Contract after PR #194

Automatic Mash-In READY now requires a **fresh canonical external MASH/process temperature** and uses a widened physical readiness band of:

```text
strike target ±1.0 °C
```

A stale process value is retained only for diagnostics, including its age. It is never accepted as automatic READY evidence.

A bounded operator strike-acceptance path is available up to:

```text
strike target ±2.0 °C
```

The operator path exists for a physically plausible near-strike condition when cloud telemetry is stale or lagging. It does not change target, heater, pump or utilization by itself; it only latches `ready_for_mash_in`.

RAPT Cloud stale-data fallback is allowed only when BrewZilla's local target and internal/WORT temperature independently show that the vessel is physically near strike. This is a bounded fallback, not a replacement process-temperature source.

Safety invariant:

```text
fresh external process temperature
  -> may create automatic READY within ±1.0 °C

stale external process temperature
  -> diagnostics only
  -> never automatic READY

bounded operator acceptance
  -> allowed only within the defined near-strike envelope
  -> latches readiness only
  -> does not energize or retarget hardware
```

---

## Mash-In UI / ownership contract

Mash-In and physical process timing are Brewday Runtime process concerns rather than a separate BrewZilla hardware cockpit.

The consolidated runtime flow therefore keeps:

```text
main Brewday Runtime card
  -> generic runtime / pending / ABORT controls

physical timing companion
  -> current physical ramp/hold timing + history

Mash-In process controls
  -> shown only during ready_for_mash_in / mash_in_started
  -> Mash-In Started is the primary operator handoff
  -> Brewfather Continue is the primary completion path
  -> manual Complete remains a fallback
```

No duplicate direct heater/pump controls belong in this Mash-In process section.

---

## Current verified architecture after the test

```text
Brewfather Brew Tracker / Manual Brewday
        ↓
normalized Brewday Runtime
        ↓
Heatstrike / Mash-In process interpretation
        ↓
BrewZilla local-regulation + safety guards
        ↓
Supervised Apply for positive physical actions
        ↓
BrewZilla hardware
```

The external process sensor remains phase-owned:

```text
Heat strike -> Mash -> Mash out -> Sparge -> Pre-boil
  owner = Brewday Runtime

Boil starts
  Brewday Runtime releases it

Chill -> Transfer
  owner = Cooling/CFC backend
  role = outlet / wort-out temperature
```

The Boil -> Chill ownership handoff is still awaiting physical validation.

---

## Next physical validation

The immediate hot-side validation target is no longer the pre-#193 final-coast behavior. The next useful supervised test should verify the merged final-approach/readiness contracts in one continuous run:

```text
[ ] Heatstrike closes the final few degrees without the previous dead zone
[ ] BrewZilla local regulation remains active through final approach / READY
[ ] automatic Mash-In READY occurs only from fresh process telemetry within ±1.0 °C
[ ] stale process telemetry remains diagnostic-only
[ ] bounded operator strike acceptance behaves correctly when needed
[ ] Mash-In Started produces pump OFF / pump utilization 0 before grain addition
[ ] Brewfather Continue completes Mash-In and circulation resumes correctly
[ ] physical mash hold starts only when the real process temperature reaches its target band
```

After a clean water regression, proceed to the first supervised real-mash validation and then continue toward Boil and the external-sensor handoff into Cooling/Chill.
