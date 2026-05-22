# State Machine

BrewAssistant v4 uses workflow/state-machine patterns for fermentation, packaging and brew-day runtime flows.

The long-term goal is that state machines live in Python/backend logic, not inside Lovelace dashboard cards.

---

## Fermentation lifecycle states

Recommended fermentation process states:

```text
Idle
Fermenting
Ready for cold crash
Cold crash
Ready for transfer
Packaged
Finished
```

Optional/future fermentation-related states:

```text
Carbonating
Storage
```

---

## Fermentation state overview

| State | Meaning | Typical next step |
| --- | --- | --- |
| Idle | No active batch. | Start or import a batch. |
| Fermenting | Batch is active and fermentation is ongoing. | Monitor SG and temperature. |
| Ready for cold crash | Fermentation appears complete. | Start cold crash. |
| Cold crash | Batch is being chilled. | Wait until crash duration/temp criteria are met. |
| Ready for transfer | Cold crash appears complete. | Transfer to keg or package. |
| Packaged | Batch has been transferred or bottled. | Carbonation/storage. |
| Finished | Workflow is complete. | Reset or archive batch. |

---

## Brewday Runtime states

Brewday Runtime is separate from fermentation lifecycle.

Current runtime states:

```text
idle
prepared
running
live
paused
awaiting_confirm
awaiting_snapshot
completed
```

State meaning:

| Runtime state | Meaning | Typical next action |
| --- | --- | --- |
| idle | No active brewday runtime source. | Select source or prepare manual brewday. |
| prepared | Manual Brewday is prepared but not running. | Start manual brewday. |
| running/live | Runtime is active and timer is moving. | Monitor, pause, next or finish. |
| paused | Runtime is paused. | Resume, next or finish. |
| awaiting_confirm | Manual step requires user confirmation. | Confirm/start or next. |
| awaiting_snapshot | Brewfather step boundary reached and BrewAssistant is waiting for a fresh snapshot. | Refresh/await Brewfather update. |
| completed | Brewday runtime is complete. | Reset or start new brewday. |

---

## Brewfather Brew Tracker runtime logic

Brewfather exposes a stage-level tracker model.

Important distinction:

```text
stage.remainingSeconds = remaining time for the whole active stage
step.time              = countdown anchor for a step/checkpoint inside the stage
step.duration          = optional duration for timed steps
```

BrewAssistant therefore exposes both:

```text
current_step_remaining_seconds
stage_remaining_seconds
```

The dashboard should use current-step remaining for “time left” on the active action and stage remaining only for full-stage context.

When current-step remaining reaches zero, BrewAssistant can trigger a guarded Brewfather refresh to compensate for upstream polling delay.

Manual refresh is also available through:

```text
brewassistant.force_brewfather_refresh
```

with a 15 minute manual cooldown.

---

## Manual Brewday runtime logic

Manual Brewday now has a Python-owned runtime session.

Core model:

```text
ManualPlan
  ManualStage[]
    ManualStep[]

ManualRuntimeSession
  state
  active_stage_index
  active_step_index
  step_started_at
  paused_at
  remaining_when_paused
```

Current services:

```text
brewassistant.manual_brewday_prepare
brewassistant.manual_brewday_start
brewassistant.manual_brewday_pause
brewassistant.manual_brewday_next
brewassistant.manual_brewday_finish
brewassistant.manual_brewday_reset
```

Manual Brewday currently stores session state in `hass.data`, which means it survives runtime sensor updates but not a full Home Assistant restart.

Future improvements:

```text
[ ] Auto-advance timed manual steps when appropriate
[ ] Set awaiting_confirm when a timed manual step reaches zero and needs user action
[ ] Persist ManualRuntimeSession across Home Assistant restarts
[ ] Build ManualPlan from Brewfather recipe or user-selected brewday profile
```

---

## Typical fermentation decision logic

A common automated fermentation rule:

```text
If SG is at or below target FG
and SG has been stable long enough
then batch may be ready for cold crash.
```

Recommended safeguards:

- Require stable SG for a defined duration.
- Do not rely on a single noisy gravity reading.
- Allow manual override.
- Display the reasoning in the dashboard.

---

## Cold crash decision logic

A common cold crash rule:

```text
If cold crash is active
and liquid/chamber temperature has been low enough
and minimum cold crash duration has passed
then batch may be ready for transfer.
```

Example thresholds:

```text
Cold crash target: 1-4 °C
Minimum duration: 24-72 hours
```

The exact values should be configurable.

---

## Manual fermentation decision logic

Manual fermentation mode should use hydrometer readings instead of RAPT/Pill gravity.

A typical manual rule:

```text
If current SG is close to target FG
and previous SG is similar
and readings are at least one day apart
then fermentation is likely complete.
```

Manual fermentation mode should be conservative and should clearly show that the user is responsible for confirming readings.

---

## Process outputs

The fermentation/lifecycle state machine should produce user-friendly sensors such as:

```text
sensor.brew_process_status
sensor.brew_process_next_step
sensor.brew_process_current_action_stage
sensor.brew_process_next_action_stage
sensor.brew_process_planned_summary
```

Brewday Runtime produces normalized runtime sensors such as:

```text
sensor.brewassistant_brewday_runtime_state
sensor.brewassistant_brewday_runtime_stage
sensor.brewassistant_brewday_runtime_step
sensor.brewassistant_brewday_runtime_next_step
sensor.brewassistant_brewday_runtime_summary
```

These are then displayed by dashboard cards.

---

## Dashboard display examples

A fermentation dashboard top card can show:

```text
Current state: Fermenting
Next step: Wait for stable FG
Liquid temp: 18.4 °C
Target temp: 18.0 °C
SG: 1.012
Target FG: 1.009
```

A Brewday Runtime dashboard top card can show:

```text
Runtime: running
Stage: Mash
Step: Saccharification rest
Time left: 58 min
Next: Mash out
```

---

## Manual override philosophy

Automation should assist, not take full control without visibility.

Recommended fermentation controls:

```text
Start batch
Reset batch
Start cold crash
Mark ready for transfer
Mark packaged
Disable automation
```

Recommended brewday controls:

```text
Prepare
Start / Resume
Pause
Next
Finish
Reset
Refresh Brewfather snapshot
```

---

## Future hot-side state machine

Hot-side/brew-day logic should be separate from fermentation lifecycle.

Potential states:

```text
Idle
Heating strike water
Mashing
Mash out
Sparging
Heating to boil
Boiling
Hop addition due
Whirlpool
Chilling
Transfer to fermenter
Complete
```

This avoids mixing fermentation logic with BrewZilla/BrewTracker logic.

