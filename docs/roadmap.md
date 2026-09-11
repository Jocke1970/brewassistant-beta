# Roadmap

This document tracks the current BrewAssistant beta roadmap.

BrewAssistant keeps runtime state, process interpretation, safety guards and hardware decisions in the Python custom integration under `custom_components/brewassistant/`.

```text
Python integration = runtime + ownership + logic + safety + hardware decisions
Dashboard layer     = presentation + explicit operator actions
```

The dashboard is still primarily YAML, with BrewAssistant-specific JavaScript/SVG cards evaluated only where they simplify complex instruments.

---

## Current project phase

The active development baseline on `dev` now includes:

```text
2026-08-29 ownership / ABORT validation
2026-08-31 Heatstrike / Mash-In regression work
2026-09-05 gradient / handoff fixes
2026-09-06 physical Heatstrike / Mash-In runs
2026-09-11 RAPT profile-runtime integration
2026-09-11 BrewTracker zero-minute PAUS checkpoint handling
2026-09-11 Brewfather Planning/full-recipe presentation
2026-09-11 Brewfather fermentation schedule-target consumption
2026-09-11 parked Grainfather GF30 read-only backend scaffold
```

The 2026-09-11 repository consolidation also moved the accidentally main-based feature work back onto the intended `dev` development line. The corresponding PR heads passed CI, HACS validation and Hassfest before merge. This is an integration milestone, **not** a physical known-good declaration.

Current sequence:

```text
stabilize current dev integration baseline
↓
validate BrewTracker PAUS -> physical target hold -> manual Resume
↓
validate RAPT profile -> BrewAssistant -> RCL -> BrewZilla path
↓
repeat full Heatstrike -> READY -> Mash-In handoff + ABORT
↓
first supervised real-mash hold + temperature-ramp validation
↓
Mash out / Sparge / Pre-boil validation
↓
Boil ramp / Boil + external process-sensor ownership release
↓
Cooling/CFC Chill / Transfer ownership handoff validation
↓
BrewZilla Equipment Learning evidence pass
↓
Climate Supervisor / Carbonation / Fermentation full-cycle validation
↓
promote dev -> beta -> main when the relevant physical evidence exists
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
- temporary feature/fix branches must target `dev` and are removed after merge;
- `dev -> beta` and `beta -> main` use pull requests;
- promotion PRs use **Create a merge commit**, not squash/rebase;
- GitHub **Automatically delete head branches** stays disabled because `dev` and `beta` are permanent;
- Dependabot targets `dev`;
- CI, HACS and Hassfest run on `dev`, `beta` and `main`;
- releases are created only from `main`;
- beta releases are prereleases such as `v0.2.0-beta.9`.

### 2026-09-11 branch reconciliation

Three development branches had accidentally been created from `main` instead of `dev`:

```text
feature/rapt-brewzilla-profile-runtime
feature/fermentation-ramp-target
feature/grainfather-gf30-backend
```

They have now been retargeted/reconciled with `dev` and merged there through PRs #205, #204 and #206 respectively. Their work is preserved by Git history and the merged PRs; the temporary branch refs may be deleted once repository cleanup is performed.

Do **not** promote the resulting `dev` state to `beta` merely because CI is green. Physical hot-side validation remains a separate promotion gate.

---

## Brewday Runtime / execution modes

Completed / integrated on `dev`:

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
[x] Physical/effective/device target diagnostics separated
[x] Brewday operator ABORT + persistent ownership latch
[x] Explicit Brewday rearm
[x] RAPT profile runtime as process/target directive source
[x] BrewTracker zero-minute PAUS checkpoint guard
[x] Planning/full-recipe Brewfather presentation
[x] Humanized BrewTracker execution schedule
```

### Runtime ownership split

BrewAssistant now treats **recipe source**, **runtime/timer owner** and **physical controller** as separate concerns.

#### Brewfather / BrewTracker supervised mode

```text
Brewfather recipe
      ↓
BrewTracker owns timeline + timer
      ↓
BrewAssistant interprets active target/checkpoint
      ↓
BrewAssistant controls BrewZilla through RCL
```

A BrewTracker step transition is never proof that the vessel physically reached the target temperature.

The verified zero-minute PAUS behavior gives an explicit synchronization checkpoint:

```text
BF reaches PAUS / 0 min
        ↓
BrewTracker = paused
BF timer/progress stay frozen
        ↓
BA holds the current tracker target
BA must not pre-actuate the next target
        ↓
physical target is satisfied
        ↓
operator resumes Brewfather
        ↓
next BF/BT step becomes eligible
```

The Brewfather/BrewTracker pause behavior itself has been practically verified. The BA/BZ current-target hold still requires physical validation.

#### Future BrewAssistant-owned imported recipe runtime

```text
Brewfather = recipe source only
BrewAssistant = runtime + timer + progression owner
BrewAssistant/RCL/BrewZilla = physical control path
```

For timed rests, the BA timer must start only after physical target reach. BrewTracker is not required for this mode.

See [`brewday-execution-modes.md`](brewday-execution-modes.md).

---

## RAPT profile runtime

The RAPT/BrewZilla profile path is now integrated on `dev` as another process/target directive source. RAPT does **not** become a competing heat/pump controller.

Ownership remains:

```text
RAPT profile intent
      ↓
BrewAssistant runtime / safety / physical policy
      ↓
RAPT Cloud Link
      ↓
BrewZilla
```

The supervised reference flow is:

```text
Heatstrike -> Mash In -> Mash Rest -> Mash Out -> Boil -> ChillOut
```

Important contracts:

