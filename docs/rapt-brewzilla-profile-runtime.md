# RAPT BrewZilla profile runtime

Status: **feature branch / supervised physical test required**  
Date: 2026-09-10

## Purpose

BrewAssistant can use an active RAPT BrewZilla profile as the hot-side process
and target source instead of Brewfather Brew Tracker or Manual Brewday.

The ownership model is:

```text
RAPT profile / Brew Tracker / Manual Brewday
        -> normalized Brewday Runtime intent
        -> BrewAssistant target + heat + pump logic
        -> RAPT Cloud Link
        -> BrewZilla
```

A RAPT profile is therefore analogous to Brewfather Brew Tracker from the
BrewAssistant controller's point of view. It supplies process directives such as
the current step, target temperature, duration/end condition and next-step
context. RAPT profile heat/pump utilisation values are metadata only; they are
not the BrewAssistant control strategy.

## Source and control ownership

Automatic source priority is currently:

```text
operator ABORT
  -> active/held RAPT BrewZilla profile
  -> actually started Brewfather Brew Tracker
  -> Manual Brewday
  -> idle
```

An active RAPT profile therefore outranks Brewfather even if Brewfather remains
available for recipe metadata. BrewAssistant does not mix process steps from two
active sources.

The long-term source UI model is `Auto / RAPT / Brewfather / Manual`. The
explicit selector is intentionally deferred until after physical validation;
the feature branch currently implements the automatic arbitration above.

The RAPT adapter consumes the RCL binary sensor marked:

```text
ba_source: rapt_cloud_link_brewzilla_profile_runtime
```

Expected default entity:

```text
binary_sensor.brewzilla_profile_active
```

## BA control rule

During a normal active RAPT hot-side step the normalized runtime exposes RAPT as
the directive source and BrewAssistant as controller:

```text
source: RAPT BrewZilla Profile
runtime_state: running
process_source: rapt_cloud_link
directive_source: rapt_profile
control_owner: brewassistant
transport: rapt_cloud_link
hardware_executor: brewzilla
rapt_profile_role: process_and_target_source
target_intent_owner: rapt_profile
heat_pump_owner: brewassistant
```

The current RAPT step target becomes the normal Brewday Runtime target.
BrewAssistant transports/reasserts that target and calculates heat/pump behaviour
with the same existing hot-side controller used for Brew Tracker.

Example:

```text
RAPT step target = 68 C
  -> Brewday Runtime requested target = 68 C
  -> BA writes target 68 C
  -> BA calculates heat utilisation from delta/rate/safety logic
  -> BA calculates pump state/utilisation from phase/mix logic
  -> RCL transports BA commands to BrewZilla
```

If RAPT/BrewZilla rewrites heat or pump utilisation during a profile transition,
BA may reassert its current desired values on a subsequent control pass.

## BrewAssistant RAPT reference profile v1

The first supervised reference profile is deliberately simple. RAPT already
supports starting a step timer only when target temperature is reached, so
separate ramp steps are not required.

```text
Heatstrike
  target: 70 C
  next: target temperature reached

Mash In
  target: 68 C
  next: button press on device (manual)

Mash Rest
  target: 68 C
  duration: 60 min
  timer starts: target temperature reached
  next: step timer finished

Mash Out
  target: 78 C
  duration: 10 min
  timer starts: target temperature reached
  next: step timer finished

Boil
  target: 100 C
  duration: 60 min
  timer starts: target temperature reached
  next: step timer finished

ChillOut
  target: 0 C (marker only for BA)
  next: button press on device (manual)
```

`Heatstrike` is normalized to the existing BA semantic `Heat Strike` so it enters
the established physical heat-strike controller.

A single timed `Mash Out` step is interpreted as a ramp while the measured
process temperature is below target and as a mash hold after target is reached.
This matches the RAPT profile model where the timer can start at target rather
than requiring a separate ramp step.

## Mash-In handoff

RAPT automatically advances from `Heatstrike 70 C` to the manual `Mash In 68 C`
when strike target is reached. That creates a deliberate difference between the
new RAPT directive target and the physical target BrewAssistant must hold until
the brewer actually starts adding grain.

BrewAssistant therefore uses this sequence:

```text
RAPT Heatstrike 70 C
  -> BA heats/regulates to 70 C
  -> RAPT automatically enters manual Mash In and advertises 68 C
  -> BA keeps the previous 70 C strike target latched
  -> operator presses BrewAssistant Mash-In Started
  -> BA releases the strike latch and uses 68 C
  -> pump remains paused while grain is added/mixed
  -> operator presses BrewAssistant Mash-In Complete
  -> BA starts normal mash circulation
  -> operator advances the manual RAPT Mash In step on BrewZilla
  -> RAPT enters Mash Rest 68 C / 60 min
```

The final manual RAPT step advance remains necessary because a verified
Next/Continue Profile Step API endpoint has not yet been reverse engineered.
If such an endpoint is later verified, Mash-In Complete can become the single
atomic BA action that both finishes the physical gate and advances RAPT.

## ChillOut / cooling handoff

`ChillOut` uses `0 C` only as a convenient RAPT profile marker in the current
reference profile. BrewAssistant must never transport that value as a hot-side
BrewZilla target.

When the active RAPT step is recognized as Cooling/ChillOut, the bridge:

