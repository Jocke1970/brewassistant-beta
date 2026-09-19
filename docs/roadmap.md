# Roadmap

This document tracks BrewAssistant's current beta roadmap. Runtime state, process interpretation, safety guards and hardware decisions belong in Python under `custom_components/brewassistant/`; dashboards present state and explicit operator actions.

**Status checkpoint: 2026-09-19.** HLT SIM-1 was merged to shared `dev` via [PR #212](https://github.com/Jocke1970/brewassistant-beta/pull/212) alongside SG-driven fermentation work. It remains **simulation only**. The subsequent water-only test found that Brewfather could advance from 66 °C to 72 °C before the physical 66 °C hold finished and that Mash-In Complete restarted the pump; the new physical mash interlock is implemented and regression-tested on `dev`, but its installed HA/hardware behavior is **not yet validated**. `v0.2.0-beta.10` was incorrectly tagged from old code and must not be used for the next test. The corrective beta.11 candidate proceeds through [PR #213](https://github.com/Jocke1970/brewassistant-beta/pull/213). See [test protocol](physical-mash-test-plan-2026-09-19_sv.md), [control findings](physical-mash-control-contract-2026-09-19.md) and [HLT evidence](hlt-sim1-field-validation-2026-09-19.md).

---

## Current project phase

Integrated development milestones:

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
2026-09-19 physical mash interlock, settling and two pump confirmations coded on dev
```

On September 11, accidentally main-based development was reconciled onto `dev`; on September 19, HLT work was likewise merged into the combined development line. Neither merge updates HA automatically, and green GitHub checks alone prove no physical safety.

Current sequence:

```text
[ ] Review combined beta.11 code and release documentation on dev
[ ] PR dev -> beta; Create a merge commit; verify all checks on beta merge SHA
[ ] Tag v0.2.0-beta.11 from verified beta SHA; GitHub Pre-release from beta
[ ] Back up HA; install exact tagged prerelease; verify installed interlock/ABORT first
[ ] Supervised water-only physical Mash-In, settling, pump and 66 -> 72 C gating tests
[ ] Re-test HLT SIM-1 ramp/cruise/yield/readback without physical HLT
[ ] Brewday/BZ BrewTracker PAUS -> hold -> manual Resume and RAPT source handoff
[ ] Real mash only after water-only acceptance and additional safety review
[ ] Mash-out, sparge, pre-boil; Boil probe handoff; Cooling/CFC Chill/Transfer
[ ] Equipment Learning and HLT simulation estimates; climate/fermentation full cycle
[ ] Consider beta -> main and stable release only after appropriate field evidence
```

Preserve dated observations as snapshots: [`physical-validation-2026-08-31.md`](physical-validation-2026-08-31.md), [`physical-validation-2026-09-05.md`](physical-validation-2026-09-05.md), [`physical-validation-2026-09-06.md`](physical-validation-2026-09-06.md), [`parking-checkpoint-2026-09-06.md`](parking-checkpoint-2026-09-06.md), [`hlt-sim1-field-validation-2026-09-19.md`](hlt-sim1-field-validation-2026-09-19.md). Never rewrite history to imply later fixes were tested earlier.

---

## Repository / release workflow

Only three permanent branches:

```text
dev  = coordinated development
beta = integrated test candidate + GitHub prerelease source
main = validated/stable distribution
```

Development is committed to `dev`. Promote `dev -> beta` via PR and **Create a merge commit** (never squash/rebase for permanent branch promotion); preserve `dev`. Require CI, HACS and Hassfest on the resulting beta merge SHA, then tag `vX.Y.Z-beta.N` from **exactly that SHA** and publish GitHub **Pre-release** with **Target: beta** and the full Markdown. Check the tag SHA and its actual manifest/critical files after publication. Install the exact tag through HACS for supervised physical beta tests. If validation fails, fix on `dev`, promote again and use a **new** beta version—never move published tags. Promote `beta -> main` separately only after sufficient physical evidence, and tag a stable version from the verified main merge SHA. `main` must not become the distribution route for unvalidated test candidates. Consult [`CONTRIBUTING.md`](../CONTRIBUTING.md) for the authoritative checklist.

CI, HACS and Hassfest run on `dev`, `beta` and `main`; Dependabot targets `dev`, and the promotion guard permits PRs to `beta` from `dev` and PRs to `main` from `beta`. Keep automatic branch deletion disabled. Don't invent branches, rely on old archives, or confuse a release title with the code inside its tag.

### Branch checkpoints

On 2026-09-11, three accidentally `main`-based feature lines were reconciled onto `dev` via PRs #205, #204 and #206 (RAPT profile, fermentation ramp targets, Grainfather GF30 scaffold). PR #212 added the HLT simulator and was squash-merged to `dev`. These are historical changes, not permission to create replacement branches or delete other people's refs. An earlier pinned test archive at `977136c5` was not the merged combined baseline. Preserve local backups and install only a verified versioned release.

**The prior requirement to complete physical testing BEFORE every beta prerelease was circular when HACS required a prerelease to install the test code.** The corrected gate is: regression/CI → promote to `beta` → tag and publish an explicitly experimental prerelease → supervised HA/water-only field test → only then consider stable promotion. CI alone never approves malt or unattended use.

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
[x] HLT SIM-1 consumes normalized Brewday/Audit + sparge volume, not a hardware controller
```

Recipe source, runtime/timer owner and physical controller are separate. In Brewfather/BrewTracker mode, Brewfather owns the recipe and timeline; BA interprets checkpoints and controls BZ via RCL. A source step transition is not proof that the kettle reached its target.

```text
BF PAUS / 0 min -> tracker paused -> timer/progress frozen
BA must hold physical current target; never pre-actuate next target
physical target satisfied -> operator BF Resume
next BF/BT step eligible only after safety/physical gating
```

Brewfather PAUS behavior has been observed; combined target-hold and the new physical handoff require installed verification. A future BA-owned imported-recipe mode would use BF as recipe source but BA as physical timer owner. See [`brewday-execution-modes.md`](brewday-execution-modes.md).

### RAPT profile runtime

RAPT supplies directives, not separate heat/pump authority:

```text
RAPT profile -> BA runtime + guards -> RAPT Cloud Link -> BrewZilla
```

Reference stages: Heatstrike -> Mash In -> Mash Rest -> Mash Out -> Boil -> ChillOut. Manual RAPT Mash-In must not bypass BA's gate; source loss is fail-passive; `ChillOut 0 °C` is a marker, not a hot-side target; ABORT outranks RAPT. See [`rapt-brewzilla-profile-runtime.md`](rapt-brewzilla-profile-runtime.md).

---

## BrewZilla hot side

Integrated on `dev` (code status, not physical sign-off):

```text
[x] Separate runtime/effective/device targets and heat/pump control surface
[x] Heatstrike/Mash-In authority and strike-target latch
[x] External MASH probe for process readiness, BZ internal/WORT for kettle/safety
[x] Local-regulation preservation, fresh READY and bounded strike acceptance
[x] Gradient relief and Mash-In Started pump OFF/0 %
[x] Strict post-start BF PAUSED -> RUNNING Mash-In Complete
[x] New 10 min settling / confirmed 25 % then confirmed 50 % recirculation
[x] Physical hold-target interlock when Brewfather proceeds early
[x] Fail-passive telemetry loss and separate report/value freshness
[x] Active RCL refresh every 30 s
[x] Hardware/operator ABORT and positive-action lockout
[x] Manual ownership, supervised apply and confirmed readback grace
[x] BrewTracker PAUS target hold and RAPT runtime bridge
```

Heatstrike gradient relief: external MASH remains below strike, gradient >=1.5 °C, hottest-view overshoot >+0.5 °C and <=+2.0 °C -> heat cap 5 % and pump 100 % for equalization while local regulation remains available. Above +2.0 °C, explicit heat stop. **Never cap BZ as an HLT power-saving strategy.**

Corrected Mash-In contract: `ready -> Started -> mash target/pump OFF -> BF PAUSED then RUNNING -> Complete -> pump OFF + 10 min settling -> separate operator 25 % -> confirmed low-flow 5 min -> separate operator 50 %`. The physical hold owns the target until both the hold and normal circulation are complete. No timer may start pump. Unverified source progression is never equivalent to operator confirmation.

RCL freshness: control/report age uses `last_reported` with `last_updated` fallback; stale numeric values alone do not prove a disconnected device. The active coordinator refreshes every 30 s; extreme reloads are throttled >=15 min. This is distinct from HLT's real physical watt/temperature freshness and electrical protection.

### Immediate supervised validation

```text
[ ] Verify tagged beta.11 integration and physical_mash_interlock_active attribute
[ ] BF PAUS holds physical target until approved resume
[ ] RAPT source, ownership and source-loss fail-passive
[ ] Hardware/operator ABORT takes precedence
[ ] RCL report freshness with stable values
[ ] Heatstrike/READY and >+2.0 C overshoot stop
[ ] Started turns pump OFF/0 % and sets mash target
[ ] Complete starts 10 min settling, pump still OFF/0 %
[ ] Settling timeout never switches pump ON
[ ] First 25 % and second 50 % each need operator confirmation + readback
[ ] Physical hold blocks BF 66 -> 72 C until fully complete
[ ] Old confirmations never resurrect after HA restart
[ ] Ramp/mash-out/sparge follow real process temperature
```

See [`physical-mash-test-plan-2026-09-19_sv.md`](physical-mash-test-plan-2026-09-19_sv.md) and [`brewday-brewzilla.md`](brewday-brewzilla.md). No physical safety approval yet.

---

## HLT SIM-1 / BrewZilla power priority — 2026-09-19

**Integrated:** read-only simulation with independent 30-second timer, 31 telemetry keys, virtual HLT water temperature/energy/ETA, per-session JSONL and English/Swedish dashboard. BZ has absolute priority. No HLT hardware calls or BZ cap/grant writes; `power_budget_verified=false` and default 2,500 W are hypothetical.

**Observed in the water-only test:** real BZ draw about 2,323–2,356 W, 17 L test water and 11.38 L sparge context; HLT waited with 0 virtual W. Stable settings were wrongly classified stale and explicit `Ramp to 72°C` briefly created a virtual HLT opportunity and simulated overlap near 3.43 kW. Fixes for held settings, eligible-stage allowlist and ramp-step veto were merged/regression-tested, but have not been verified in installed HA. This does **not** establish safe physical HLT arbitration.

```text
[x] Integrate SIM-1 telemetry, traces, cards and tests into common dev (#212)
[x] Preserve SG fermentation and pass combined CI/HACS/Hassfest
[x] Confirm BZ wattmeter and sparge context reach HLT model
[x] Correct stable-setpoint freshness and virtual none UI
[x] Add eligible-stage allowlist and ramp-step veto with tests
[ ] Field-retest ramp, cruise, new ramp, yield, idle with current tagged integration
[ ] Confirm BF/Manual/RAPT stage labels, unknown must fail closed
[ ] Verify real power/temp freshness, JSONL/session/ETA fidelity
[ ] Review learning suggestions separately; never adapt safety policy autonomously
[ ] Identify verified real HLT meter/switch/probe and OFF readback
[ ] Engineer independent fast fail-OFF shedding, dry-fire and circuit protection
[ ] Commission hardware separately before ANY physical HLT output
```

The 30-second HA loop **cannot** protect against overcurrent. Physical HLT work is parked pending an independently reviewed electrical interlock. See [HLT test evidence](hlt-sim1-field-validation-2026-09-19.md), [backend](hlt-dashboard-backend.md), [dashboard](hlt-dashboard-card.md) and [code README](../custom_components/brewassistant/hlt/README.md).

---

## External process-temperature sensor ownership

```text
Heat strike -> Mash -> Mash out -> Sparge -> Pre-boil
  owner = Brewday / BZ; external MASH/process probe
Boil start -> hot side releases probe
Chill -> Transfer -> Cooling/CFC acquires outlet/wort-out if needed
```

BZ internal probe remains kettle temperature. Validate Boil release, absence of competing source ownership, CFC acquisition and coil/manual methods without unnecessary external-probe dependency.

---

## Fermentation targets and GF30

Explicit Brewfather fermentation-schedule metadata may supply `recommended_temperature_c`; an ordinary numeric recipe target must not override SG/manual tracking. Climate Supervisor needs full-cycle testing. SG-driven fermentation work shares the same development baseline and must be preserved. GF30 phase 1 is a parked read-only discovery/normalization scaffold; hardware entity/feature evidence and supervised write architecture are still required. See [`backends/grainfather-fermenter.md`](backends/grainfather-fermenter.md).

---

## Physical timing / Equipment Learning

Read-only ramp/hold/wall/pause duration, delta-T, average °C/min, process source and water-only versus malt context. Later: approved calibration proposals, confidence/evidence, persistence and reversible reset. Learning remains advisory until explicitly accepted; HLT's model is not an adaptive controller. The requested **total Brewday elapsed-time clock** is not included in beta.11.

---

## Cooling / Chill / Transfer

Cooling Runtime v2 supports CFC and immersion-coil/manual-water modeling. Physical checks remain: Boil→Chill ownership, outlet probe, sanitization, coil/internal/manual readings, manually or pump-driven cooling water, pitch readiness and Transfer completion.

---

## Dashboard direction

Modular cards have one responsibility each. Main blocks: `brewassistant_brewday` overview, `brewtracker_runtime`, `rapt_profile_runtime`, `brewzilla_mash_in_controls`, `brewday_operator_actions`, `brewday_details` and `brewfather_recipe`. HLT dashboard cards are read-only standalone and never actuator controls. The runtime-flow layout is currently large and will be compacted separately; dashboard YAML pasted into HA is not updated by HACS integration installation.

---

## Beta.11 prerelease path

Follow [`CONTRIBUTING.md`](../CONTRIBUTING.md) and the [complete Swedish beta.11 release notes](beta11-prerelease-notes_sv.md): `dev` verified → PR #213 `dev -> beta` **merge commit** → verify beta merge SHA + CI/HACS/Hassfest + manifest/interlock → create tag `v0.2.0-beta.11` **from that beta commit**, publish GitHub Pre-release with full Markdown → check actual tag SHA and tagged code → install via HACS for supervised water-only validation → if unsuccessful fix on `dev` and publish NEW beta version. Only consider `beta -> main` and stable release after relevant physical evidence. The incorrectly packaged beta.10 tag remains unchanged and must not be used. HLT SIM-1 is never a physical electrical safety system.
