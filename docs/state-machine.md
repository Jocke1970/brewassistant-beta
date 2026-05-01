# State Machine

BrewAssistant v4 uses a workflow/state-machine approach for fermentation and packaging.

The state machine should live in backend package templates, not inside Lovelace dashboard cards.

---

## Main process states

Recommended process states:

```text
Idle
Fermenting
Ready for cold crash
Cold crash
Ready for transfer
Packaged
Finished
```

Optional/future states:

```text
Brew day
Mashing
Boiling
Chilling
Transferring to fermenter
Carbonating
Storage
```

---

## State overview

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

## Manual mode decision logic

Manual mode should use hydrometer readings instead of RAPT/Pill gravity.

A typical manual rule:

```text
If current SG is close to target FG
and previous SG is similar
and readings are at least one day apart
then fermentation is likely complete.
```

Manual mode should be conservative and should clearly show that the user is responsible for confirming readings.

---

## Process outputs

The state machine should produce user-friendly sensors such as:

```text
sensor.brew_process_status
sensor.brew_process_next_step
sensor.brew_process_current_action_stage
sensor.brew_process_next_action_stage
sensor.brew_process_planned_summary
```

These are then displayed by dashboard cards.

---

## Dashboard display examples

A dashboard top card can show:

```text
Current state: Fermenting
Next step: Wait for stable FG
Liquid temp: 18.4 °C
Target temp: 18.0 °C
SG: 1.012
Target FG: 1.009
```

A detailed section can show:

```text
Fermentation complete: no
Ready for cold crash: no
Cold crash active: no
Ready for transfer: no
Batch packaged: no
```

---

## Manual override philosophy

Automation should assist, not take full control without visibility.

Recommended override controls:

```text
Start batch
Reset batch
Start cold crash
Mark ready for transfer
Mark packaged
Disable automation
```

---

## Future hot-side state machine

Hot-side/brew-day logic should be a separate module.

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

