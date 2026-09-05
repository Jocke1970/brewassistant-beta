# Brewday backend

Status: active  
Code snapshot documented: 2026-09-05

`brewday` owns BrewAssistant's normalized brewday process model. It merges external Brewfather Brew Tracker state and the Python-owned Manual Brewday engine into one runtime contract, interprets that runtime into human-facing process stages, keeps physical timing, and records the Brewday/BrewZilla flight recorder.

It is intentionally not a BrewZilla hardware backend. Hardware-specific actuation belongs in [`../brewzilla/`](../brewzilla/).

## Responsibilities

- normalize Brewfather Brew Tracker into a stable Brewday Runtime snapshot;
- provide a first-class Python Manual Brewday runtime when Brewfather is not the active owner;
- enforce Brewfather actual-start ownership instead of trusting only batch status;
- keep the operator ABORT/rearm ownership latch above all runtime sources;
- interpret normalized runtime + telemetry into readable brewday stages;
- keep physical phase/timer context separate from external tracker pauses where required;
- emit addition alerts and refresh guidance;
- persist a compact event/audit log (Flight Recorder);
- preserve session boundaries and recorder continuity across source transitions.

## Source priority

The public runtime resolver in `brewday_runtime.py` applies this order:

```text
operator ABORT latch
  -> explicit aborted/non-owning runtime

active Brewfather Brew Tracker
  -> Brewfather runtime wins
  -> Manual Brewday is paused for handoff

active Manual Brewday
  -> Python Manual Brewday runtime

otherwise
  -> normalized idle/core snapshot
```

A Brewfather batch being in a broad `Brewing` state is not sufficient by itself. The ownership policy requires evidence that the Brew Tracker has actually started/advanced. Once legitimately started, ownership may remain through normal tracker pauses.

## Operator ABORT boundary

Brewday operator ABORT is an ownership latch, not merely a UI state. While latched:

- normalized source becomes `None`/aborted;
- Brewfather cannot reclaim hot-side ownership;
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

The default BIAB plan contains Setup, Mash, Sparge, Boil, Whirlpool and Chill/Transfer stages. Manual steps can carry duration, target temperature, `pause_before` and `auto_advance` metadata. The adapter converts this internal model to the same normalized surface used by Brewfather.

Important files:

| File | Purpose |
| --- | --- |
| `manual_brewday_runtime.py` | Manual plan/session model, timers and transitions |
| `manual_brewday_store.py` | Current Manual Brewday session storage/access |
| `manual_brewday_adapter.py` | Converts Manual runtime into normalized Brewday snapshot |

## Runtime and stage interpretation

`brewday_runtime_core.py` resolves the external/core runtime. `brewday_runtime.py` is the stable compatibility/public wrapper. `brewday_ramp_target_gate.py` adjusts core behavior so temperature ramps do not advance merely because the external schedule did.

`brewday_stage_engine.py` is read-only. It combines normalized runtime and BrewZilla telemetry into operator-facing stages such as:

```text
Idle -> Prepare -> Heating Strike / Strike Water -> Mash In -> Mash
-> Mash Out -> Heating To Boil -> Boiling / Hop Addition -> Whirlpool
-> Wort Cooling -> Pitch Ready / Transfer -> Cleaning -> Completed
```

The stage engine may indicate `cooling_handoff`, but it does not control the Cooling backend or BrewZilla hardware.

## Physical timing

`brewday_physical_timing.py` and `brewday_physical_timing_phase_patch.py` keep timers tied to real controller/physical phase behavior where that differs from Brewfather's schedule state. A Brewfather pause around mash additions must not freeze an already active Heatstrike physical ramp clock.

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
| `brewfather_ownership.py` | Actual-start ownership policy |
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
2. Brewfather must not gain hot-side authority solely from a broad batch status.
3. Operator ABORT outranks Brewfather and Manual sources.
4. Manual Brewday is a real Python runtime, not a dashboard/YAML emulation.
5. The stage engine is interpretive/read-only.
6. Physical timing and external tracker timing are deliberately distinct where controller reality requires it.
7. Flight Recorder session continuity is a diagnostic contract; avoid resetting/rotating it on cosmetic source changes.
