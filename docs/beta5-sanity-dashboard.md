# BrewAssistant Beta.5 Sanity Dashboard

> Historical snapshot
>
> This document describes the older beta.5 sanity-dashboard workflow. It is kept for context only. For the current dashboard baseline, use `dashboard/README.md` and `docs/dashboard-baselines.md`.

`dashboard/brewassistant_sanity.yaml` is intended for quick validation after Home Assistant restarts or BrewAssistant updates.

It is not the full brewing UI. It is a compact smoke-test surface for the core integration, kegerator guard/fan backend and Brewday Event Log basics.

## File

```text
dashboard/brewassistant_sanity.yaml
```

## Core entities from the beta.5 snapshot

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

## Additional beta.7 smoke-test entities

Current beta.7 BrewZilla/mash-in testing should also verify:

```text
binary_sensor.brewassistant_brewzilla_mash_in_gate_pending
button.brewassistant_brewzilla_mash_in_complete
button.brewassistant_brewzilla_start_mash_circulation
```

## Expected use

```text
1. Restart Home Assistant.
2. Open the sanity dashboard.
3. Confirm BrewAssistant core/version/module summary is populated.
4. Confirm kegerator guard/fan entities exist and have sane states.
5. Confirm Brewday Event Log entities exist.
6. For beta.7 BrewZilla testing, confirm the mash-in gate and button entities exist.
7. Check HA logs for BrewAssistant errors.
```

## Current dashboard baseline

The current reusable card baseline lives in:

```text
dashboard/cards/
```

See also:

```text
dashboard/README.md
docs/dashboard-baselines.md
```
