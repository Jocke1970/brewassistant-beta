# Physical validation — 2026-08-30

Status: **two controlled water-only regression runs completed; phase authority restored, final-approach defect found and fixed in #179 pending revalidation**.

Context:

- Brewfather Brew Tracker
- Water-only context
- BrewZilla hot-side physical validation
- external mash/process temperature gate active
- second run used 17 L effective test-water context

---

## First regression run — control-authority failures

The first run was intentionally aborted before Mash-In completion because control/UI semantics were no longer trustworthy enough to continue.

### What still worked

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

### Regression 1 — Supervised Apply was below the physical controller

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

### Regression 2 — Brewday Advice competed with Heatstrike

Near strike, Clean Heatstrike intentionally requested low heat while Brewday Advice created an actionable recommendation to raise heat to 70% based on the source schedule / learning phase.

During controller-owned Heatstrike/Mash-In:

```text
Advice may observe
Advice may learn
Advice may report diagnostics
Advice must not expose APPLY for controller-owned heat/pump
Advice must not send a conflicting actionable notification
```

### Regression 3 — physical ramp timing followed source pause

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

---

## Fixed architecture after the first run

For Brewfather Brew Tracker:

```text
Brewfather PLAY
    -> authorizes Heatstrike physical controller

Heatstrike / pre-Mash-In
    -> Clean Heatstrike owns target + heat + pump
    -> no generic BEKRÄFTA for internal modulation
    -> hard safety / ABORT / explicit safe-down still outrank controller
    -> Advice is observe-only

Strike ready
    -> operator notification / Mash-In Started gate only
    -> NOT a release of Heatstrike target/heat authority

Mash-In Started
    -> explicit physical transition
    -> pump OFF while malt is added
    -> strike target released to effective mash target / anti-drop logic

Mash-In Complete
    -> Heatstrike/Mash-In authority ends
    -> mash circulation resumes
    -> later genuinely new positive process authority may use Supervised Apply
```

Behavioral reference for Heatstrike itself is PR #109 / commit `6b2241c` (`Make heat-strike control physically dominant`). This validation does **not** justify rolling back unrelated later safety, ABORT, dashboard or ownership work.

---

## Second water-only run — phase authority restored

The follow-up run used the phase-authority and #157 timing fixes. The Flight Recorder was manually cleared during the run to keep the final Heatstrike/Mash-In evidence compact, so the first seconds around Brewfather Play are preserved primarily by screenshots rather than the retained log.

### Physical PASS observations

```text
✅ Brewfather Play started physical Heatstrike directly
✅ no duplicate generic BEKRÄFTA was required for Heatstrike start
✅ Heatstrike autonomously modulated heat and pump
✅ pump modulation to stronger mixing did not create a new generic confirmation
✅ Advice remained controller-owned / non-actionable
✅ #157 physical ramp continued while Brewfather later changed to paused mash-additions
✅ #157 showed pause 00:00 while physical Heatstrike continued
✅ 71.8°C physical strike target stayed latched after Brewfather exposed the later 66°C mash target
✅ explicit zero-heat safe-down was physically applied when Clean Heatstrike requested it
✅ final operator ABORT produced heater OFF / pump OFF / heat 0 / pump 0 and hardware lockout
```

Representative retained Flight Recorder sequence:

```text
61.3°C readiness / 68.59°C hottest view
  -> Clean Heatstrike 25%, pump 90%

63.1°C readiness / 69.58°C hottest view
  -> Clean Heatstrike 10%, pump 100%

67.9°C readiness / 70.93°C hottest view
  -> old Clean Heatstrike final coast 0%, heater OFF, pump 100%

Brewfather then pauses on 31 min, mäsktillsatser / next Hold 66°C
  -> physical strike target remains 71.8°C
  -> Heatstrike remains pre-Mash-In controller
```

### Regression 4 — final coast could park below strike

The second run exposed a narrower Heatstrike defect.

At the critical point:

```text
strike target: 71.8°C
readiness/mash view: 67.9°C
hottest/internal view: 70.93°C
hottest delta: 0.87°C below target
old safety profile: <=1.0°C -> 0% / heater OFF
pump: 100%
```

The old 1.0°C permanent-coast threshold was wider than the physical readiness tolerance used by #157 and Mash-In readiness (`±0.3°C`). If thermal momentum ended inside that gap, Heatstrike had no way to add low heat again until the vessel fell more than 1.0°C below target.

This was a real process-control dead zone:

```text
Heatstrike says final coast
#157 says target not reached
Mash-In readiness says target not reached
no low heat available
```

The run was intentionally ABORTED rather than waiting indefinitely for passive thermal drift.

---

## #179 — final approach / maintained strike-ready hold

PR #179 changes only the final Heatstrike capture band and clarifies the existing Mash-In READY contract.

New Heatstrike behavior:

```text
>10°C below strike: 100%
8–10°C: 75%
5–8°C: 50%
3–5°C: 25%
0.3–3°C: 10%
within ±0.3°C readiness band: 0% coast
at/over strike: safety 0% / heater OFF
```

If temperature drifts below the ±0.3°C readiness band while the operator has not started Mash-In, 10% heat becomes available again. Therefore `ready_for_mash_in` is a maintained strike-temperature state rather than a one-shot target event.

Existing Mash-In target patch semantics remain authoritative:

```text
ready_for_mash_in
  -> inherit Heatstrike target + heat logic
  -> pump remains ON/circulating at the ready-state circulation level
  -> wait indefinitely for operator if necessary

Mash-In Started
  -> explicit release boundary
  -> pump OFF / pump utilization 0
  -> strike target released to effective mash target
  -> anti-drop heat logic may operate only when mash temperature is below that target

Mash-In Complete
  -> circulation resumes
  -> pre-Mash-In phase authority ends
```

#179 also corrects the ready notification so it no longer claims the pump is already paused before Mash-In Started.

---

## Follow-up / release-gate validation

- #175 / phase-authority behavior is physically PASS in the second run.
- #157 source-pause decoupling is physically PASS in the second run; target-reach/hold behavior still needs completion.
- #179 is code/CI PASS and requires one focused physical revalidation before beta release.

Required next water-only checkpoints:

```text
[x] Play starts Heatstrike without generic BEKRÄFTA
[x] far Heatstrike applies target / heat / pump autonomously
[x] near-target taper and pump equalization produce no generic BEKRÄFTA
[x] Brewfather mash-additions pause does not pause physical ramp timing
[x] Advice remains non-actionable while Heatstrike/Mash-In owns IO
[ ] final approach reaches the ±0.3°C strike-ready band without parking low
[ ] strike-ready coast goes to 0% inside the band
[ ] if waiting causes drift below the band, low heat re-enters automatically
[ ] READY keeps strike target/heat active until Mash-In Started
[ ] Mash-In Started: pump OFF / utilization 0 and strike target released
[ ] Mash-In Complete: circulation resumes and phase authority ends cleanly
[ ] #157 records completed Heatstrike ramp and begins first 66°C hold only after physical target + Mash-In gate
[ ] later 66 -> 72°C ramp is recorded separately
[x] ABORT remains OFF/OFF/0/0 with ownership lockout
```
