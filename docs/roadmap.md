# Roadmap

This document tracks the current BrewAssistant beta roadmap.

BrewAssistant keeps runtime state, process interpretation, safety guards and hardware decisions in the Python custom integration under `custom_components/brewassistant/`.

```text
Python integration = runtime + ownership + logic + safety + hardware decisions
Dashboard layer     = presentation + explicit operator actions
```

The dashboard is still primarily YAML, with a BrewAssistant-specific JavaScript/SVG card pilot now being evaluated for complex instruments.

---

## Current project phase

The current hot-side baseline includes the 2026-08-29 ownership/ABORT validation, the 2026-08-31 Heatstrike/Mash-In regression work, the 2026-09-05 gradient/handoff fixes and both 2026-09-06 physical runs.

Current sequence:

```text
beta.9 candidate / supervised Heatstrike + Mash-In validation
↓
validate 30 s active RCL coordinator refresh + report-freshness semantics
↓
repeat full Heatstrike -> READY -> Mash-In handoff
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
Climate Supervisor / Carbonation / Fermentation full-cycle validation
↓
remaining dashboard/business-logic retirement and release hardening
```

Latest physical evidence:

- [`physical-validation-2026-08-31.md`](physical-validation-2026-08-31.md)
- [`physical-validation-2026-09-05.md`](physical-validation-2026-09-05.md)
- [`physical-validation-2026-09-06.md`](physical-validation-2026-09-06.md)
- [`parking-checkpoint-2026-09-06.md`](parking-checkpoint-2026-09-06.md)

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
- beta releases are prereleases such as `v0.2.0-beta.9`.

Current parking note: HACS and Hassfest are green for the RCL patch, and the RCL regression tests pass. General CI remains blocked by older EN/SV cockpit content-parity drift. The JS gauge filename pair is fixed by the parking sync; the remaining cockpit parity must be resolved deliberately before promotion.

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
[x] +2.0 °C gradient hard-stop boundary with 5 % relief cap
[x] Mash-In Started target release
[x] Mash-In Started pump OFF / 0 % ownership window (#202)
[x] Strict post-start BF PAUSED -> RUNNING automatic Mash-In completion
[x] Plain BF running and target movement forbidden as standalone completion evidence
[x] Live Mash-In UI state preferred over stale button attributes
[x] Fail-passive ordinary telemetry loss
[x] Report freshness separated from value-change age
[x] Active hot-side RCL coordinator refresh every 30 s using one trigger entity
[x] Hard RCL reload kept separate and throttled
[x] Hardware ABORT + positive-action lockout
[x] Manual channel ownership
[x] Generic Supervised Apply outside dedicated phase authority
[x] Confirmed readback grace
```

### Current Heatstrike contract

```text
MASH/BLE still below strike
AND real mash/wort gradient >= 1.5 °C
AND hottest-view overshoot > +0.5 °C
AND hottest-view overshoot <= +2.0 °C

=> heat authority cap 5 %
=> heater master remains available to BrewZilla local thermostat
=> pump 100 % for temperature equalization
```

If hottest-view overshoot exceeds +2.0 °C, explicit hard stop remains authoritative.

This does not widen Mash-In READY.

### Current Mash-In contract

```text
ready_for_mash_in
  -> Mash-In Started
  -> target releases toward mash target
  -> pump OFF / utilization 0 %
  -> operator adds/stirs grain
  -> BA observes BF PAUSED after Mash-In Started
  -> later BF RUNNING / Continue
  -> Mash-In Complete
  -> normal mash circulation resumes
```

Not sufficient by themselves:

```text
BF already running at Mash-In Started
active Brewfather mash target changing
normalized BA runtime remaining live/running
```

The second 2026-09-06 field run confirms the backend handoff can complete correctly. UI completion feedback still needs polish.

### Current RCL freshness contract

```text
control/report freshness
  -> last_reported, fallback last_updated

value age / stagnation
  -> last_updated + explicit value-change tracking
  -> diagnostics only

active hot-side polling
  -> one BrewZilla CoordinatorEntity
  -> update_entity / coordinator async_request_refresh()
  -> every 30 seconds

hard recovery
  -> reload_config_entry only for hard loss/extreme report staleness
  -> minimum 15 minutes between reload requests
```

The new contract is regression-tested but not yet physically validated.

---

## Physical validation still required

Immediate next-run checks:

```text
[ ] active RCL report age stays bounded under BA 30 s refresh cadence
[ ] stable temperature/target does not create false stale/fail-passive blocking
[ ] 5 % / 100 % Heatstrike gradient relief converges safely
[ ] > +2.0 °C hottest-view overshoot still hard-stops heat
[ ] READY still depends on process probe / bounded operator acknowledgement only
[ ] Mash-In Started visibly holds pump OFF / 0 % during grain addition
[ ] BF PAUSED is observed only after Mash-In Started
[ ] later RUNNING is the first automatic completion evidence
[ ] target becomes actual mash target, e.g. 66.0 °C
[ ] normal mash circulation resumes after completion
[ ] completion is immediately obvious in the master UI
[ ] #157 66 °C hold starts only on actual target reach
[ ] #157 PAUSE freezes timing
[ ] #157 66 -> 72 °C ramp is recorded separately and next hold starts on reach
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

BrewZilla internal temperature remains primary kettle context throughout the hot side.

Validation still required:

```text
[ ] release exactly at Boil start
[ ] no competing Brewday/Cooling interpretation during Boil
[ ] Cooling/CFC acquisition during Chill
[ ] continued wort-out use during Transfer
[ ] immersion-coil/manual-temperature path without unnecessary external-sensor dependency
```

---

## Physical timing / Equipment Learning

The #157 physical timing layer remains read-only and must not influence live control.

Evidence fields include:

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

## Dashboard direction

Current production/test UI remains YAML-based.

A pilot BrewAssistant JavaScript/SVG pre-boil temperature gauge is now present. The purpose is to validate a future architecture where complex BrewAssistant-specific presentation moves from very large YAML cards into reusable JS cards while YAML becomes a thin configuration wrapper.

Current rule:

```text
pilot first
-> validate geometry/state behavior
-> do not rewrite all cards during beta.9 hot-side validation
-> if successful, plan staged YAML -> JS migration separately
```

The existing `gauge-card-pro` card remains available until the pilot is accepted.

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

---

## Beta.9 release path

Current candidate release notes:

[`beta9-release-notes.md`](beta9-release-notes.md)

Required before release:

```text
1. make dev green under CI + HACS + Hassfest
2. complete the next physical RCL + Heatstrike + Mash-In regression
3. validate first real-mash hold/ramp path
4. promote dev -> beta with Create a merge commit
5. run intended beta validation
6. fix regressions on dev, then promote again if needed
7. promote validated beta -> main with Create a merge commit
8. create GitHub prerelease v0.2.0-beta.9 from main
```
