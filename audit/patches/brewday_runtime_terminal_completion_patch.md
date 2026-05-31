# Brewday runtime terminal completion patch

Observed during reality test:

```text
After the final boil step finishes, BrewAssistant runtime does not shut off cleanly.
```

Likely cause:

Brewfather Brew Tracker may keep exposing `status = running` at the end of the final stage/step until the next cloud snapshot/status update. BrewAssistant currently converts `step_remaining <= 0` into `awaiting_snapshot`, even when there is no next step or next stage.

Expected behavior:

```text
If Brewfather status is running
and the active stage is the final stage
and the active step is the final step
and stage/step remaining time is zero
then BrewAssistant should resolve runtime_state = completed.
```

Recommended backend patch:

```text
1. Add helper in brewday_runtime_core.py:
   - _is_terminal_stage_step(...)
   - _runtime_terminal_complete(...)

2. In brewfather_snapshot:
   - compute all_stages before runtime_state
   - if terminal complete, force:
       runtime_state = completed
       refresh_recommended = false
       awaiting_snapshot = false
       time_remaining_seconds = 0
       target_temperature = None or keep final step target as historical attr only

3. In orchestration:
   - completed runtime must not keep applying target/heat/pump
   - optionally add completion_stop_needed if heater or pump remains on
   - at minimum control_reason should say Brewday runtime completed
```

Suggested detection:

```python
def _is_last_stage_step(all_stages, stage_index, stage, step_index):
    if stage_index is None or step_index is None:
        return False
    if stage_index != len(all_stages) - 1:
        return False
    steps = stage.get("steps") if isinstance(stage.get("steps"), list) else []
    return bool(steps) and step_index >= len(steps) - 1

terminal_complete = (
    status == "running"
    and _is_last_stage_step(all_stages, stage_index, stage, resolved_step_index)
    and stage_remaining <= 0
)
```

Manual workaround for current test:

```text
When final boil is done:
- stop/finish Brew Tracker in Brewfather if possible
- turn off heater
- keep pump off
- stop audit after final snapshot
```
