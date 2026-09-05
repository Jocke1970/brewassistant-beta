# Roadmap

This document tracks the current BrewAssistant beta roadmap.

BrewAssistant keeps runtime state, process interpretation, safety guards and hardware decisions in the Python custom integration under `custom_components/brewassistant/`.

```text
Python integration = runtime + ownership + logic + safety + hardware decisions
Dashboard YAML      = presentation + explicit operator actions
```

---

## Current project phase

The current hot-side baseline includes the 2026-08-29 ownership/ABORT validation, the 2026-08-31 Heatstrike/Mash-In regression work, and the 2026-09-05 Heatstrike gradient/Mash-In handoff fixes.

Current sequence:

```text
beta.9 candidate / supervised Heatstrike + Mash-In validation
↓
continuous physical regression of PR #197 + PR #202
↓
first supervised real-mash 66 °C hold + 66 -> 72 °C ramp validation
↓
Mash out / Sparge / Pre-boil validation
↓
Boil ramp / Boil + external process-sensor ownership release
↓
Cooling/CFC Chill / Transfer ownership handoff validation
↓
BrewZilla Equipment Learning timing/profile evidence pass
↓
RAPT Cloud Link profile-orchestration investigation
↓
Climate Supervisor full-cycle validation
↓
Carbonation runtime validation
↓
Fermentation cockpit/runtime validation
↓
remaining YAML/business-logic retirement and release hardening
```

Latest physical evidence:

- [`physical-validation-2026-08-31.md`](physical-validation-2026-08-31.md)
- [`physical-validation-2026-09-05.md`](physical-validation-2026-09-05.md)

The 2026-09-05 run confirmed that Heatstrike/Mash-In progressed farther but exposed two deterministic edge cases now covered by PR #197 and PR #202:

```text
1. Heatstrike gradient deadlock
   external MASH/BLE still below strike
   internal BrewZilla view already above strike
   -> narrow gradient-relief mode
   -> heat cap 15%
   -> pump 100% for equalization
   -> > +1.5 °C hottest-view overshoot remains hard stop

2. Mash-In handoff / early circulation restart
   plain Brewfather running state was too weak as completion evidence
   -> Mash-In Started owns pump OFF / 0%
   -> completion waits for real BF progression
   -> paused -> running OR BF mash target leaving strike target
```

---

## Repository / release workflow

Only three long-lived branches are allowed:

```text
dev  = ongoing development
beta = integrated field-test candidate
main = installable/runnable version
```

Promotion path:

```text
dev -> beta -> main -> GitHub Release
```

Rules:

- normal project work happens on `dev`;
- `dev -> beta` and `beta -> main` use pull requests;
- promotion PRs use **Create a merge commit**, not squash/rebase;
- GitHub **Automatically delete head branches** stays disabled because `dev` and `beta` are permanent;
- Dependabot targets `dev`;
- CI, HACS and Hassfest run on `dev`, `beta` and `main`;
- releases are created only from `main`;
- beta releases are GitHub prereleases such as `v0.2.0-beta.9`.

See [`../CONTRIBUTING.md`](../CONTRIBUTING.md).

---

## Brewday Runtime / ownership status

Completed:

```text
[x] Custom integration + config flow + coordinator
[x] Normalized Brewday Runtime
[x] Brewfather RAW Brew Tracker timeline resolver
[x] Planning / Brewing pre-start visible without hot-side ownership
[x] Brewfather ownership begins only after positive tracker-start evidence
[x] Started Brewfather tracker retains ownership through legitimate pause
[x] Manual/Brewfather mutual exclusion and safe handoff
[x] Brewday Stage Engine v2
[x] Persistent Brewday Event Log / Flight Recorder
[x] One Brewfather batch keeps one Flight Recorder session through Planning -> pre-start -> Play
[x] Physical/effective target diagnostics separated
[x] Brewday operator ABORT + persistent ownership latch
[x] Explicit Brewday rearm
[x] Read-only Brewsteps process view
[x] Read-only physical ramp/hold timing layer (#157)
[x] Mash-In + timing presented in the Brewday Runtime flow
```

Operator safety remains:

```text
CONFIRM ACTION
  -> execute a still-valid pending positive plan

REJECT ACTION
  -> reject one pending positive intention

ABORT BREWDAY
  -> physical safe-down
  -> clear pending positive intent
  -> persistent Brewday ownership lock

REARM CONTROL
  -> release Brewday ownership lock only
  -> never bypass BrewZilla hardware ABORT lockout
```

---

## BrewZilla hot-side status

Implemented:

```text
[x] Normalized BrewZilla runtime sensors
[x] Runtime/effective/device target separation
[x] Heat/pump utilization and switch control surface
[x] Dedicated Heatstrike/Mash-In phase authority
[x] Real strike-target latch
[x] External MASH/process probe as readiness authority
[x] BrewZilla internal/WORT as limiter/safety view
[x] Heatstrike final-approach local-regulation preservation (#193)
[x] Fresh-only automatic Mash-In READY (#194)
[x] Bounded operator strike acceptance (#194)
[x] Heatstrike gradient-relief mode (#197)
[x] +1.5 °C gradient hard-stop boundary (#197)
[x] Mash-In Started target release
[x] Mash-In Started pump OFF / 0% ownership window (#202)
[x] Brewfather progression-based Mash-In Complete (#202)
[x] Plain BF running state forbidden as completion evidence (#202)
[x] Live Mash-In UI state preferred over stale button attributes (#202)
[x] RCL recovery / local-regulation preservation
[x] Fail-passive ordinary telemetry loss
[x] Hardware ABORT + positive-action lockout
[x] Manual channel ownership
[x] Generic Supervised Apply outside dedicated phase authority
[x] Confirmed readback grace
[x] BrewZilla live heat/pump visualization
[x] BrewZilla thermal-state gauge background
```

