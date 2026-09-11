# Brewday backend

Status: active  
Code snapshot documented: 2026-09-11

`brewday` owns BrewAssistant's normalized brewday process model. It arbitrates external Brewfather Brew Tracker state, RAPT profile runtime and the Python-owned Manual Brewday engine into one runtime contract, interprets that runtime into human-facing process stages, keeps physical timing, and records the Brewday/BrewZilla flight recorder.

It is intentionally not a BrewZilla hardware backend. Hardware-specific actuation belongs in [`../brewzilla/`](../brewzilla/).

For the distinction between recipe source, runtime/timer owner and physical-control policy, see [`../../../docs/brewday-execution-modes.md`](../../../docs/brewday-execution-modes.md).

## Responsibilities

- normalize Brewfather Brew Tracker into a stable Brewday Runtime snapshot;
- normalize an active RAPT BrewZilla profile into the same runtime surface while BrewAssistant remains the hot-side controller;
- provide a first-class Python Manual Brewday runtime when no higher-priority external owner is active;
- enforce external-source ownership from real start/profile evidence rather than broad batch/device status alone;
- keep the operator ABORT/rearm ownership latch above all runtime sources;
- interpret normalized runtime + telemetry into readable brewday stages;
- keep physical phase/timer context separate from external schedule timing where required;
- emit addition alerts and refresh guidance;
- persist a compact event/audit log (Flight Recorder);
- preserve session boundaries and recorder continuity across source transitions.

## Source priority

The public runtime resolver in `brewday_runtime.py` applies this order on the current RAPT-profile branch:

```text
operator ABORT latch
  -> explicit aborted/non-owning runtime

active / uncertain / stopped-handoff RAPT profile
  -> RAPT profile runtime wins
  -> Manual Brewday is paused for handoff

active Brewfather Brew Tracker
  -> Brewfather runtime wins
  -> Manual Brewday is paused for handoff

active Manual Brewday
  -> Python Manual Brewday runtime

otherwise
  -> normalized idle/core snapshot
```

A Brewfather batch being in a broad `Brewing` state is not sufficient by itself. The ownership policy requires evidence that the Brew Tracker has actually started/advanced. Once legitimately started, ownership may remain through normal tracker pauses.

A RAPT source loss after an observed active profile intentionally keeps the RAPT handoff rather than silently falling back to Brewfather. A confirmed profile STOP likewise keeps its stop guard until an explicit/new handoff is allowed.

## Execution ownership is separate from recipe source

BrewAssistant must keep these concepts distinct:

```text
recipe/profile source
runtime/timer owner
physical BrewZilla control policy
```

Two Brewfather-derived execution models are now explicitly planned:

```text
Brewfather/BrewTracker supervised
  -> Brewfather supplies recipe + Brew Tracker runtime
  -> Brew Tracker owns step/timer progression
  -> BA owns physical target/heat/pump policy

BrewAssistant recipe runtime
  -> Brewfather supplies recipe/profile data only
  -> BA builds and owns the Python runtime/timers
  -> BA starts timed holds only after physical target reach
  -> Brew Tracker is not required for progression
```

The second model is future work. Its natural implementation foundation is the existing Python Manual Brewday runtime generalized/populated from imported recipe data.

Runtime ownership is also separate from actuation policy: a BA-owned runtime may still use Supervised Apply before any future direct/unattended apply mode is considered validated.

## Brewfather 0-minute PAUS checkpoint

A 2026-09-11 water test verified that a 0-minute mash-profile step named `PAUS` creates a hard Brew Tracker checkpoint:

```text
status              -> paused
raw step            -> PAUS
time remaining      -> 0
stage/progress      -> frozen
Play/Resume in BF   -> tracker returns to running
```

This is useful for Brewfather/BrewTracker-owned execution because the following Brewfather rest timer does not need to run while BrewAssistant/BrewZilla is still approaching the target temperature.

Required BA contract while the tracker is paused:

```text
- keep the current tracker target latched;
- continue only the physical work required to reach/hold that current target;
- never use next_step as a hardware target;
- notify when the physical target is ready;
- accept the following target only after Brewfather has resumed/advanced.
```

The same test exposed a current orchestration bug: while Brew Tracker was paused, BA could pre-actuate the following target (40 -> 45 °C and later 45 -> 55 °C). Fixing that paused-target hold is the next required BrewTracker regression before the checkpoint pattern is considered production-ready.

The current BrewTracker path is read-only toward tracker progression, so BrewAssistant can notify that the target is ready but the operator resumes Brewfather.

## Operator ABORT boundary

Brewday operator ABORT is an ownership latch, not merely a UI state. While latched:

- normalized source becomes `None`/aborted;
- RAPT/Brewfather cannot reclaim hot-side ownership;
- Manual Brewday is not allowed to continue normal ownership;
- pending positive hot-side work is discarded by the surrounding control path;
- BrewZilla's authoritative physical ABORT path is invoked by the integration service layer.

Control must be explicitly rearmed. Rearming Brewday ownership does not bypass a separate BrewZilla hardware ABORT lockout.

## Manual Brewday

`manual_brewday_runtime.py` is UI-independent and owns its own timers/transitions. Main states:

