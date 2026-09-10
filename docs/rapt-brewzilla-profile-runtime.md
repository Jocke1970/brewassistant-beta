# RAPT BrewZilla profile runtime

Status: **feature branch / supervised test required**  
Date: 2026-09-10

## Purpose

BrewAssistant can use a locally executing RAPT BrewZilla profile as the
hot-side process runtime instead of Brewfather Brew Tracker or Manual
Brewday. The BrewZilla remains the profile executor; BrewAssistant observes
and supervises it through the BrewAssistant RAPT Cloud Link branch.

## Runtime ownership

Source priority is:

```text
operator ABORT
  -> RAPT BrewZilla profile / RAPT handoff guard
  -> actually started Brewfather Brew Tracker
  -> Manual Brewday
  -> idle
```

An active RAPT profile therefore outranks Brewfather even when Brewfather is
still available as recipe metadata or as a background Brew Tracker source.
BrewAssistant does not combine process steps from the two sources.

The RAPT runtime adapter consumes the operational RCL binary sensor marked:

```text
ba_source: rapt_cloud_link_brewzilla_profile_runtime
```

The expected default entity is:

```text
binary_sensor.brewzilla_profile_active
```

The adapter also supports discovery by the `ba_source` marker if the device
name causes Home Assistant to generate another entity id.

## Local executor rule

While the RAPT profile is active the normalized Brewday Runtime reports:

```text
source: RAPT BrewZilla Profile
status: running
runtime_state: external_executor
process_executor: brewzilla_local_profile_runner
brewassistant_role: supervisor
direct_brewzilla_control_allowed: false
```

`external_executor` is intentionally not one of BrewZilla orchestration's
positive direct-control runtime states. This prevents BrewAssistant target,
heater, pump and utilisation logic (including previously remembered
BA-owned Advice utilisation) from fighting the local BrewZilla profile
runner.

Current and next profile step data are normalized into Brewday Runtime. Step
target temperature is exposed as `target_temperature`, but BrewAssistant
observes it rather than writing it back to the BrewZilla while the local
profile runner owns execution.

## Source loss

If RAPT Cloud Link becomes missing, restored-only, unknown or unavailable
after BrewAssistant has observed an active profile, BrewAssistant keeps the
RAPT runtime handoff with:

```text
runtime_state: source_unavailable
```

It does **not** silently fall back to Brewfather or Manual Brewday and it
does not infer STOP from stale/missing data.

## Confirmed STOP and safe-off

A profile STOP is confirmed only when BrewAssistant has previously observed
an active RAPT profile and receives a fresh operational RCL binary-sensor
state of `off`. Restored state is not accepted as STOP evidence.

On confirmed STOP BrewAssistant automatically clears old BA-owned
utilisation state and sends the safe-off commands:

```text
switch.brewzilla_heater          -> OFF
switch.brewzilla_pump            -> OFF
number.brewzilla_heat_utilization -> 0 %
number.brewzilla_pump_utilization -> 0 %
```

This is required because live testing showed that RAPT can end a profile
while leaving BrewZilla's generic target and heater-enabled state behind.

After safe-off BrewAssistant keeps an in-memory RAPT STOP handoff guard. It
does not immediately switch to an already-running Brewfather source. A new
RAPT profile clears the guard automatically. An explicit Manual Brewday
positive-control action may release a confirmed STOP guard and take manual
ownership; it cannot release an active or unavailable-after-active RAPT
handoff.

## RCL command surface

The BrewAssistant RAPT Cloud Link branch exposes:

```text
rapt_cloud_link.start_brewzilla_profile
rapt_cloud_link.end_brewzilla_profile
```

The implementation mirrors the RAPT Portal requests observed live on
2026-09-10:

```text
POST /api/ProfileSessions/StartProfileSession
GET  /api/ProfileSessions/EndBrewZillaProfileSession?brewZillaId=...
```

After either command RCL requests a fresh `GetBrewZillas` update. The live
`activeProfile*` fields, not the command response alone, are the runtime
truth.

## Supervised test checklist

1. Install/update RCL from `ba/brewassistant-rapt-cloud-link`.
2. Install BrewAssistant from `feature/rapt-brewzilla-profile-runtime`.
3. With no profile running, verify normal Brewfather/Manual behavior is
   unchanged.
4. Start a harmless RAPT test profile with low/zero utilisation.
5. Verify Brewday Runtime source becomes `RAPT BrewZilla Profile` and state
   becomes `external_executor`.
6. Verify current step, next step and target follow BrewZilla step changes.
7. Verify BrewAssistant orchestration does not write target/heat/pump while
   the profile is active.
8. Temporarily reload/disconnect RCL and verify runtime becomes
   `source_unavailable` without switching to Brewfather and without safe-off.
9. Restore RCL and verify the same RAPT profile resumes as source.
10. Stop the profile locally or via the RCL end service.
11. Wait for fresh RCL `off` and verify all four safe-off values are applied.
12. Verify Brewday Runtime remains on the stopped RAPT handoff rather than
    silently adopting an already-active Brewfather tracker.

## Known first-pass limits

- The handoff guard is in memory; a full Home Assistant/BrewAssistant restart
  clears it. An actually active RAPT profile is rediscovered from RCL after
  restart.
- RAPT step `length` is exposed as raw metadata but is not assumed to be a
  reliable countdown for all step end types.
- BrewAssistant does not yet expose a profile selector or its own Start/Stop
  profile buttons; the RCL services are the initial command surface.
- Operator ABORT while a local RAPT profile is running still needs an explicit
  integration test before this feature is merged to `main`; remote profile
  termination must be included in that safety path before unsupervised use.
