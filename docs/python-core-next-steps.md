# BrewAssistant Python Core Next Steps

This document prepares the next implementation path after v0.6.

The guiding rule remains:

```text
Read-only first. Recommendations before control. Control only after validation.
```

---

## Completed validation

### v0.5 Options Flow / Pill stale

```text
[x] Base core sensors still work
[x] Process mirror still works
[x] Smart recommendations still work
[x] Pill stale signals work
[x] Options flow appears under BrewAssistant -> Configure
[x] Saving options reloads the integration cleanly
[x] No new numbered entities remain unresolved
```

Validation notes:

```text
Base core: OK
Process mirror: OK
Smart recommendations: OK
Pill stale: OK
Options flow: OK after OptionsFlowWithConfigEntry compatibility patch
Options save/reload: OK
```

### v0.6 Source Health + Entity Diagnostics

```text
[x] Source health summary sensor works
[x] Source health level sensor works
[x] Configured source entity sensors work
[x] Source availability binary sensors work
[x] Current setup reports 6/6 sources available
[x] Liquid temperature source resolves to sensor.yellow_pill_temperature
[x] Gravity source resolves to sensor.yellow_pill_gravity
```

Validation notes:

```text
Source health: OK · 6/6 sources available
Source health level: ok
Liquid source: sensor.yellow_pill_temperature · OK
Gravity source: sensor.yellow_pill_gravity · OK
```

---

## v0.7 candidate: Debug Card v2

Goal: upgrade the debug card to show all Python Core layers.

Sections:

```text
Core
- version/manual label
- liquid/source/target/delta/gravity

Process
- Python process
- YAML process
- mismatch warning

Smart recommendations
- heat/cooling/fan
- block reason
- pulse minutes
- mode

Pill health
- pill status
- age
- stale flag

Source health
- configured source entities
- availability flags
```

This should use existing Python Core sensors and avoid duplicating complex JS/Jinja.

---

## v0.8 candidate: Next Recommended Action

Goal: expose one compact action sensor for dashboards and notifications.

Suggested entity:

```text
sensor.brewassistant_next_recommended_action
```

Possible values:

```text
Maintain cold crash
Monitor fermentation
Check Pill signal
Check source configuration
Cooling recommended
Fan assist recommended
Heat blocked
Ready for transfer
```

Inputs:

- `sensor.brewassistant_process_status`
- `sensor.brewassistant_process_next_step`
- smart recommendation sensors
- pill stale signal
- source health signals

This becomes useful for top cards and morning/status notifications.

---

## v0.9 candidate: Brewfather Runtime Normalization

Goal: reduce dependency on YAML/Jinja runtime parsing.

Suggested entities:

```text
sensor.brewassistant_runtime_recipe_name
sensor.brewassistant_runtime_status
sensor.brewassistant_runtime_primary_target_temperature
sensor.brewassistant_runtime_cold_crash_target_temperature
sensor.brewassistant_runtime_target_fg
sensor.brewassistant_runtime_source_status
binary_sensor.brewassistant_runtime_brewfather_available
```

This should remain read-only and only normalize existing HA/Brewfather sensor data.

---

## v1.0 candidate: Read-only Core Stable

v1.0 should mean:

```text
[x] Base temperature/target/gravity normalization is stable
[x] Process mirror is stable
[x] Smart recommendations are stable
[x] Source diagnostics are stable
[ ] Debug card is useful
[x] Options flow works
[x] No hardware control in Python Core yet
```

At that point, dashboards can rely primarily on Python Core for display/state decisions.

---

## Later: smart fermentation control

Do not move hardware control until read-only recommendations have been tested over multiple real fermentation/cold-crash scenarios.

Future safe-control steps:

```text
[ ] expose enable switch
[ ] expose mode select
[ ] expose tuning numbers
[ ] expose services for applying targets
[ ] add safety checks
[ ] add manual override
[ ] add emergency off path
[ ] then consider climate/switch/fan actions
```

---

## Notes from v0.4/v0.5/v0.6 lessons

- Entity registry can keep old object IDs even after code changes.
- New entity names may become `brewassistant_2`, `brewassistant_3`, etc. if Home Assistant cannot derive a unique/stable object ID.
- Always check real entities by iterating `states.sensor` / `states.binary_sensor`, not only by calling `states('entity_id')`.
- `states('missing.entity')` returns `unknown`, which can be misleading.
- For new sensors, stable `suggested_object_id` and explicit names matter.
- Source health diagnostics should be checked before debugging temperature, gravity or target logic.
