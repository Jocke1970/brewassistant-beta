# RAPT BrewZilla profile runtime

Status: **feature branch / supervised test required**  
Date: 2026-09-10

## Purpose

BrewAssistant can use an active RAPT BrewZilla profile as the hot-side process
and target source instead of Brewfather Brew Tracker or Manual Brewday.

The important ownership rule is:

```text
RAPT profile / Brew Tracker / Manual Brewday
        -> normalized Brewday Runtime intent
        -> BrewAssistant target + heat + pump logic
        -> RAPT Cloud Link
        -> BrewZilla
```

A RAPT profile is therefore analogous to Brewfather Brew Tracker from the
BrewAssistant controller's point of view. It supplies the current process step,
target temperature and next-step context. It is **not** expected to contain the
heat-utilisation or pump-utilisation strategy that BrewAssistant already owns.

The BrewZilla/RAPT profile runner may still advance the profile steps locally.
BrewAssistant consumes those active-step transitions and continuously applies
its own existing control strategy to the target supplied by that step.

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

## BA control rule

While the RAPT profile is active the control bridge presents the normalized
runtime as an active BrewAssistant control source:

```text
source: RAPT BrewZilla Profile
status: running
runtime_state: running
rapt_profile_role: process_and_target_source
process_executor: rapt_profile_step_runner
control_owner: brewassistant
brewassistant_role: hot_side_controller
target_intent_owner: rapt_profile
heat_pump_owner: brewassistant
direct_brewzilla_control_allowed: true
```

Current RAPT step target is exposed as the normal Brewday Runtime
`target_temperature`. BrewAssistant then transports/reasserts that target to the
BrewZilla and calculates heat/pump behaviour with the same existing hot-side
logic used when Brew Tracker is the process source.

This means a RAPT profile can intentionally omit heat/pump utilisation tuning.
For example:

```text
RAPT active step target = 68 C
  -> Brewday Runtime requested target = 68 C
  -> BA target transport = 68 C
  -> BA Heat Strike / ramp / mash-hold regulator chooses heat utilisation
  -> BA chooses pump state/utilisation
  -> RCL writes those values to BrewZilla
```

If the RAPT runner writes its own default heat/pump values on a step transition,
BrewAssistant sees the readback difference and may reassert the current BA
desired values on the next control pass.

## RAPT step semantics

Explicitly named RAPT steps are preferred because names such as `Heat Strike`,
`Mash`, `Mash Out`, `Boil` and `Whirlpool` give BrewAssistant the strongest
process context.

For generic RAPT names such as `Step 1`, the bridge provides conservative
fallback semantics:

```text
endType Temperature / controlType Ramp -> Mash ramp
endType Duration                       -> Mash hold
>=95 C temperature/duration target     -> Boil heat/hold
```

Those normalized words intentionally feed the existing BrewAssistant
`stage_kind`, Heat Strike, ramp, mash-hold, thermal-mix and pump logic rather
than creating a second RAPT-specific regulator.

During the pre-mash-in phase an active RAPT profile receives the same physical
phase authority as Brew Tracker: once the profile itself is active, BA's
Heatstrike/Mash-In controller can modulate target/heat/pump without asking for a
new generic confirmation on every small regulator write. Lower ABORT, safety,
freshness and fail-passive guards remain installed.

Outside that dedicated physical phase, RAPT profile-driven positive actions use
the same supervised control-policy class as Brew Tracker.

## Source loss

If RAPT Cloud Link becomes missing, restored-only, unknown or unavailable after
BrewAssistant has observed an active profile, BrewAssistant keeps the RAPT
runtime handoff with:

```text
runtime_state: source_unavailable
```

It does **not** silently fall back to Brewfather or Manual Brewday and it does
not infer STOP from stale/missing data. New BA positive writes are blocked by
the existing fail-passive path; BrewZilla keeps the last locally applied target
and output configuration until communication returns or an explicit safety path
acts.

## Confirmed STOP and safe-off

A profile STOP is confirmed only when BrewAssistant has previously observed an
active RAPT profile and receives a fresh operational RCL binary-sensor state of
`off`. Restored state is not accepted as STOP evidence.

On confirmed STOP BrewAssistant automatically clears old BA-owned utilisation
state and sends the safe-off commands:

```text
switch.brewzilla_heater           -> OFF
switch.brewzilla_pump             -> OFF
number.brewzilla_heat_utilization -> 0 %
number.brewzilla_pump_utilization -> 0 %
```

This is required because live testing showed that RAPT can end a profile while
leaving BrewZilla's generic target and heater-enabled state behind.

After safe-off BrewAssistant keeps an in-memory RAPT STOP handoff guard. It does
not immediately switch to an already-running Brewfather source. A new RAPT
profile clears the guard automatically. An explicit Manual Brewday
positive-control action may release a confirmed STOP guard and take manual
ownership; it cannot release an active or unavailable-after-active RAPT handoff.

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
`activeProfile*` fields, not the command response alone, are the runtime truth.

## Supervised test checklist

1. Install/update RCL from `ba/brewassistant-rapt-cloud-link`.
2. Install BrewAssistant from `feature/rapt-brewzilla-profile-runtime`.
3. With no profile running, verify normal Brewfather/Manual behaviour is
   unchanged.
4. Start a harmless RAPT test profile. It does not need meaningful heat/pump
   utilisation values; keep the first target conservative for the physical test.
5. Verify Brewday Runtime source becomes `RAPT BrewZilla Profile` and state
   becomes `running`.
6. Verify current step, next step and requested target follow BrewZilla profile
   step changes.
7. Verify BA writes/reasserts the RAPT step target and chooses heat/pump
   utilisation from the existing BA regulator rather than requiring those values
   from the RAPT profile.
8. Verify a temperature-ended generic step is interpreted as a ramp and a
   duration-ended generic step as a hold; explicitly named steps should retain
   their stronger semantic meaning.
9. Temporarily reload/disconnect RCL and verify runtime becomes
   `source_unavailable` without switching to Brewfather and without accidental
   safe-off.
10. Restore RCL and verify the same RAPT profile resumes as source and BA control
    resumes from current readback.
11. Stop the profile locally or via the RCL end service.
12. Wait for fresh RCL `off` and verify all four safe-off values are applied.
13. Verify Brewday Runtime remains on the stopped RAPT handoff rather than
    silently adopting an already-active Brewfather tracker.

## Known first-pass limits

- The handoff guard is in memory; a full Home Assistant/BrewAssistant restart
  clears it. An actually active RAPT profile is rediscovered from RCL after
  restart.
- RAPT step `length` is exposed as raw metadata but is not assumed to be a
  reliable countdown for all step end types.
- Generic step semantic inference is intentionally conservative; meaningful
  profile step names remain preferable.
- BrewAssistant does not yet expose a profile selector or its own Start/Stop
  profile buttons; the RCL services are the initial command surface.
- Operator ABORT while a RAPT profile is running still needs an explicit
  integration test before this feature is merged to `main`; remote profile
  termination must be included in that safety path before unsupervised use.
