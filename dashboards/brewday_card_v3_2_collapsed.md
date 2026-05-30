# Brewday Card v3.2 - collapsed layout plan

Brewday should follow the same visual pattern as BrewZilla Cockpit v3.2:

```text
inactive / idle:
- show only the top card
- compact standby layout
- no runtime/debug/detail noise

active runtime or BrewZilla on:
- show top card
- show runtime details
- show Brewfather RAW debug summary
```

Recommended visibility rule:

```text
Top card:
- always visible

Detail sections:
- visible when sensor.brewassistant_brewday_runtime_state is not idle/inactive/completed
- or when switch.brewzilla is on
```

Recommended top card entities:

```text
sensor.brewassistant_brewday_runtime_state
sensor.brewassistant_brewday_runtime_source
sensor.brewassistant_brewday_runtime_stage
sensor.brewassistant_brewday_runtime_step
sensor.brewassistant_brewday_runtime_next_step
sensor.brewassistant_brewday_target_temperature
sensor.brewassistant_brewday_live_time_remaining_minutes
sensor.brewassistant_brewday_live_progress
sensor.brewassistant_brewday_snapshot_age_minutes
sensor.brewassistant_brewzilla_current_temperature
sensor.brewassistant_brewzilla_target_temperature
switch.brewzilla
switch.brewzilla_heater
switch.brewzilla_pump
```

Recommended RAW debug entities:

```text
sensor.brewfather_brew_tracker_raw
runtime attributes:
- raw_step_index
- resolved_step_index
- raw_step_name
- snapshot_age_seconds
```

Design decision:

```text
Brewfather RAW should be included as a compact debug section in Brewday Card.
The full RAW checklist should remain a separate card:

dashboards/brewfather_raw_timeline_v2.yaml
```

Reason:

```text
Brewday card = operator overview
RAW timeline card = deep debug/checklist
```
