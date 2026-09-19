# Roadmap

This document tracks the current BrewAssistant beta roadmap. Runtime state, process interpretation, safety guards and hardware decisions belong in the Python integration under `custom_components/brewassistant/`; the dashboard presents state and explicit operator actions. The dashboard remains primarily YAML, with optional dedicated JS/SVG instruments where justified.

**Status checkpoint: 2026-09-19.** HLT SIM-1 is now integrated into shared `dev` via [PR #212](https://github.com/Jocke1970/brewassistant-beta/pull/212); it remains **simulation-only**. The prior `dev` SG-driven fermentation changes remain present. CI, HACS validation and Hassfest passed for the merged `dev` commit `746633cfd5c22483fc25e821a966cccb25f84784`. These checks do not validate physical HLT power allocation. See [HLT field evidence and Brewday handoff](hlt-sim1-field-validation-2026-09-19.md).

---

## Current project phase

Integrated `dev` milestones:

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
2026-09-17 SG-driven fermentation development integrated on dev
2026-09-19 HLT SIM-1 read-only backend, sensors, trace and EN/SV cards merged to dev
```

The 2026-09-11 reconciliation moved accidentally main-based feature work back onto the intended `dev` line. PR checks passed before merge, but integration is not automatically physically known-good. The 2026-09-19 HLT merge similarly incorporates an independently developed feature into an already-advanced `dev`; it does **not** replace or install the local Home Assistant integration automatically.

Current sequence:

```text
stabilize and synchronize the combined dev integration baseline
↓
Brewday/BrewZilla: BrewTracker PAUS -> target hold -> manual Resume
↓
RAPT profile -> BA -> RCL -> BZ and complete Heatstrike/Mash-In/ABORT validation
↓
first supervised real-mash hold / target ramp / mash-out / sparge / pre-boil
↓
HLT SIM-1 HA retest against the current combined dev (ramp, cruise, yield, logs)
↓
Boil + external process-sensor release; Cooling/CFC Chill/Transfer handoff
↓
Equipment Learning and HLT simulation ETA/evidence review
↓
Climate Supervisor / Carbonation / Fermentation full-cycle validation
↓
consider dev -> beta -> main only after relevant field evidence
```

Physical evidence snapshots remain separate and should not be rewritten retroactively:

- [`physical-validation-2026-08-31.md`](physical-validation-2026-08-31.md)
- [`physical-validation-2026-09-05.md`](physical-validation-2026-09-05.md)
- [`physical-validation-2026-09-06.md`](physical-validation-2026-09-06.md)
- [`parking-checkpoint-2026-09-06.md`](parking-checkpoint-2026-09-06.md)
- [`hlt-sim1-field-validation-2026-09-19.md`](hlt-sim1-field-validation-2026-09-19.md) — simulator-only BZ/HLT observation and outstanding verification

---

## Repository / release workflow

Only three **long-lived** branches are intended:

```text
dev  = coordinated development
beta = integrated field-test candidate
main = installable/released version
```

Normal work goes on `dev`. Temporary feature/fix branches must target `dev` and should be cleaned up after merge, subject to checking they contain no independent work; never delete a branch blindly. Promotion `dev -> beta` and `beta -> main` uses PRs with **Create a merge commit**, not squash/rebase; permanent ancestry matters. GitHub automatic head-branch deletion remains disabled so `dev`/`beta` cannot disappear. Dependabot targets `dev`; CI, HACS and Hassfest run on `dev`, `beta` and `main`; releases come only from `main` and beta versions are prereleases.

### Branch checkpoints

On 2026-09-11, three development branches accidentally based on `main` were reconciled to `dev` and merged via PRs #205, #204 and #206: `feature/rapt-brewzilla-profile-runtime`, `feature/fermentation-ramp-target` and `feature/grainfather-gf30-backend`. Their work remains in Git history.

HLT used PR #212 (`feature/hlt-simulation-core` -> `dev`) and was squash-merged 2026-09-19. Number-suffixed HLT branch refs from the parallel work were observed; do not create replacements or delete them without checking owners/references. Development and installation must always be based on the **current combined `dev`**, not a stale feature archive. A previous pinned test archive at commit `977136c5` was installed locally; that installation is not the same as merged `dev` commit `746633c` and lacks the final stage/ramp fixes. Preserve backups/logs; compare the installed files with intended version before any whole-integration update.

**Do not promote `dev` to `beta` just because GitHub checks are green.** Required physical validation is a separate gate. See [`CONTRIBUTING.md`](../CONTRIBUTING.md).

---

## Brewday Runtime / execution modes

Integrated on `dev`:

```text
[x] Custom integration, config flow and coordinator
[x] Normalized Brewday Runtime
[x] Brewfather RAW Brew Tracker timeline resolver
[x] Planning/Brewing pre-start visible without hot-side ownership
[x] Positive tracker-start ownership; legitimate pause keeps ownership
[x] Manual/Brewfather mutual exclusion and safe handoff
[x] Brewday Stage Engine v2
[x] Persistent Brewday Event Log / Flight Recorder
[x] Physical/effective/device target diagnostics separated
[x] Operator ABORT, persistent ownership latch and explicit rearm
[x] RAPT profile runtime as process/target directive source
[x] BrewTracker zero-minute PAUS checkpoint guard
[x] Planning/full-recipe presentation and humanized schedule
[x] HLT SIM-1 consumes normalized Brewday/Audit + sparge volume without becoming a physical controller
```

Recipe source, runtime/timer owner and physical controller are separate. Brewfather/BrewTracker mode: recipe and timer belong to Brewfather/BrewTracker; BA interprets target/checkpoint and controls BZ via RCL. A step transition is not proof that the kettle reached target. In particular:

```text
BF PAUS / 0 min -> tracker paused -> timer/progress frozen
BA must hold current target; never pre-actuate next target
physical target satisfied -> operator BF Resume
next BF/BT step becomes eligible only after that handoff
```

Brewfather PAUS behavior has been physically observed; the combined BA/BZ target-hold still requires validation. Future BA-owned imported recipe mode instead uses Brewfather as recipe source, BA as runtime/timer owner, and starts timed rests only after physical target attainment. See [`brewday-execution-modes.md`](brewday-execution-modes.md).

### RAPT profile runtime

The RAPT/BrewZilla profile on `dev` supplies directives, **not** competing heat/pump authority:

```text
RAPT profile intent -> BA runtime/safety/physical policy -> RAPT Cloud Link -> BrewZilla
```

Reference stages: Heatstrike -> Mash In -> Mash Rest -> Mash Out -> Boil -> ChillOut. A manual RAPT Mash-In does not bypass BA's Mash-In gate; source loss is fail-passive; `ChillOut 0 °C` is a process marker, never hot-side target; ABORT outranks RAPT. See [`rapt-brewzilla-profile-runtime.md`](rapt-brewzilla-profile-runtime.md).

---

## BrewZilla hot side

Integrated on `dev`:

```text
[x] Normalized BZ runtime, separate runtime/effective/device targets
[x] Heat/pump utilization and switch control surface
[x] Dedicated Heatstrike/Mash-In phase authority and real strike-target latch
[x] External MASH/process probe for readiness; BZ internal/WORT for limiter/safety
[x] Final-approach local-regulation preservation, fresh-only READY, bounded strike acceptance
[x] Gradient-relief mode and strict Mash-In Started pump OFF/0 % window
[x] Strict post-start BF PAUSED -> RUNNING Mash-In completion
[x] Fail-passive telemetry loss; report freshness distinct from numeric-change age
[x] Active RCL coordinator refresh every 30 s
[x] Hardware ABORT, operator ABORT, positive-action lockout
[x] Manual channel ownership; generic Supervised Apply outside dedicated phase authority
[x] Confirmed readback grace; BrewTracker PAUS current-target hold; RAPT bridge
```

Current Heatstrike exception: external MASH/BLE remains below strike, mash/wort gradient >=1.5 °C, hottest-view overshoot >+0.5 °C and <=+2.0 °C -> heater authority cap 5 %, master available to local thermostat, pump 100 % for equalization. Above +2.0 °C, explicit hard stop. **This narrowly scoped Heatstrike safety limit is distinct from HLT's unconditional rule: never cap BZ for HLT.**

Mash-In: `ready_for_mash_in -> Mash-In Started -> target releases to mash target -> pump OFF/0 % -> operator adds grain -> real post-start BF PAUSED then RUNNING -> Mash-In Complete -> normal circulation`. Plain BF `running`, target movement or live normalized runtime alone is insufficient.

RCL freshness: control/report age uses `last_reported` with `last_updated` fallback; numeric stagnation is diagnostic only. One BZ CoordinatorEntity is refreshed every 30 s; hard `reload_config_entry` for extreme loss only, throttled >=15 min. This is separately regression-tested, not a replacement for HLT's physical watt/temperature freshness or electrical protection.

### Immediate supervised validation

```text
[ ] BF PAUS holds physical current target until explicit Resume
[ ] RAPT profile target propagates BA -> RCL -> BZ
[ ] RAPT source loss remains fail-passive; Mash-In authority and ChillOut marker safe
[ ] ABORT overrides both process sources
[ ] Active RCL report freshness bounded despite stable unchanged settings
[ ] Heatstrike gradient relief converges; >+2.0 °C overshoot hard stop
[ ] READY uses process probe / bounded acknowledgement
[ ] Mash-In Started keeps pump OFF/0 % during grain addition
[ ] Post-start progression releases correct mash target and circulation
[ ] Timed holds and ramps use actual physical reach, not source step start
```

Do not present CI-green or this roadmap as physical validation. See [`brewday-brewzilla.md`](brewday-brewzilla.md).

---

## HLT SIM-1 / BrewZilla power priority — 2026-09-19

**Integrated:** read-only simulation backend on independent 30-second timer; 31 telemetry keys; virtual HLT thermal model and time/energy estimates; JSONL per Audit session; EN/SV standalone high-contrast cards; regression tests. BZ retains absolute priority, including if a later autonomous heater cycle raises observed consumption. No HLT hardware service calls and no BZ cap/grant writes. `power_budget_verified=false`; the default 2,500 W budget is a scenario, not an electrical rating.

**Observed in physical-water test:** BZ sensor followed its real 2,323–2,356 W heating; 17 L mash/test and 11.38 L sparge propagated correctly; HLT waited with 0 virtual W. Stable BZ target/utilization settings were falsely treated as stale; corrected after the run. Uploaded JSONL contained a virtual HLT opportunity during explicit `Ramp to 72°C`, then virtual yield and simulated overlap about 3.43 kW. It does **not** show a safe physical arbitration. An explicit preparation-stage allowlist and ramp-step veto were added before merge and passed CI, but the final logic is not yet revalidated in installed HA.

```text
[x] Merge SIM-1 telemetry, trace, card and regression work to common dev (#212)
[x] Preserve parallel SG fermentation files on dev and pass combined CI/HACS/Hassfest
[x] Confirm BZ wattmeter tracks physical heater and sparge context reaches HLT
[x] Fix held numeric setpoint/utilization freshness and erroneous virtual none UI label
[x] Add explicit eligible-stage allowlist and ramp-step veto with tests
[ ] Field-retest latest combined dev: ramp, cruise, new ramp, virtual yielding and off
[ ] Confirm real BF / Manual / RAPT stage and step labels are covered, unknown fails closed
[ ] Verify stale physical power/temp fail closed and normal held number settings stay valid
[ ] Review full JSONL, session/reset/timer gaps, temperature/ETA vs real mash window
[ ] Implement separately reviewed learning proposals; no autonomous safety-policy rewriting
[ ] Identify actual HLT meter, switch and probe with verified OFF readback
[ ] Engineer independent fast fail-OFF HLT shedding/interlock, circuit and dry-fire safety
[ ] Complete supervised hardware commissioning before physical HLT output
```

The 30-second HA loop **cannot** provide overcurrent protection. An independent physical interlock is essential before energizing HLT on a shared budget; BZ must not wait to receive power or be throttled. Next HLT work is deliberately parked until Brewday can coordinate a current combined-`dev` field test. See [dated handoff](hlt-sim1-field-validation-2026-09-19.md), [HLT backend](hlt-dashboard-backend.md), [dashboard guide](hlt-dashboard-card.md), and [code-local README](../custom_components/brewassistant/hlt/README.md).

---

## External process-temperature sensor ownership

```text
Heat strike -> Mash -> Mash out -> Sparge -> Pre-boil
  owner = Brewday / BZ hot side; role = external process/mash sensor
Boil starts -> hot side releases external sensor
Chill -> Transfer -> Cooling/CFC acquires as outlet/wort-out if method requires it
```

BZ internal remains the kettle-temperature context. Validate release exactly at Boil, absence of competing interpretation, CFC acquisition during Chill/Transfer and coil/manual path not depending unnecessarily on external probe.

---

## Fermentation targets and GF30

Brewfather fermentation-schedule metadata may supply `recommended_temperature_c` when explicit `schedule_target_temperature` is available. An ordinary numeric recipe target without schedule metadata may **not** silently override SG/manual tracking. Climate Supervisor remains separately subject to full-cycle testing. On `dev`, parallel SG-driven fermentation work is present; HLT merge must not remove it.

Grainfather GF30 phase 1 is a parked **read-only** scaffold: domain split, discovery/readback normalization and regression guards exist. Still to do: characterize physical GF30 entities, heating/cooling capabilities, setpoint/readback semantics, supervised executor and provider selection. Never guess GF30 IDs or enable automatic writes before hardware evidence. See [`backends/grainfather-fermenter.md`](backends/grainfather-fermenter.md).

---

## Physical timing / Equipment Learning

Timing remains read-only: ramp/hold/wall/pause duration, delta-T, mean °C/min, selected sensor, water-only vs real mash and heat/pump evidence. Later work: strike/mash-ramp/mash-out/boil timing suggestions, confidence per observation quality/count/context, operator-reviewed profile candidates, persistent approved overrides, reversible reset. Learning is advisory until explicitly approved. HLT's current thermal model and JSONL do **not** constitute a self-adapting controller.

---

## Cooling / Chill / Transfer

Cooling Runtime v2 models CFC and traditional immersion-coil/manual-water methods. Physical checks still due: Boil->Chill ownership, CFC outlet probe, CFC and coil sanitation, coil with internal/manual temperature, manually or pump-driven cooling water, pitch readiness and Transfer completion.

---

## Dashboard direction

Dashboard design is modular, with one responsibility per reusable card. Key surfaces: `brewassistant_brewday` overview; `brewtracker_runtime`; `rapt_profile_runtime`; `brewzilla_mash_in_controls`; `brewday_operator_actions`; `brewday_details`; `brewfather_recipe` (available in Planning with recipe data). The HLT cards `hlt_power_dashboard.yaml` / `_sv.yaml` are **read-only standalone** examples, not automatically inserted into Brewday or actuator controls. They separate physical BZ W from virtual HLT W, temperature measurement from model and actual energy recipient from simulated permission.

---

## Beta.9 release path

Current candidate notes: [`beta9-release-notes.md`](beta9-release-notes.md). Required sequence: keep `dev` green; validate BrewTracker/RAPT/RCL/Heatstrike/Mash-In and real-mash hold/ramp; add separate HLT field evidence before considering its promotion; update dated validation; promote `dev -> beta` via merge commit; run beta HA tests; fix regressions on `dev` and re-promote if necessary; promote validated `beta -> main` via merge commit; create prerelease from main. **HLT SIM-1 integration on `dev` does not by itself authorize physical HLT or a beta/main promotion.**