```text
ignores RAPT target 0 C for hot-side target transport
sets desired hot-side heat utilisation to 0 %
requests BrewZilla heater OFF
stops BA target synchronization
releases BrewZilla pump ownership to Cooling Runtime/operator
```

The pump is intentionally not forced OFF by the ChillOut boundary because CFC
cooling may require wort flow and the current Cooling Runtime treats that pump
as operator-owned. Existing cooling-method logic then decides whether the CFC,
immersion-chiller or manual cooling path is active.

## RAPT step semantics

Meaningful RAPT step names are preferred. The bridge recognizes names such as
`Heatstrike`, `Mash In`, `Mash Rest`, `Mash Out`, `Boil`, `Whirlpool/Hopstand`
and `ChillOut`.

For generic RAPT names such as `Step 1`, conservative fallbacks remain:

```text
endType Temperature / controlType Ramp -> mash ramp
endType Duration                       -> mash hold
>=95 C temperature/duration target     -> boil heat/hold
```

These semantic labels feed the existing BA stage/advice/heat/pump logic; they do
not create a separate RAPT regulator.

## Source loss

If RAPT Cloud Link becomes missing, restored-only, unknown or unavailable after
BrewAssistant has observed an active profile, BrewAssistant holds RAPT ownership
with:

```text
runtime_state: source_unavailable
```

It does not silently fall back to Brewfather or Manual, and missing/stale data is
not interpreted as STOP. Ordinary source loss remains fail-passive: no new BA
writes are issued and BrewZilla keeps the last locally applied target/output
state until trustworthy telemetry returns or an explicit safety path acts.

## Confirmed STOP and safe-off

A profile STOP is confirmed only after BrewAssistant has observed an active RAPT
profile and then receives a fresh operational RCL profile state of `off`.
Restored state is not accepted as STOP evidence.

Confirmed STOP performs full safe-off:

```text
switch.brewzilla_heater            -> OFF
switch.brewzilla_pump              -> OFF
number.brewzilla_heat_utilization  -> 0 %
number.brewzilla_pump_utilization  -> 0 %
```

A STOP handoff guard prevents an already-running Brewfather source from silently
taking over the same brewday. An explicit Manual takeover may release only a
confirmed STOP guard; it cannot release an active or uncertain RAPT handoff.

## RCL command surface

The BrewAssistant RCL branch exposes:

```text
rapt_cloud_link.start_brewzilla_profile
rapt_cloud_link.end_brewzilla_profile
```

Reverse-engineered RAPT Portal requests used by the implementation:

```text
POST /api/ProfileSessions/StartProfileSession
GET  /api/ProfileSessions/EndBrewZillaProfileSession?brewZillaId=...
```

After either command, RCL requests a fresh `GetBrewZillas` update. Live
`activeProfile*` data remains the runtime truth; HTTP success alone is not used
as proof of the physical runner state.

## Supervised physical test checklist

1. Update RCL from `ba/brewassistant-rapt-cloud-link` and verify
   `binary_sensor.brewzilla_profile_active` plus start/end services exist.
2. Install BrewAssistant from `feature/rapt-brewzilla-profile-runtime`.
3. Keep the test supervised and use the reference RAPT profile above.
4. Start the RAPT profile and verify Brewday Runtime source becomes
   `RAPT BrewZilla Profile`.
5. Verify the UI chain shows `RAPT PROFILE -> BREWASSISTANT -> RCL -> BREWZILLA`.
6. During Heatstrike, verify BA uses 70 C as target and controls heat/pump with
   the existing BA heat-strike strategy.
7. When RAPT advances to manual Mash In and advertises 68 C, verify RAPT target
   shows 68 C while BA effective target remains 70 C until Mash-In Started.
8. Press Mash-In Started and verify BA target becomes 68 C while pump remains
   paused.
9. Press Mash-In Complete and verify mash circulation starts; then manually
   advance the RAPT Mash In step on BrewZilla.
10. Verify Mash Rest timer does not start until 68 C is reached and BA continues
    to regulate heat/pump from the RAPT directive.
11. Verify Mash Out behaves as ramp-to-78 followed by the timed 10 min hold.
12. Verify Boil target/time transition without letting BA invent a second RAPT
    timer.
13. On ChillOut, verify RAPT raw target can be 0 C but BA does not write 0 C as
    BrewZilla target; heat is removed and cooling owns/uses the pump separately.
14. Temporarily lose/reload RCL and verify `source_unavailable` without source
    fallback or accidental safe-off.
15. Restore RCL and verify the same RAPT profile resumes as directive source.
16. Stop the profile and verify fresh inactive RCL state causes full safe-off.

## Known first-pass limits

- The RAPT STOP handoff guard is in memory; a full Home Assistant/BrewAssistant
  restart clears it. An actually active RAPT profile is rediscovered from RCL.
- RAPT `length`/duration metadata is exposed, but BA does not invent a countdown
  for RAPT steps unless the runtime contract proves enough timing information.
- The explicit `Auto / RAPT / Brewfather / Manual` selector is architectural
  follow-up; automatic arbitration is the current implementation.
- BrewAssistant has no verified RAPT Next/Continue Step command yet, so the
  manual Mash In profile step must still be advanced on the BrewZilla.
- Operator ABORT while RAPT is active still requires explicit physical
  integration validation before this feature is merged to `main`.
