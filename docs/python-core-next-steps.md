# BrewAssistant Python Core Next Steps

This document prepares the next implementation path after v0.5.

The guiding rule remains:

```text
Read-only first. Recommendations before control. Control only after validation.
```

---

## Immediate after-work flow

Recommended order for the next session:

1. Update Home Assistant custom component from the PR branch.
2. Restart Home Assistant.
3. Run `docs/python-core-v0.5-test-plan.md`.
4. Fix any entity registry naming issues before adding new logic.
5. Only then continue with v0.6.

Status: completed and validated.

---

## v0.5 validation target

v0.5 is considered validated when:

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

---

## v0.6 candidate: Source Health + Entity Diagnostics

Goal: make troubleshooting easier before moving more logic.

Suggested new entities:

```text
sensor.brewassistant_source_health_summary
sensor.brewassistant_source_health_level
sensor.brewassistant_configured_liquid_temp_entity
sensor.brewassistant_configured_chamber_temp_entity
sensor.brewassistant_configured_recipe_target_entity
sensor.brewassistant_configured_cold_crash_active_entity
sensor.brewassistant_configured_cold_crash_target_entity
sensor.brewassistant_configured_gravity_entity
binary_sensor.brewassistant_source_liquid_temp_available
binary_sensor.brewassistant_source_chamber_temp_available
binary_sensor.brewassistant_source_recipe_target_available
binary_sensor.brewassistant_source_cold_crash_target_available
binary_sensor.brewassistant_source_gravity_available
```

Purpose:

- Show exactly what BrewAssistant is reading.
- Show whether each configured source exists.
- Avoid digging through options/config files when something returns `unknown`.
- Prepare for a better debug card.

Why v0.6 should probably be this:

- It is still read-only.
- It reduces support/debug time.
- It helps catch naming errors like `sensor.yellow_pill_gravity_2` vs `sensor.yellow_pill_gravity`.

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
[ ] Base temperature/target/gravity normalization is stable
[ ] Process mirror is stable
[ ] Smart recommendations are stable
[ ] Source diagnostics are stable
[ ] Debug card is useful
[ ] Options flow works
[ ] No hardware control in Python Core yet
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

## Notes from v0.4/v0.5 lessons

- Entity registry can keep old object IDs even after code changes.
- New entity names may become `brewassistant_2`, `brewassistant_3`, etc. if Home Assistant cannot derive a unique/stable object ID.
- Always check real entities by iterating `states.sensor` / `states.binary_sensor`, not only by calling `states('entity_id')`.
- `states('missing.entity')` returns `unknown`, which can be misleading.
- For new sensors, stable `suggested_object_id` and explicit names matter.
