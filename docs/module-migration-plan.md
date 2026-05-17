# BrewAssistant Module Migration Plan

This document outlines which BrewAssistant modules should move toward Python and in what order.

The guiding rule remains:

```text
Read-only first. Recommendations before control. Control only after validation.
```

---

## Recommended order

```text
1. BIAB module
2. Manual Fermentation module
3. Notifications polish
4. Smart fermentation control, much later
```

---

## BIAB module

BIAB is the best next Python candidate.

Why:

- It is smaller than fermentation core.
- It is calculation-heavy.
- It benefits from stable Python sensors.
- Dashboard YAML should not own calculations.
- It can be migrated safely in read-only layers.

Recommended phases:

### BIAB v0.1 read-only calculations

Expose calculated sensors only.

Suggested entities:

```text
sensor.brewassistant_biab_profile_name
sensor.brewassistant_biab_batch_volume_l
sensor.brewassistant_biab_grain_weight_kg
sensor.brewassistant_biab_mash_water_l
sensor.brewassistant_biab_sparge_water_l
sensor.brewassistant_biab_pre_boil_volume_l
sensor.brewassistant_biab_boiling_power_mode
sensor.brewassistant_biab_calculation_summary
binary_sensor.brewassistant_biab_ready_for_brewday
```

Inputs can still be existing helpers/options.

### BIAB v0.2 brewday status mirror

Expose current stage and next step.

Suggested entities:

```text
sensor.brewassistant_biab_stage
sensor.brewassistant_biab_next_step
sensor.brewassistant_biab_advice
sensor.brewassistant_biab_timer_summary
sensor.brewassistant_biab_problem_level
```

### BIAB v0.3 Digiboil power diagnostics

Read-only diagnostics for Digiboil state.

Suggested entities:

```text
sensor.brewassistant_biab_digiboil_power_w
sensor.brewassistant_biab_digiboil_power_mode
binary_sensor.brewassistant_biab_digiboil_heating_active
```

No power control yet.

### BIAB v1.0 read-only stable

Only after v0.1-v0.3 have been tested in real brewday scenarios.

---

## Manual Fermentation module

Manual Fermentation should stay mostly helper/UI-driven for now.

Why:

- It is user-input heavy.
- It needs flexible notes and manual status changes.
- YAML/helpers are currently a good fit.
- Python can help by normalizing and summarizing, not replacing everything immediately.

Recommended phases:

### Manual v0.1 read-only summary

Suggested entities:

```text
sensor.brewassistant_manual_batch_name
sensor.brewassistant_manual_batch_status
sensor.brewassistant_manual_current_sg
sensor.brewassistant_manual_target_fg
sensor.brewassistant_manual_abv_estimate
sensor.brewassistant_manual_next_step
sensor.brewassistant_manual_summary
binary_sensor.brewassistant_manual_batch_active
```

### Manual v0.2 notes/status helper bridge

Keep helpers as the source of truth, but expose clean Python sensors.

### Manual v1.0 stable

Only after the manual workflow has been used across multiple batches.

---

## What should not move yet

Do not move these into Python until read-only layers are stable:

```text
[ ] chamber hardware control
[ ] fridge switching
[ ] heat mat switching
[ ] fan switching
[ ] automatic target application
[ ] notification sending side effects
```

---

## Recommendation

Next implementation target:

```text
BIAB Python v0.1 read-only calculations
```

Manual Fermentation should follow later as a read-only summary/bridge module.
