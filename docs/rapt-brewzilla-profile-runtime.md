# RAPT BrewZilla profile runtime

> [!CAUTION]
> **Historical implementation document — NOT the current operating plan (2026-09-19).** This describes the existing adapter in which RAPT supplies profile directives but **BrewAssistant owns and writes BrewZilla target, heat and pump**, including possible reassertion. After the aborted beta.11 water-only test, BA active hot-side control is parked. The desired new model is **RAPT/BrewZilla as sole controller, BA read-only observer**; that model is NOT implemented or verified in BA. Do not start a RAPT profile concurrently with BA's active hot-side integration and assume two-controller isolation. Read [BA pause / RAPT handoff, 2026-09-19](ba-hot-side-pause-and-rapt-handoff-2026-09-19_sv.md). RAPT controller development belongs in the separate RAPT Cloud Link chat. The test checklist below is historical and must NOT be executed on beta.11.

Status of original document: feature-branch / supervised test design, 2026-09-10. Retained for code tracing, not operating instructions.

## Purpose — legacy BA-controlled architecture

BrewAssistant can use an active RAPT BrewZilla profile as hot-side process and target source instead of Brewfather Brew Tracker or Manual Brewday. **In the existing code the RAPT profile does not independently control heat/pump under BA ownership.**

```text
LEGACY IMPLEMENTED MODEL (ACTIVE BA CONTROL NOW PARKED)
RAPT profile / Brew Tracker / Manual Brewday
    -> normalized Brewday Runtime intent
    -> BrewAssistant target + heat + pump logic
    -> RAPT Cloud Link
    -> BrewZilla
```

The profile supplies directives (step, target, duration/end condition and next step); its heat/pump utilisation values are metadata for BA, not the BA control strategy. This design must not be mistaken for the new RAPT-alone plan.

## Source and control ownership — as implemented, historical

```text
operator ABORT
  -> active/held RAPT BrewZilla profile
  -> actually started Brewfather Brew Tracker
  -> Manual Brewday
  -> idle
```

In the legacy runtime an active RAPT profile outranks Brewfather as **source**, but BA still owns the physical controller. The explicit `Auto / RAPT / Brewfather / Manual` selector was deferred. RCL identifies the profile source with `ba_source: rapt_cloud_link_brewzilla_profile_runtime`; the expected default active entity is `binary_sensor.brewzilla_profile_active`.

The normalized active runtime sets:

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

The RAPT target becomes BA's normal target request. BA can transport/reassert that setpoint and calculate heat/pump settings using the existing controller. RAPT resetting utilisation at a step transition can provoke a new BA write. **This is the exact conflicting-writer risk that must be removed before using BA as a passive companion to standalone RAPT control.**

## Original reference profile v1 — historical example, not a current test request

```text
Heatstrike: 70 C; advance at target
Mash In: 68 C; manual device step
Mash Rest: 68 C; 60 min starting when target reached
Mash Out: 78 C; 10 min starting when target reached
Boil: 100 C; 60 min starting when target reached
ChillOut: 0 C BA marker only; manual device step
```

Original BA semantic interpretation: `Heatstrike` becomes Heat Strike; a timed `Mash Out` is described as ramp before target and hold afterwards. A manual RAPT Mash In may advertise the lower mash target before grain addition; the old bridge latched the preceding strike target until the BA Mash-In Started button. BA's subsequent Mash-In Complete path formerly started circulation, which conflicts with the newer operator-gated settling design and must not be followed as physical instructions. Verified Next/Continue Profile Step API was not established at the time; the operator had to advance the manual RAPT step on BrewZilla.

## Original ChillOut boundary — code behavior, not verified external-owner mode

A RAPT `ChillOut` target of `0 C` was interpreted by BA as a phase marker, not a hot-side setpoint. The legacy bridge requested heat-utilization 0 %, heater OFF, disabled target sync and released pump ownership to Cooling Runtime/operator. **These are BA actuator actions and do not satisfy the new no-writes observer contract.** Cooling pump ownership and safe-off must be redesigned/verified under external RAPT ownership rather than copied unchanged.

## Original step and source-loss semantics

Meaningful names include Heatstrike, Mash In, Mash Rest, Mash Out, Boil, Whirlpool/Hopstand and ChillOut. For generic steps the legacy bridge treats `endType Temperature`/`controlType Ramp` as ramp, `endType Duration` as hold and high targets (>=95 C) as boil. These map into BA's existing stage/advice/heat/pump logic; they are not a separate RAPT regulator.

If RCL becomes missing/restored-only/unknown/unavailable after an observed active profile, BA retains RAPT source ownership and may report `source_unavailable`, with ordinary source loss fail-passive: BA issues no *new* writes but BrewZilla may keep the last locally applied target/output. **Fail-passive is not hardware OFF.**

A confirmed STOP originally required fresh inactive RCL state after a previously observed active profile, and could request:

```text
switch.brewzilla_heater            -> OFF
switch.brewzilla_pump              -> OFF
number.brewzilla_heat_utilization  -> 0 %
number.brewzilla_pump_utilization  -> 0 %
```

That STOP ownership/physical behavior cannot be assumed in a redesign where RAPT is the sole controller. A restart may clear memory-only STOP guards, while actual profile state can be rediscovered from RCL. Source handoff must be explicit and proven.

## Historical RCL command surface

The earlier RCL branch exposed:

```text
rapt_cloud_link.start_brewzilla_profile
rapt_cloud_link.end_brewzilla_profile
```

Earlier reverse-engineered requests were:

```text
POST /api/ProfileSessions/StartProfileSession
GET /api/ProfileSessions/EndBrewZillaProfileSession?brewZillaId=...
```

A successful HTTP response is not independent proof of active BrewZilla state: fresh `GetBrewZillas` / live `activeProfile*` was the intended source of truth. These endpoint descriptions are **historical, not newly reverified**; confirm current supported RCL functionality in the RAPT chat before changing or using them.

## Former supervised physical test checklist — WITHDRAWN for beta.11

The 2026-09-10 sequence would have installed a feature-branch BA controller, started a RAPT profile, inspected BA ownership/strike latch, pressed BA Mash-In Started and Complete, advanced the manual RAPT step, then tested Mash Rest, Mash Out, Boil, ChillOut, RCL loss/recovery and STOP. **Do not execute it while the present BA control and timing defects remain open.** Its former automatic pump-start expectation is obsolete relative to the later 10-minute settling/two operator confirmations and failed field test.

For a future single-controller solution, the RAPT chat must independently verify actual RAPT profile execution, user interaction and safe local pump behavior, *plus* confirmed suppression of **all** BA actuator writes before any simultaneous installation. The BA repo owns the no-write boundary and passive telemetry/UX work; it must not silently reintroduce a second regulator.

## Known limits carried forward

- Memory-only STOP handoff is reset by a full HA restart; active RAPT status may be rediscovered but this is not a physical safety validation.
- Profile durations do not imply BA may invent a step countdown without adequate source timing evidence.
- Explicit mode selection was an architectural follow-up; current automatic arbitration is not an external-owner mode.
- Verified profile Next/Continue API was not established in this historical adapter.
- ABORT with RAPT active and all physical cooling/STOP paths need fresh ownership design and evidence before any future active control.

**Latest BA-side decision and incident:** [2026-09-19 checkpoint](ba-hot-side-pause-and-rapt-handoff-2026-09-19_sv.md). RAPT Cloud Link design and implementation continue in the separate chat.
