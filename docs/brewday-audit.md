# Brewday Event Log / Flight Recorder

BrewAssistant includes a Python-owned Brewday Event Log for post-run analysis of Brewfather Brew Tracker, normalized Brewday Runtime and BrewZilla orchestration.

Status: **supervised hot-side beta baseline after the 2026-08-29 physical Brewfather/BrewZilla tests**.

The backend/storage keeps historical `audit` naming for compatibility. User-facing language may use **Brewday Event Log** or **Flight Recorder**.

---

## Purpose

The Flight Recorder should make it possible to reconstruct:

```text
What Brewfather exposed
What BrewAssistant resolved as source/stage/step/target
Whether Brewfather actually owned hot-side control
What physical BrewZilla state/readback was visible
What positive plan BA wanted
Whether it waited for confirmation
Whether the operator confirmed, rejected or aborted
What writes were actually executed
Whether stale RCL readback influenced the decision
Whether safety/ABORT blocked later positive actions
```

It is the primary evidence source for supervised hot-side regression tests.

---

## Storage

Persisted Home Assistant storage:

```text
.storage/brewassistant_brewday_audit_log
```

The filename remains unchanged for compatibility.

The operator Brewday ABORT latch is intentionally a separate persistent store because safety ownership must survive even if the rolling event log is cleared or rotated.

---

## Services

Compatibility service names:

```text
brewassistant.brewday_audit_start
brewassistant.brewday_audit_stop
brewassistant.brewday_audit_clear
brewassistant.brewday_audit_snapshot
```

The hardware-level service:

```text
brewassistant.abort_brewzilla
```

is also recorded when used.

General Brewday operator ABORT is exposed through:

```text
button.brewassistant_abort_brewday
```

and produces a dedicated `brewday_abort` event after latching ownership off and executing BrewZilla safe-down.

---

## One brewday = one recorder session

A Brewfather session often appears in several states before it owns the hot side:

```text
Planning
  -> Brewing pre-start / paused on Start
  -> Play / running
  -> active hot-side runtime
```

These are one brewday and must keep one Flight Recorder `started_at`.

A transient `idle` / `source: None` snapshot during Brewfather pre-start is **not** a terminal session boundary. A dedicated deterministic session-boundary latch decides when the previous brewday is truly over.

New log rotation is expected for a genuinely new brewday, for example:

```text
previous session terminal / no owner
  -> new Manual prepared session
or
previous session terminal / no owner
  -> new Brewfather Planning/Brewing session
```

Manual ↔ Brewfather handoff inside the same brewday does not itself require a new log.

### Physical validation

The 2026-08-29 test started the recorder in Brewfather Planning at:

```text
started_at: 2026-08-29T16:39:42.512671+00:00
```

After Brewfather changed to Brewing pre-start and later Play changed tracker status `paused -> running`, the same `started_at` remained. No second `audit_started` event was created. This is the expected baseline.

---

## Autostart

Autostart has two jobs:

```text
1. capture early Brewfather Planning/pre-start context
2. capture an already active trusted Brewday if startup/race timing skipped the early phase
```

Primary runtime gate:

```text
- trusted active Brewday Runtime
- source Brewfather Brew Tracker or Manual Brewday
- relevant hot-side stage/step
- BrewZilla/RAPT backend available
- Flight Recorder inactive
```

Early fallback:

```text
- Brewfather batch phase Planning / new session context
```

A pre-start `idle` snapshot must not be reinterpreted as a completed old brewday when the same batch later starts.

---

## Sensors

```text
sensor.brewassistant_brewday_event_log_summary
sensor.brewassistant_brewday_event_log_event_count
sensor.brewassistant_brewday_event_log_last_event
sensor.brewassistant_brewday_event_log_last_step
sensor.brewassistant_brewday_event_log_last_target
```

The summary sensor exposes:

```text
events
recent_events
started_at
updated_at
last_event_type
last_stage
last_step
last_target
last_action_type
last_control_reason
last_apply_result
```