- BA keeps physical target/heat/pump authority;
- a manual RAPT Mash-In step does not bypass BA's Mash-In gate;
- source loss is fail-passive rather than silently falling back to another runtime owner;
- `ChillOut 0 °C` is a process marker, never a hot-side setpoint;
- ABORT remains authoritative over RAPT ownership.

See [`rapt-brewzilla-profile-runtime.md`](rapt-brewzilla-profile-runtime.md).

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
[x] Heatstrike final-approach local-regulation preservation
[x] Fresh-only automatic Mash-In READY
[x] Bounded operator strike acceptance
[x] Heatstrike gradient-relief mode
[x] Mash-In Started target release
[x] Mash-In Started pump OFF / 0 % ownership window
[x] Strict post-start BF PAUSED -> RUNNING automatic Mash-In completion
[x] Fail-passive ordinary telemetry loss
[x] Report freshness separated from value-change age
[x] Active hot-side RCL coordinator refresh every 30 s
[x] Hardware ABORT + positive-action lockout
[x] Manual channel ownership
[x] Generic Supervised Apply outside dedicated phase authority
[x] Confirmed readback grace
[x] BrewTracker PAUS current-target hold guard
[x] RAPT profile target/control bridge
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

### Current Mash-In contract

```text
ready_for_mash_in
  -> Mash-In Started
  -> target releases toward mash target
  -> pump OFF / utilization 0 %
  -> operator adds/stirs grain
  -> BA observes real progression evidence
  -> Mash-In Complete
  -> normal mash circulation resumes
```

Plain BF `running`, target movement or a live normalized runtime are not sufficient by themselves to fake completion.

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

The current RCL freshness contract is regression-tested but still requires physical validation in the merged runtime combination.

---

## Physical validation still required

Immediate supervised checks:

```text
[ ] BrewTracker PAUS holds the current physical target and never pre-actuates the next target
[ ] manual BF Resume is the first point where the next BF/BT target becomes eligible
[ ] RAPT profile target propagates through BA -> RCL -> BrewZilla correctly
[ ] RAPT source loss remains fail-passive
[ ] RAPT Mash-In handoff keeps BA physical authority
[ ] ChillOut marker releases hot-side authority without writing 0 °C
[ ] operator ABORT safely overrides RAPT and BrewTracker paths
[ ] active RCL report age stays bounded under BA 30 s refresh cadence
[ ] stable temperature/target does not create false stale/fail-passive blocking
[ ] Heatstrike gradient relief converges safely
[ ] > +2.0 °C hottest-view overshoot still hard-stops heat
[ ] READY still depends on the process probe / bounded operator acknowledgement
[ ] Mash-In Started visibly holds pump OFF / 0 % during grain addition
[ ] target becomes actual mash target after handoff
[ ] normal mash circulation resumes after completion
[ ] timed mash hold starts only after actual target reach
[ ] physical pause freezes BA timing where BA owns timing
[ ] physical ramp is recorded separately and the next hold starts on reach
```

None of the merged 2026-09-11 work should be labelled physically known-good until the relevant checks pass in Home Assistant/BrewZilla.

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

## Fermentation targets

The Brewfather fermentation-schedule target path is integrated on `dev`.

Contract:

```text
explicit Brewfather schedule_target_temperature metadata
  -> may provide recommended_temperature_c
  -> source/entity are exposed for diagnostics

ordinary numeric recipe-target state without schedule metadata
  -> must NOT silently replace BA's existing SG/manual tracking rules
```

Climate Supervisor remains outside this runtime-validation change and requires its own full-cycle validation before automatic actuation is considered proven.

---

## Grainfather GF30 fermenter backend

Phase 1 is integrated on `dev` as a **read-only, parked scaffold**.

```text
[x] backend/domain split established
[x] discovery/readback normalization scaffold
[x] documentation + regression guards
[ ] physical GF30 entity characterization
[ ] verified heating/cooling capabilities
[ ] verified setpoint/readback semantics
[ ] Supervised Apply executor
[ ] provider selection against existing fermentation chamber
```

Do not add guessed GF30 entity IDs, model heuristics, actuator assumptions or automatic target writes before physical hardware is available.

See [`backends/grainfather-fermenter.md`](backends/grainfather-fermenter.md).

---

## Physical timing / Equipment Learning

The physical timing layer remains read-only and must not influence live control.

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

The dashboard is explicitly modular. Reusable cards should expose one responsibility rather than rebuilding a private monolithic Brewday stack.

Current key surfaces include:

```text
brewassistant_brewday          = overview / source chain
brewtracker_runtime            = BrewTracker runtime
rapt_profile_runtime           = RAPT runtime
brewzilla_mash_in_controls     = physical Mash-In gate
brewday_operator_actions       = operator controls
brewday_details                = diagnostics/details
brewfather_recipe              = full recipe + humanized execution schedule
```

The Brewfather recipe card is intentionally available already in `Planning` when full recipe data exists. BrewTracker remains the runtime feed; the full batch recipe remains the recipe source.

---

## Beta.9 release path

Current candidate release notes:

[`beta9-release-notes.md`](beta9-release-notes.md)

Required before release:

```text
1. keep dev green under CI + HACS + Hassfest
2. complete the current BrewTracker/RAPT/RCL/Heatstrike/Mash-In physical regression set
3. validate the first real-mash hold/ramp path
4. update dated physical-validation evidence
5. promote dev -> beta with Create a merge commit
6. run the intended beta field validation
7. fix regressions on dev and promote again if needed
8. promote validated beta -> main with Create a merge commit
9. create GitHub prerelease v0.2.0-beta.9 from main
```
