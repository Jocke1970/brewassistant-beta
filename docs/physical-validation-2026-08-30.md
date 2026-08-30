# Physical validation — 2026-08-30

Status: **ABORTED regression run — actionable control-authority failures found**.

Context:

- Brewfather Brew Tracker
- Water-only context
- BrewZilla hot-side physical validation
- external mash/process temperature gate active
- test intentionally aborted before Mash-In completion because control/UI semantics were no longer trustworthy enough to continue

## What still worked

The Clean Heatstrike physical calculation remained coherent. During the run it:

- held the strike target at 71.8 °C while Brewfather later paused on mash additions;
- used the mash/BLE view as the readiness gate;
- used the hotter internal/wort view to cap heat near strike;
- reduced heat from the far-ramp value toward 25/10% near strike;
- increased pump mixing toward 90/100% when the mash/wort temperature split grew;
- preserved the 71.8 °C physical strike target while the source schedule had already exposed the later 66 °C mash target.

The operator ABORT path also passed:

```text
Brewday Runtime -> aborted
heater -> OFF
pump -> OFF
heat utilization -> 0
pump utilization -> 0
operator ownership lock -> active
```

## Regression 1 — Supervised Apply was below the physical controller

The run showed generic Supervised Apply treating internal Heatstrike modulation as new positive operator intent.

Example sequence:

```text
Heatstrike physical controller requests stronger mixing
pump 70 -> 90/100%
-> generic BEKRÄFTA appears
-> operator confirms
-> source/runtime context changes while physical Heatstrike continues
-> confirmed plan rejected as supervised_plan_stale:live_plan_changed
-> another pending confirmation may appear
```

This is the wrong abstraction boundary. The operator should authorize **new control authority / a new physical phase**, not every register adjustment made by an already-authorized controller.

## Regression 2 — Brewday Advice competed with Heatstrike

Near strike, Clean Heatstrike intentionally requested low heat while Brewday Advice created an actionable recommendation to raise heat to 70% based on the source schedule / learning phase.

During controller-owned Heatstrike/Mash-In:

```text
Advice may observe
Advice may learn
Advice may report diagnostics
Advice must not expose APPLY for controller-owned heat/pump
Advice must not send a conflicting actionable notification
```

## Regression 3 — physical ramp timing followed source pause

The first #157 implementation started a ramp timer when a ramp candidate appeared in the normalized source schedule, before the physical hardware actuation necessarily began.

It also froze the ramp whenever:

```text
runtime_state == paused
```

Brewfather legitimately paused at `31 min, mäsktillsatser` while physical Heatstrike was still heating/mixing. The UI therefore showed `ramp_paused` even though the physical process continued.

Required timing model:

```text
source schedule = diagnostic context
physical controller = timing authority

ramp timer starts when physical target/actuation is observed
Brewfather event-step pause does not freeze an active physical ramp
ABORT stops timing
mash hold starts only after actual process target reach and Mash-In Complete
```

## Fixed architecture after this run

For Brewfather Brew Tracker:

```text
Brewfather PLAY
    -> authorizes Heatstrike physical controller

Heatstrike / pre-Mash-In
    -> Clean Heatstrike owns target + heat + pump
    -> no generic BEKRÄFTA for internal modulation
    -> hard safety / ABORT / explicit safe-down still outrank controller
    -> Advice is observe-only

Mash-In
    -> dedicated Mash-In operator state machine
    -> no duplicate generic confirmation inside the transition

Mash-In Complete
    -> Heatstrike/Mash-In authority ends
    -> later genuinely new positive process authority may use Supervised Apply
```

Behavioral reference for Heatstrike itself is PR #109 / commit `6b2241c` (`Make heat-strike control physically dominant`). This validation does **not** justify rolling back unrelated later safety, ABORT, dashboard or ownership work.

## Follow-up

- #175 tracks/restores Heatstrike physical phase authority around generic Supervised Apply.
- #157 is reopened for physical timing semantics.
- Next physical test must begin from a clean ABORT/rearm state and verify one checkpoint at a time.

Required next water-only checkpoints:

```text
[ ] Play starts Heatstrike without generic BEKRÄFTA
[ ] far Heatstrike applies target / heat / pump autonomously
[ ] near-target taper and pump equalization produce no generic BEKRÄFTA
[ ] Brewfather mash-additions pause does not pause physical ramp timing
[ ] Advice remains non-actionable while Heatstrike/Mash-In owns IO
[ ] strike-ready / Mash-In dedicated controls appear at the correct physical gate
[ ] after Mash-In Complete, generic confirmation is available only for genuinely new positive process authority
[ ] 66 °C hold timer starts on actual process target reach
[ ] later 66 -> 72 °C ramp is recorded separately
[ ] ABORT remains OFF/OFF/0/0 with ownership lockout
```