---

## Effective target vs physical device target

Target diagnostics must keep runtime intent separate from physical RAPT state.

```text
brewzilla_effective_target
  = normalized/effective BA target; may follow active runtime intent

brewzilla_device_target
  = physical/raw BrewZilla/RAPT target through the dedicated device-target sensor
```

Therefore this is valid while a positive target increase is waiting for confirmation:

```text
runtime/effective target = new value
physical device target   = old value
```

A change in `brewzilla_effective_target` is not proof that BA wrote the physical target.

For very fast entity transitions, the nested/raw `brewzilla_readback.target_c` and changed raw entity may update before the normalized device-target sensor propagates. Treat short propagation delay separately from actual physical control.

---

## Core event fields

Typical fields:

```text
timestamp
event_type
runtime_state
status
source
stage
step
next_step
raw_step_index
resolved_step_index
raw_step_name
target_temperature
tracker_target
brewzilla_effective_target
brewzilla_device_target
brewzilla_current_temp
requested_target
applied_target
target_delta
target_sync_needed
heating_needed
heater_action_needed
pump_recommended
pump_action_needed
heat_utilization_action_needed
pump_utilization_action_needed
orchestration_mode
control_reason
apply_result
applied
actions
main_power
heater_state
pump_state
power_w
snapshot_age_seconds
awaiting_snapshot
```

---

## Supervised Apply event sequence

A positive physical plan should normally produce evidence in this order:

```text
pending_confirmation
  -> operator presses CONFIRM
supervised_confirmed
  -> raw entity writes / transitions
brewzilla_action with direct_applied
  -> complete plan applied
supervised_executed
```

No positive hardware write should precede `supervised_confirmed` for that plan.

A stale or changed plan may instead produce `supervised_not_executed`.

Reject path:

```text
supervised_cancelled
cancelled_plan_suppressed   # while exact rejected intent/context remains unchanged
```

The UI now labels this action **REJECT ACTION / AVVISA ÅTGÄRD** to distinguish it from a true ABORT.

---

## Confirmed-plan RCL readback grace

RAPT Cloud Link may briefly replay old configuration after a successful confirmed write.

Example reproduced physically:

```text
heat utilization 0 -> 100   # confirmed physical write
later RCL readback 100 -> 0 # stale cloud/config replay
```

The confirmed-plan grace prevents that exact stale number readback from immediately creating a new confirmation for the same runtime intention.

Expected evidence when the grace is used:

```text
apply_result / diagnostics indicate confirmed-plan readback grace
no new positive write
no new pending_confirmation for the protected number action
```

The protection is narrow:

```text
- only confirmed target/heat/pump number increases actually sent
- same source/stage/step/target intention
- bounded 240 s window
- heater/pump ON are not silently reasserted
- ABORT breaks the grace
```

---

## ABORT evidence

### Hardware-level BrewZilla ABORT

Expected actions:

```text
abort_off:switch.brewzilla_heater
abort_off:switch.brewzilla_pump
abort_zero:number.brewzilla_heat_utilization
abort_zero:number.brewzilla_pump_utilization
```

Afterward, positive orchestration should be blocked by the BrewZilla ABORT lockout rather than immediately recreating heater/pump actions.

The 2026-08-29 physical test verified this safe-down and subsequent lockout behavior.

### Brewday operator ABORT

`button.brewassistant_abort_brewday` adds Brewday-level semantics on top of the same physical safe-down:

```text
- persist operator ownership latch = aborted
- reject/discard pending Supervised Apply intent
- reset Manual Brewday to idle
- run authoritative BrewZilla ABORT safe-down
- expose runtime_state = aborted and source = None
- block Brewfather from automatically reclaiming BA ownership
```

Expected audit event:

```text
brewday_abort
```

Explicit release event:

```text
brewday_control_rearmed
```

Rearming Brewday ownership does not remove the independent BrewZilla hardware ABORT lockout.