```text
idle
prepared
running
paused
awaiting_confirm
completed
```

The default BIAB plan contains Setup, Mash, Sparge, Boil, Whirlpool and Chill/Transfer stages. Manual steps can carry duration, target temperature, `pause_before` and `auto_advance` metadata. The adapter converts this internal model to the same normalized surface used by external owners.

Important files:

| File | Purpose |
| --- | --- |
| `manual_brewday_runtime.py` | Manual plan/session model, timers and transitions |
| `manual_brewday_store.py` | Current Manual Brewday session storage/access |
| `manual_brewday_adapter.py` | Converts Manual runtime into normalized Brewday snapshot |
| `rapt_profile_runtime.py` | Converts the active RAPT profile/step into normalized runtime intent |

## Runtime and stage interpretation

`brewday_runtime_core.py` resolves the Brewfather/core runtime. `brewday_runtime.py` is the stable public wrapper and source arbiter. `brewday_ramp_target_gate.py` adjusts Brewfather behavior so temperature ramps do not advance merely because the external schedule did.

`brewday_stage_engine.py` is read-only. It combines normalized runtime and BrewZilla telemetry into operator-facing stages such as:

```text
Idle -> Prepare -> Heating Strike / Strike Water -> Mash In -> Mash
-> Mash Out -> Heating To Boil -> Boiling / Hop Addition -> Whirlpool
-> Wort Cooling -> Pitch Ready / Transfer -> Cleaning -> Completed
```

The stage engine may indicate `cooling_handoff`, but it does not control the Cooling backend or BrewZilla hardware.

## Physical timing

`brewday_physical_timing.py` and `brewday_physical_timing_phase_patch.py` keep timers tied to real controller/physical phase behavior where that differs from an external schedule state.

Important distinction:

```text
source timer / source pause
  != proof of physical target reach
```

For Brewfather/BrewTracker-owned execution, the 0-minute PAUS checkpoint may intentionally freeze Brewfather progression while BA continues the physical target approach. For a future BA-owned imported-recipe runtime, BA itself will start each timed hold only after the selected physical process temperature reaches its target band.

## Flight Recorder / audit log

`brewday_audit.py` is Python-owned and persisted through Home Assistant Storage:

```text
storage key: brewassistant_brewday_audit_log
schema version: 2
max events: 250
```

The log records normalized runtime context plus selected BrewZilla action/safety/freshness fields. It is intended as the source of truth for diagnosing hot-side behavior rather than inferring control from dashboard appearance alone.

Typical important event classes include:

- audit start/stop and manual snapshots;
- Brewfather refresh requests;
- BrewZilla actions and owned-control reasserts;
- Mash-In confirmation/circulation events;
- ABORT, warnings and errors;
- periodic orchestration evidence when meaningful state changes occur.

Session-boundary and continuity patches in `__init__.py` prevent a ready-only Brewfather pre-start row from being mistaken for a completed prior brewday when Play is pressed.

## Other files

| File | Purpose |
| --- | --- |
| `brewfather_ownership.py` | Actual-start BrewTracker ownership policy |
| `rapt_profile_runtime.py` | RAPT profile ownership/runtime normalization |
| `brewday_operator_abort.py` | Persistent operator-control latch |
| `brewday_refresh.py` / `brewday_refresh_policy.py` | Guarded Brewfather refresh behavior |
| `brewday_addition_alerts.py` | Timed/step addition alert logic |
| `brewday_*_sensor.py` | Home Assistant presentation entities |
| `brewday_audit_autostart.py` | Recorder lifecycle automation |
| `brewday_audit_session_boundary.py` | Deterministic new-session boundary |
| `brewday_audit_session_continuity.py` | Recorder continuity around tracker start |

## Public service surface

The integration root registers Brewday-related services including:

```text
brewassistant.force_brewfather_refresh
brewassistant.brewday_audit_start
brewassistant.brewday_audit_stop
brewassistant.brewday_audit_clear
brewassistant.brewday_audit_snapshot

brewassistant.manual_brewday_prepare
brewassistant.manual_brewday_start
brewassistant.manual_brewday_pause
brewassistant.manual_brewday_next
brewassistant.manual_brewday_start_mash
brewassistant.manual_brewday_start_boil
brewassistant.manual_brewday_start_whirlpool
brewassistant.manual_brewday_start_cooling
brewassistant.manual_brewday_finish
brewassistant.manual_brewday_reset
```

Exact entity names are registered through the root platform modules; backend code should expose normalized snapshots rather than depend on Lovelace helpers.

## Do not change casually

1. Brewday Runtime must remain hardware-independent enough to work without BrewZilla.
2. External process ownership must come from real start/profile evidence, not broad batch/device status alone.
3. Operator ABORT outranks RAPT, Brewfather and Manual sources.
4. Manual Brewday is a real Python runtime, not a dashboard/YAML emulation.
5. The stage engine is interpretive/read-only.
6. Recipe source, runtime owner and hardware apply policy are separate architectural concepts.
7. A paused BrewTracker must never authorize pre-actuation of `next_step` target.
8. Physical timing and external tracker timing are deliberately distinct where controller reality requires it.
9. Flight Recorder session continuity is a diagnostic contract; avoid resetting/rotating it on cosmetic source changes.
