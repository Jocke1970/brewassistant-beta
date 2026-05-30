# Brewday Audit Log

BrewAssistant includes a Python-owned Brewday audit log for post-run analysis of Brewfather Brew Tracker, BrewAssistant runtime resolution and BrewZilla orchestration.

Status: **validated during a Brewfather/BrewZilla dry-run mash profile**.

---

## Purpose

The audit log is intended to answer these questions after a test batch or real brewday:

```text
What did Brewfather expose?
What did BrewAssistant resolve?
What target did BrewZilla receive?
Was heater/pump action needed or executed?
Was the system waiting for a fresh Brewfather snapshot?
```

The audit log should be used during regression testing before adding new large features.

---

## Storage

The log is persisted through Home Assistant storage:

```text
.storage/brewassistant_brewday_audit_log
```

It is also exposed through dashboard-friendly sensors.

---

## Services

```text
brewassistant.brewday_audit_start
brewassistant.brewday_audit_stop
brewassistant.brewday_audit_clear
brewassistant.brewday_audit_snapshot
```

Recommended dry-run flow:

```text
brewassistant.brewday_audit_clear
brewassistant.brewday_audit_start
run Brewfather Brew Tracker / BrewZilla test
brewassistant.brewday_audit_snapshot   # optional checkpoints
brewassistant.brewday_audit_stop
```

`brewassistant.abort_brewzilla` is recorded as an audit event as well.

---

## Sensors

```text
sensor.brewassistant_brewday_audit_summary
sensor.brewassistant_brewday_audit_event_count
sensor.brewassistant_brewday_audit_last_event
sensor.brewassistant_brewday_audit_last_step
sensor.brewassistant_brewday_audit_last_target
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

---

## Dry-run validation notes

The Brewfather/BrewZilla dry-run mash profile validated that target changes were applied at each ramp/step boundary:

```text
45 → 55°C
55 → 65°C
65 → 72°C
72 → 78°C
```

Observed behavior:

```text
✅ paused Brewfather state remains stable as paused
✅ awaiting_snapshot is not triggered while Brewfather is intentionally paused
✅ requested_target follows the runtime core target
✅ BrewZilla target sync actions are logged as brewzilla_action
✅ target_changed is true when BrewZilla target is updated
✅ action_skipped events show why no action was needed or why action was blocked
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
dashboards/brewday_audit_card_v1_1.yaml
```

The card provides:

```text
Start / Snapshot / Stop / Clear controls
event count
last event / step / target
recent event preview
action / skipped / paused / awaiting snapshot counters
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