---

## RAPT/RCL freshness fields

```text
rapt_brewzilla_poll_age_seconds
rapt_brewzilla_poll_age_minutes
rapt_brewzilla_dynamic_age_seconds
rapt_brewzilla_dynamic_age_minutes
rapt_brewzilla_temperature_age_seconds
rapt_brewzilla_power_age_seconds
rapt_brewzilla_target_age_seconds
rapt_brewzilla_heat_util_age_seconds
rapt_brewzilla_pump_util_age_seconds
rapt_brewzilla_poll_warning
rapt_critical_refresh_recommended
```

Recovery diagnostics may also appear:

```text
rcl_active_hot_side_recovery_active
rcl_active_hot_side_recovery_reason
rcl_active_hot_side_recovery_update_requested
rcl_active_hot_side_recovery_reload_requested
rcl_active_hot_side_recovery_local_regulation_preserved
rcl_active_hot_side_recovery_preserved_target
```

RCL recovery should refresh diagnostics while preserving a valid BrewZilla local target. Recovery itself is not permission to change heat/pump/target.

---

## Mash-in fields

```text
mash_in_gate_state
mash_in_gate_pending
mash_in_gate_latched
mash_in_gate_active_key
mash_in_gate_trigger
mash_in_gate_confirmed
mash_in_gate_confirmed_at
mash_in_gate_current_target
mash_in_gate_current_temperature
mash_in_resume_allowed
mash_in_resume_result
```

Mash-in is one-way. A stale late Mash-In Started action must not move `mash_in_complete` backwards.

---

## BA-owned control diagnostics

```text
ba_owned_control_active
ba_owned_desired_heat_utilization
ba_owned_desired_pump_utilization
ba_owned_reassert_heat_utilization
ba_owned_reassert_pump_utilization
heat_utilization_action_needed
pump_utilization_action_needed
```

Manual channel ownership fields may coexist with these diagnostics. Safety/ABORT always outrank both.

---

## 2026-08-29 physical validation baseline

Observed behavior now considered the regression baseline:

```text
✅ Planning starts/maintains the recorder without hot-side ownership
✅ Brewing pre-start can expose active:true without being interpreted as started
✅ Play / paused->running produces Brewfather ownership
✅ Play keeps the same Flight Recorder started_at
✅ pending Supervised Apply causes no positive physical write
✅ explicit confirmation leads to utilization + heater/pump writes
✅ supervised_executed follows complete physical execution
✅ already-satisfied plan is not blindly repeated
✅ hardware ABORT performs full safe-down
✅ hardware ABORT lockout blocks later positive orchestration
```

Dedicated follow-up validation still required for the new Brewday operator ABORT persistence/rearm path.

---

## Dashboard

Event Log cards:

```text
dashboard/cards/brewassistant_brewday_event_log.yaml
dashboard/cards/brewassistant_brewday_event_log_sv.yaml
```

General Brewday operator cockpit:

```text
dashboard/cards/brewassistant_brewday.yaml
dashboard/cards/brewassistant_brewday_sv.yaml
```

The general cockpit deliberately separates:

```text
CONFIRM
REJECT
ABORT
REARM after ABORT
```

so rejecting one pending plan cannot be confused with physically aborting the hot side.

---

## Interpretation hints

`target_delta` is synchronization delta:

```text
requested_target - applied_target
```

not process temperature delta.

`raw_step_index != resolved_step_index` is not automatically a fault. BrewAssistant may resolve the active timeline step ahead of lagging Brewfather convenience/raw indicators.

`awaiting_snapshot` at a real stage boundary means the local timeline has exhausted known timing and awaits a fresh Brewfather checkpoint. It should not be created merely because Brewfather is intentionally paused.

An RCL freshness warning is not by itself evidence that physical BrewZilla control failed. Correlate raw entity transitions, utilization/switch states, `brewzilla_action`, `supervised_executed` and ABORT events before concluding what the hardware did.