### Current Heatstrike contract

Normal hottest-view overshoot above approximately target +0.5 °C remains a safe-down trigger by default.

A narrow exception exists only during the physically observed pre-mash-in gradient state:

```text
MASH/BLE still below strike
AND hottest-view overshoot > +0.5 °C
AND hottest-view overshoot <= +1.5 °C

=> heat authority cap 15%
=> heater master remains available to BrewZilla local thermostat
=> pump 100% for temperature equalization
```

If hottest-view overshoot exceeds +1.5 °C, explicit hard stop remains authoritative even when a gradient exists.

### Current Mash-In contract

```text
ready_for_mash_in
  -> Mash-In Started
  -> target releases toward mash target
  -> pump OFF / utilization 0%
  -> operator adds/stirs grain
  -> wait for real Brewfather progression
  -> Mash-In Complete
  -> normal mash circulation resumes
```

Valid automatic completion evidence:

```text
paused -> running
OR
active Brewfather mash target moves away from captured strike target
```

A plain `running` state alone is not completion evidence.

---

## Physical validation still required

Immediate checks:

```text
[ ] Heatstrike gradient relief converges MASH/BLE toward strike without unsafe internal overshoot
[ ] > +1.5 °C hottest-view overshoot still produces intended hard stop
[ ] Mash-In Started visibly holds pump OFF / 0% for the entire grain-addition window
[ ] Brewfather Continue/progression is the first event that permits circulation restart
[ ] Mash-In waiting/status box disappears immediately after confirmed completion
[ ] Physical #157 66 °C hold starts only on actual target reach
[ ] #157 PAUSE freezes timer
[ ] #157 66 -> 72 °C ramp is recorded separately and starts next hold only on target reach
[ ] Brewsteps follows BrewTracker-owned physical process phase correctly
[ ] First supervised real-mash heat-strike / mash-in temperature-drop behavior
[ ] Real-mash 66 °C hold + 66 -> 72 °C ramp
[ ] Full boil ramp / boil
```

---

## External process-temperature sensor ownership

Architecture decision is fixed:

```text
Heat strike -> Mash -> Mash out -> Sparge -> Pre-boil
  owner = Brewday / BrewZilla hot-side
  role  = external process/mash temperature

Boil starts
  hot-side releases external sensor ownership

Chill -> Transfer
  owner = Cooling/CFC when method requires it
  role  = CFC outlet / wort-out temperature
```

BrewZilla internal temperature remains the primary kettle temperature throughout the hot-side path.

Validation still required:

```text
[ ] release exactly at Boil start
[ ] no competing Brewday/Cooling interpretation during Boil
[ ] Cooling/CFC acquisition during Chill
[ ] continued wort-out use during Transfer
[ ] traditional immersion-coil/manual-temperature path without unnecessary external-sensor dependency
```

---

## Physical timing / Equipment Learning

The #157 physical timing layer remains read-only and must not influence live control.

Implemented evidence fields include:

```text
ramp/hold duration
wall duration
pause duration
ΔT
average °C/min
process-temperature source
water-only vs real-mash context
heat/pump utilization start/end
```

Next Equipment Learning work should use validated physical timing rather than source-schedule timing alone.

Planned later work:

```text
[ ] heat-strike timing suggestion
[ ] mash-ramp timing suggestion
[ ] mash-out timing suggestion
[ ] boil-ramp timing suggestion
[ ] confidence model by observation count/context/source quality
[ ] operator-reviewed learned profile candidates
[ ] persistent approved overrides
[ ] reversible disable/revert/reset
[ ] water-only evidence can never silently activate real-mash override
```

Learning remains advisory until explicitly approved.

---

## Cooling / Chill / Transfer

Cooling Runtime v2 supports CFC and traditional immersion-coil/manual-water workflows.

Next validation:

```text
[ ] Boil -> Chill ownership handoff
[ ] CFC outlet temperature acquisition
[ ] CFC sanitation path
[ ] immersion-coil sanitation path
[ ] traditional coil using BrewZilla internal/manual temperature
[ ] manual cooling-water flow
[ ] pump-assisted cooling-water flow where configured
[ ] Chill target / pitch-ready behavior
[ ] Transfer completion behavior
```

---

## Other active backends

Already present in Python Core:

```text
[x] Cooling Runtime v2
[x] Counterflow Wort Cooling backend/cockpit
[x] Carbonation Runtime/session + persistence
[x] Climate Supervisor
[x] Kegerator fan/guard logic
[x] Fermentation Tracking / cockpit foundation
[x] EN canonical + SV presentation mirror policy
```

These remain secondary to completing deterministic hot-side and cooling ownership validation.

---

## Beta.9 release path

Current candidate release notes:

[`beta9-release-notes.md`](beta9-release-notes.md)

Required before release:

```text
1. keep `dev` green under CI + HACS + Hassfest
2. promote `dev -> beta` with Create a merge commit
3. run intended physical beta validation
4. fix regressions on `dev`, then promote again if needed
5. promote validated `beta -> main` with Create a merge commit
6. create GitHub prerelease v0.2.0-beta.9 from the resulting main commit
```
