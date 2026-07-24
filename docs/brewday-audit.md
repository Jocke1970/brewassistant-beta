# Brewday Event Log

BrewAssistant includes a Python-owned Brewday Event Log for post-run analysis of Brewfather Brew Tracker, BrewAssistant runtime resolution and BrewZilla orchestration.

Status: **post-#112 supervised hot-side beta flow**.

The event log is still stored under the older audit-log storage key for compatibility, but user-facing docs and dashboards should call it Brewday Event Log.

---

## Purpose

The event log is intended to answer these questions after a test batch or real brewday:

```text
What did Brewfather expose?
What did BrewAssistant resolve?
What target did BrewZilla receive?
Was heater/pump action needed or executed?
Was the system waiting for a fresh Brewfather snapshot?
Did RAPT Cloud Link / BrewZilla telemetry become stale?
Did BrewAssistant request recovery?
Which mash-in transition state was active?
```

Use the event log during regression testing before adding new large features.

---

## Storage

The log is persisted through Home Assistant storage:

```text
.storage/brewassistant_brewday_audit_log
```

The storage filename is kept as-is for compatibility. User-facing sensors use event-log naming.

---

## Services

Current service names are kept as-is for compatibility:

```text
brewassistant.brewday_audit_start
brewassistant.brewday_audit_stop
brewassistant.brewday_audit_clear
brewassistant.brewday_audit_snapshot
```

Recommended supervised test flow:

```text
brewassistant.brewday_audit_clear
start Brewfather Brew Tracker / Manual Brewday / BrewZilla test
wait for autostart, or run brewassistant.brewday_audit_start manually if needed
brewassistant.brewday_audit_snapshot   # optional checkpoints
brewassistant.brewday_audit_stop
```

`brewassistant.abort_brewzilla` is recorded as an event as well.

---

## Autostart

Post-#112 autostart is based primarily on normalized Brewday Runtime instead of only exact Brewfather Planning state.

Primary gate:

```text
- Brewday Runtime is active/trusted
- source is Brewfather Brew Tracker or Manual Brewday
- stage/step is hot-side relevant
- BrewZilla/RAPT backend entities are present
- event log is inactive
- runtime is not completed/idle/archived
```

Fallback gate:

```text
- Brewfather batch status Planning
```

The fallback exists for startup/race windows where Brewfather batch metadata appears before the normalized runtime is fully stable.

The watchdog runs approximately every 30 seconds while the log is inactive. The last autostart decision is kept in Home Assistant runtime memory:

```text
hass.data["brewassistant"]["brewday_audit_autostart_last_result"]
```

This is diagnostics data, not a Home Assistant entity.

---

## Sensors

```text
sensor.brewassistant_brewday_event_log_summary
sensor.brewassistant_brewday_event_log_event_count
sensor.brewassistant_brewday_event_log_last_event
sensor.brewassistant_brewday_event_log_last_step
sensor.brewassistant_brewday_event_log_last_target
```

The summary sensor exposes the full event list in attributes:

```text
events
recent_events
last_event_type
last_step
last_stage
last_target
last_control_reason
last_apply_result
```

---

## Important event fields

Each event captures a compact runtime and orchestration snapshot:

```text
timestamp
event_type
runtime_state
status
stage
step
next_step
raw_step_index
resolved_step_index
raw_step_name
tracker_target
requested_target
applied_target
target_delta
target_sync_needed
heating_needed
heater_action_needed
pump_recommended
pump_action_needed
orchestration_mode
control_reason
apply_result
applied
target_changed
heater_started
pump_started
brewzilla_current_temp
brewzilla_device_target
power_w
main_power
heater_state
pump_state
snapshot_age_seconds
awaiting_snapshot
```

Mash-in gate fields:

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

RAPT/RCL freshness fields:

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

Active hot-side RCL recovery fields may appear in orchestration attributes and log entries when recovery is triggered:

```text
rcl_active_hot_side_recovery_active
rcl_active_hot_side_recovery_reason
rcl_active_hot_side_recovery_update_requested
rcl_active_hot_side_recovery_reload_requested
rcl_active_hot_side_recovery_update_recently_requested
rcl_active_hot_side_recovery_reload_recently_requested
rcl_active_hot_side_recovery_local_regulation_preserved
rcl_active_hot_side_recovery_preserved_target
```

BA-owned utilization/reassert fields:

```text
ba_owned_control_active
ba_owned_desired_heat_utilization
ba_owned_desired_pump_utilization
ba_owned_reassert_heat_utilization
ba_owned_reassert_pump_utilization
heat_utilization_action_needed
pump_utilization_action_needed
```

---

## Validation notes

The original dry-run mash profile validated target changes across:

```text
45 → 55°C
55 → 65°C
65 → 72°C
72 → 78°C
```

Later supervised water/hot-side tests validated the current clean heat-strike and mash transition model:

```text
Heat-strike to ~71.8°C
Mash-In Started
Brewfather Continue / auto Mash-In Complete
Hold 66°C
Ramp 66→72°C, currently 9 min
Hold 72°C
Ramp / hold toward 77°C
```

Observed behavior to preserve:

```text
✅ paused Brewfather state remains stable as paused
✅ awaiting_snapshot is not triggered while Brewfather is intentionally paused
✅ requested_target follows the runtime core target
✅ BrewZilla target sync actions are logged as brewzilla_action
✅ target_changed is true when BrewZilla target is updated
✅ action_skipped events show why no action was needed or why action was blocked
✅ stale/disconnected RCL should trigger recovery diagnostics, not target/heat/pump changes
✅ Mash-In Started after Mash-In Complete should be ignored rather than reverting state
```

One expected diagnostic pattern is that BrewAssistant may resolve ahead of Brewfather RAW step index:

```text
raw_step_index != resolved_step_index
```

This is not automatically an error. BrewAssistant resolves the active step from stage timing and step anchors because convenience step sensors and RAW step indexes can lag behind the actual timeline.

---

## Dashboard

Current dashboard example:

```text
dashboard/cards/brewassistant_brewday_event_log.yaml
```

Some historical docs or local backups may still reference older card paths such as `dashboards/brewday_audit_card_v1_2.yaml`. Treat those as legacy names.

The card should provide:

```text
Start / Snapshot / Stop / Clear controls
event count
last event / step / target
recent event preview
action / skipped / paused / awaiting snapshot counters
RAPT/RCL warnings when present
```

---

## Interpretation hints

`target_delta` means target synchronization delta:

```text
requested_target - applied_target
```

It is not the same as temperature delta:

```text
current_temperature - target_temperature
```

`awaiting_snapshot` near a stage boundary means BrewAssistant has reached the end of its locally resolved stage/step and is waiting for Brewfather/RAPT Cloud to publish the next checkpoint.

`Missing or invalid Brew Tracker target` can be valid at non-temperature stages such as sparge or transitions where Brewfather does not expose a direct target.

`rcl_active_hot_side_recovery_*` means BrewAssistant is trying to refresh/reload telemetry while preserving BrewZilla local regulation. It should not imply that BA changed heat, pump or target.
