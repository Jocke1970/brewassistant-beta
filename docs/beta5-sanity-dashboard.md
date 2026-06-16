# BrewAssistant Beta.5 Sanity Dashboard

`dashboard/brewassistant_sanity.yaml` is intended for quick validation after Home Assistant restarts or BrewAssistant updates.

It is not the full brewing UI. It is a compact smoke-test surface for the core integration, kegerator guard/fan backend and Brewday Event Log basics.

## File

```text
dashboard/brewassistant_sanity.yaml
```

## Core entities

```text
update.brewassistant_beta_update
sensor.brewassistant_core_version
sensor.brewassistant_module_summary
climate.kegerator_kylskap
switch.brewassistant_kegerator_guard_enabled
switch.brewassistant_kegerator_fan_auto_enabled
select.brewassistant_kegerator_fan_mode
number.brewassistant_kegerator_fan_afterrun_minutes
switch.kegerator_fan
sensor.brewassistant_brewday_event_log_summary
sensor.brewassistant_brewday_event_log_event_count
```

## Expected use

```text
1. Restart Home Assistant.
2. Open the sanity dashboard.
3. Confirm BrewAssistant core/version/module summary is populated.
4. Confirm kegerator guard/fan entities exist and have sane states.
5. Confirm Brewday Event Log entities exist.
6. Check HA logs for BrewAssistant errors.
```

## Current dashboard baseline

The full reusable card baseline lives in:

```text
dashboard/cards/
```

See also:

```text
dashboard/README.md
docs/dashboard-baselines.md
```
