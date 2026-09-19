# Roadmap — current beta.12 candidate and retained beta.11 history

> [!IMPORTANT]
> **Current development decision after PR #215 (2026-09-19):** The source-scoped controller is now merged into `dev`, but is **not installed, physically validated or released as beta.12**. The beta.11 failure and previous proposed all-passive architecture below remain historical evidence; they do not override the current code/source contract. No hardware test is allowed from `dev`. See [beta.12 release notes](beta12-prerelease-notes_sv.md) and [beta-first validation](beta-first-physical-validation-2026-09-19_sv.md).
>
> **Input is not actuation:** RAPT is the sole selected BA brewing **input** for steps/target/timing; BA may control BrewZilla through RCL only through the live RAPT source/step, safety and Supervised Apply gates. RAPT advances its own profile steps. BF and BT share Brewfather upstream, remain readable/displayable and cannot affect RAPT brewing decisions; BF fermentation is independent. BT as selected brewing source is observer-only for BA hot-side writes. Manual retains its existing policy. RAPT loss/STOP/ABORT must never imply physical OFF or automatically choose BT. The alternative design where BA is entirely read-only and RAPT controls all physical outputs is **not the architecture implemented by #215**.
>
> **Current promotion work:** [#215](https://github.com/Jocke1970/brewassistant-beta/pull/215) merged to `dev` with `64bd1a69d25e319a18c38d087921d0ba039ee076`; CI, HACS and Hassfest are green on that exact SHA. [#216](https://github.com/Jocke1970/brewassistant-beta/pull/216) is the separate `dev → beta` promotion; its final diff and merge-commit checks must pass before a new immutable `v0.2.0-beta.12` prerelease, displayed as `2026_09-01`, can be published. Verify the tag's exact beta SHA, tagged manifest and HACS version **before** supervised water-only testing. Any fix requires a new beta version; never retarget an old tag. Do not promote to `main` without field evidence and explicit approval.
>
> **Post-installation acceptance, not claimed as passed:** verify actual RCL source/session/step and temperature target, readback and local heater/pump state, old pending plans, loss/STOP/ABORT, EN/SV Lovelace cards and HLT-only simulation. Start read-only/observer with operator present. If RAPT's active Sparge target is 78 °C or missing while BA proposes 95 °C, positive preboil heating **must remain blocked**; no artificial target or bypass. Independently confirm sufficient water and safe physical output state before any positive command. No malt, unattended or physical HLT use authorized by an automated green check.

---

## Historical beta.11 incident and previously proposed passive architecture (preserved)

The following content records the 2026-09-19 beta.11 operating pause and the design then proposed. Its historical instructions remain evidence, not current beta.12 design or permission to run dev physically.

# Roadmap

BrewAssistant's Python integration owns runtime/diagnostics and presently contains actuator-control paths; dashboard YAML displays data and can invoke operator actions. **As of 2026-09-19, the hot-side actuator feature is paused, not accepted for physical use.** This is an operational decision/documentation update, **not** an implemented monitor-only code guard.

> [!CAUTION]
> **Read [the 2026-09-19 BA pause + RAPT handoff](ba-hot-side-pause-and-rapt-handoff-2026-09-19_sv.md) first.** The beta.11 water-only retest was aborted: Mash-In gate remained `idle`, the interlock went `recovery_required` without a physical target, and the independent timer presented a 66 °C hold. While BA blocked new writes, pump and heater remained ON in an operator snapshot. Do not run new BA-controlled physical tests or assume RAPT-alone control while this BA integration still has actuator write paths. Verify physical device status locally.

## Current decision and highest-priority tasks

```text
[DECIDED] Suspend BA actuator testing and accept the beta.11 water-only retest as FAILED / aborted.
[DECIDED] Keep RAPT Cloud Link feature design and execution in its separate chat.
[TARGET]  RAPT/BrewZilla owns hot-side profile and temperature; BA observes only.
[NOT DONE] A central verified BA monitor-only / external-owner actuator-write boundary.
[NOT DONE] Safe installation of RAPT + passive BA together.
[NOT DONE] Permission for BA to resume hot-side actuator control.
```

Prioritized work **within this BA repository**:

1. Inventory every existing actuator write path: orchestrator, phase authority, profile bridge, direct/supervised Apply, ownership/reassert, STOP/ABORT, buttons/services, startup/reload and cooling handoff. Define and implement a *central fail-closed write boundary* for an external RAPT controller. A status label or hidden card is not an interlock. Define safety-command ownership deliberately rather than disabling emergency functions blindly.
2. Prove with automated tests that BA emits **zero** hot-side writes in passive mode at startup, normal steps, pause/resume, source transitions, cloud loss/recovery, abort and reload; test it in HA with no active/heated equipment before enabling coexistence.
3. Preserve passive sensors, Brewday Flight Recorder, physical timing (clearly labeled as telemetry), efficiency/Equipment Learning and unrelated modules without requiring hot-side control ownership. Confirm what is unavailable if the actuator integration is disabled.
4. Make gate/timer/authoritative target status non-contradictory; fix false `recovery_required` classification and rebuild the oversized SV/EN runtime-flow cards only after safe isolation. Preserve the evidence from this field failure and add targeted regressions.
5. Sync only the **verified** RAPT control interface and ownership decisions from the dedicated RAPT chat. Do not develop competing RAPT controller logic in this BA workstream.
6. Consider returning BA to active control only as a separately reviewed design with passing regression, correct release flow and supervised water-only acceptance. Malt or unattended running requires additional appropriate evidence; currently neither is approved.

There is no new BA hot-side prerelease scheduled just to apply this documentation. `beta`/`main` and published beta.11 remain untouched by documentation-only `dev` updates.

---

## Historical release / branch state

The permanent branch process is:

```text
dev (development) -> beta (integrated test and GitHub prerelease) -> main (validated/stable)
```

Promote `dev -> beta` with a PR and **Create a merge commit**, never squash/rebase; verify CI/HACS/Hassfest on *beta merge SHA*, then create/tag the prerelease from that exact beta commit. Confirm the tag's true SHA, manifest and critical tagged files. Any later fix gets a **new** version, never a moved published tag. Only promote `beta -> main` after suitable validation. See [`CONTRIBUTING.md`](../CONTRIBUTING.md).

On September 19, PR [#213](https://github.com/Jocke1970/brewassistant-beta/pull/213) merged `dev` to `beta`, producing `c989cde6dbebe769c2f4ff9575c78b532718f8eb`. [v0.2.0-beta.11](https://github.com/Jocke1970/brewassistant-beta/releases/tag/v0.2.0-beta.11) is a published prerelease whose tag, tagged version `0.2.0-beta.11` and Mash-In interlock installation were checked. **Its installed physical-control acceptance failed.** The older beta.10 tag contains the wrong code and must never be reused; both published tags remain immutable by policy. GitHub merges/releases never automatically update HA or manually pasted dashboard YAML.

Earlier development milestones (historical, not new deployment approval):

```text
2026-08-29 ownership / ABORT validation
2026-08-31 Heatstrike / Mash-In regression work
2026-09-05 gradient and handoff fixes
2026-09-06 physical Heatstrike / Mash-In runs
2026-09-11 RAPT profile runtime integrated
2026-09-11 BrewTracker zero-minute PAUS checkpoint and BF schedule improvements
2026-09-11 Grainfather GF30 read-only scaffold parked
2026-09-17 SG-driven fermentation development
2026-09-19 read-only HLT SIM-1 merged (#212)
2026-09-19 physical mash interlock coding/regressions
2026-09-19 beta.11 released, water-only retest ABORTED, BA active hot-side parked
```

The earlier accidental main-based feature work was reconciled to `dev` via PRs #205/#204/#206, and HLT work via #212. Do not create replacement branches or retroactively relabel historical evidence. Old [physical validation 2026-08-31](physical-validation-2026-08-31.md), [2026-09-05](physical-validation-2026-09-05.md), [2026-09-06](physical-validation-2026-09-06.md), [HLT field evidence](hlt-sim1-field-validation-2026-09-19.md) and the [original Mash-In test plan](physical-mash-test-plan-2026-09-19_sv.md) are evidence/old plans, **not** current instructions to restart testing.

---

## Brewday Runtime and source/ownership architecture

**Implemented in code, independently validated to differing degrees:** custom integration/coordinator; normalized runtime; Brewfather RAW Brew Tracker timeline and positive-start ownership; manual/Brewfather exclusion; stage engine; persistent audit/Flight Recorder; diagnostic distinction among recipe/current/effective/device targets; operator ABORT latch; RAPT profile runtime source; BrewTracker PAUS checkpoint; recipe/planning presentation; physical ramp/hold timing; HLT simulator as a read-only consumer.

Historical BA control model:

```text
Brewfather Brew Tracker / Manual / RAPT profile -> BA runtime and guards
  -> BA target / heater / pump writes -> RAPT Cloud Link -> BrewZilla
```

**Intended future model, not implemented:**

```text
RAPT profile -> RAPT/BrewZilla owns actual process / temperature
                       ↓ read-only measurements
BA -> status / audit / timing / passive learning, no actuator writes
```

A Brewfather PAUS/0-minute checkpoint should freeze source progress while physical current-target conditions are handled. A source step transition is not physical proof, but the current BA controller has not passed the relevant 66→72 °C field acceptance. Do not run source/phase handoff physically until redesigned. See [`brewday-execution-modes.md`](brewday-execution-modes.md) and [`brewday-brewzilla.md`](brewday-brewzilla.md).

### RAPT profile runtime: WARNING – historical active-controller adapter

The existing [`rapt-brewzilla-profile-runtime.md`](rapt-brewzilla-profile-runtime.md) and implementation [`brewzilla_rapt_profile_control_bridge.py`](../custom_components/brewassistant/brewzilla/brewzilla_rapt_profile_control_bridge.py) specify `control_owner: brewassistant` / `heat_pump_owner: brewassistant`; BA can reassert heat/pump/target after RAPT steps. They describe the **old BA-controlled RAPT-directive design**, not the new external-controller plan. Source-loss semantics may leave BrewZilla running at its last local state. Selecting RAPT as a source without isolating all BA writes is **not** safe proof of a single controller. Design/validation of the actual RAPT standalone control proceeds in the RAPT chat.

---

## BrewZilla hot side — code present; control use parked

The implementation includes physical/process/kettle temp roles, Heatstrike and Mash-In gate, staged pump interlock, local regulation, RCL report-age freshness, supervised/direct Apply, manual ownership, hardware/operator ABORT and positive-action lockouts. A green unit test indicates a code path was exercised, not that it controls the connected hardware safely.

The designed Mash-In contract is: READY → Started → mash target and pump OFF → Brewfather PAUSED then RUNNING or manual Complete → 10-min settling with pump OFF → operator-authorized ~25 % → five minutes after device readback → separately authorized ~50 %, while the physical hold should prevent early next target. **Do not execute this on beta.11:** the field attempt produced `gate idle` + `recovery_required`, with no latched physical target even when the timing display showed `Hold 66 °C`. The `recovery_required` classifier can treat an empty interlock state plus a late Brewfather step as a restart without explicitly observing a restart. Treat this as a plausible defect, not a fully established root cause. Details and observations: [BA incident checkpoint](ba-hot-side-pause-and-rapt-handoff-2026-09-19_sv.md).

The process probe (external MASH) is the intended process-readiness authority, BZ internal/WORT is kettle/safety context. Brewday/BZ historically owns the extra probe until Boil, with CFC outlet ownership during Chill/Transfer. Passive ownership needs redesign so displaying temperature never grabs control authority. Hardware ABORT, operator ownership ABORT, and `recovery_required` are distinct; BA stopping writes cannot guarantee physical outputs OFF.

### Re-entry gate (no current physical test)

```text
[ ] Independent review of every hot-side write path and external-owner state
[ ] Central no-write barrier + tests across all BA actions, services, startup/reload
[ ] Safe passive BA + independently running RAPT verified without heated hardware
[ ] Consistent physical step, Mash-In gate, target and timer state
[ ] Root cause of incorrect recovery classification documented and regressed
[ ] Explicit approval of any separate BA control design
[ ] New beta candidate via dev -> beta and full prerelease identity checks
[ ] Supervised water-only verification, then separately assess real mash
```

The previous water-only test plan stays as a historical test artifact, not a go-ahead.

---

## HLT SIM-1 / power priority — strictly simulated

On `dev`, the simulator offers its own 30-second timer, read-only telemetry, virtual water temperature/energy/ETA, JSONL and dashboard. BZ absolute priority in this hypothetical model does **not** imply electrical protection. Real and virtual watt/temp are kept separate; No Sparge stays idle and unknown stages fail closed.

Earlier water test saw approximately 2,323–2,356 W BZ power, 17 L test water and 11.38 L sparge volume, while stable setpoints and ramp stage detection exposed issues later fixed in code. Those fixes still need a **read-only HA retest**, not a real HLT activation. The 30-second loop cannot protect a physical circuit: independent fast fail-OFF, dry-fire, real meter/switch and electrician-reviewed design are prerequisites before any HLT output. [HLT evidence](hlt-sim1-field-validation-2026-09-19.md), [backend](hlt-dashboard-backend.md), [dashboard](hlt-dashboard-card.md), [HLT README](../custom_components/brewassistant/hlt/README.md).

---

## Other BrewAssistant modules and deferred work

- **Fermentation:** SG-driven development and Brewfather fermentation schedule metadata; Climate Supervisor requires full-cycle validation. Preserve this separate workstream rather than changing it as part of hot-side retirement.
- **Grainfather GF30:** parked, read-only discovery scaffold; hardware evidence and a separately reviewed write architecture needed before control.
- **Cooling / CFC / coil:** model exists; Boil→Chill ownership, sanitize, outlet probe, pump/water method and Transfer need validation. Do not accidentally allow cooling to bypass the new external-controller write boundary.
- **Physical timing / Equipment Learning:** read-only ramp/hold/wall/pause, delta-T, average °C/min and water/malt context; labels must not imply a physical operator confirmation. Passive learning only until explicitly accepted. Total Brewday elapsed clock not in beta.11.
- **Dashboard:** separate Brewday overview, BrewTracker and RAPT status, Mash-In controls, operator actions, HLT SIM-1. Current runtime-flow timer and malt icons are oversized; layout should be compacted after ownership isolation. Pasted HA YAML is not updated by HACS.
- **External sensor:** previous hot-side → Boil release → Cooling/CFC Chill/Transfer role boundary needs revalidation under the passive hot-side architecture.

**BA-side checkpoint:** [2026-09-19 paused control and RAPT handoff](ba-hot-side-pause-and-rapt-handoff-2026-09-19_sv.md). **RAPT implementation continues exclusively in its dedicated chat.**
