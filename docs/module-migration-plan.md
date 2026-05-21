# BrewAssistant Module Migration Plan

This document outlines which BrewAssistant modules should move toward Python and in what order.

The guiding rule remains:

```text
Read-only first. Recommendations before control. Control only after validation.
```

The new architectural rule is stricter:

```text
Python owns backend logic.
YAML owns presentation only.
```

YAML packages should be treated as legacy/bridge code unless they only define dashboard cards or very thin user-facing helpers.

---

## Target architecture

```text
custom_components/brewassistant/
  Owns state, calculations, readiness, summaries, recommendations and future services.

packages/*.yaml
  Legacy bridge during migration. Should shrink over time.

dashboards/**/*.yaml
  Presentation layer only. Cards may call entities/services, but should not contain business logic.
```

---

## Recommended order

```text
1. Workflow / batch lifecycle engine
2. Packaging / transfer readiness
3. Runtime adapter cleanup
4. BIAB read-only calculations
5. Manual Fermentation summary bridge
6. Smart fermentation control, much later
7. Hardware control, last
```

Why workflow first:

- It is the system brain.
- It currently drives many downstream cards and notifications.
- It removes the need to rebuild new backend sensors in YAML.
- It creates a clean source of truth before BIAB, BrewZilla and multi-batch logic expand.

---

## Workflow engine

Workflow should become the first major YAML-retirement target.

### Workflow v0.1 read-only state mirror

Expose current lifecycle state without controlling hardware.

Suggested entities:

```text
sensor.brewassistant_process_status
sensor.brewassistant_process_status_sv
sensor.brewassistant_process_stage
sensor.brewassistant_process_summary
sensor.brewassistant_next_step
sensor.brewassistant_next_step_sv
binary_sensor.brewassistant_batch_active
binary_sensor.brewassistant_cold_crash_active
binary_sensor.brewassistant_ready_for_packaging
binary_sensor.brewassistant_ready_for_transfer
```

Inputs may initially come from existing HA entities, Brewfather runtime sensors and RAPT/Pill readings.

### Workflow v0.2 lifecycle actions

Add safe Python buttons/services for lifecycle marking only.

Suggested actions:

```text
button.brewassistant_start_batch
button.brewassistant_start_cold_crash
button.brewassistant_mark_packaging_done
button.brewassistant_mark_transferred_to_keg
button.brewassistant_reset_batch
```

These actions should update integration-owned state, not YAML helpers.

### Workflow v0.3 event model

Emit internal BrewAssistant events for dashboards/notifications to consume later.

Suggested events:

```text
brewassistant_batch_started
brewassistant_cold_crash_started
brewassistant_ready_for_packaging
brewassistant_transferred_to_keg
brewassistant_batch_completed
```

No notification side effects yet.

---

## Packaging / transfer readiness

Packaging should move after Workflow v0.1 exists.

Suggested entities:

```text
binary_sensor.brewassistant_packaging_recommended
sensor.brewassistant_packaging_reason
sensor.brewassistant_packaging_checklist_status
sensor.brewassistant_transfer_summary
```

Initial rules can be conservative:

```text
batch active
cold crash active or completed
liquid temperature below configured threshold
gravity at/below target FG threshold or stable
source health OK or explicitly acknowledged
```

---

## Runtime adapter cleanup

Runtime should normalize Brewfather/manual/source data into integration-native objects.

Suggested direction:

```text
Brewfather sensors -> Python runtime model -> BrewAssistant workflow entities
Manual inputs     -> Python runtime model -> BrewAssistant workflow entities
Future BrewZilla  -> Python runtime model -> BrewAssistant workflow entities
```

Dashboards should read BrewAssistant entities, not nested Brewfather details directly.

---

## BIAB module

BIAB is still a strong Python candidate, but should follow the workflow engine so brewday logic has a lifecycle model to attach to.

Why:

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

Inputs can initially come from existing helpers/options.

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

### BIAB v0.3 Digiboil/BrewZilla power diagnostics

Read-only diagnostics for hot-side equipment state.

Suggested entities:

```text
sensor.brewassistant_hot_side_power_w
sensor.brewassistant_hot_side_power_mode
binary_sensor.brewassistant_hot_side_heating_active
```

No power control yet.

---

## Manual Fermentation module

Manual Fermentation should become a Python summary/runtime source, not a separate YAML brain.

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

### Manual v0.2 integration-owned state

Move manual lifecycle state into integration storage/options where practical.

### Manual v1.0 stable

Only after the manual workflow has been used across multiple batches.

---

## What should not move yet

Do not move these into active Python control until read-only layers are stable:

```text
[ ] chamber hardware control
[ ] fridge switching
[ ] heat mat switching
[ ] fan switching
[ ] automatic target application
[ ] notification sending side effects
```

These may get read-only diagnostics earlier, but no control side effects.

---

## YAML retirement checklist

```text
[ ] Identify YAML sensors that only calculate or summarize state
[ ] Recreate them as Python entities
[ ] Update dashboard cards to read Python entities
[ ] Keep old YAML entities temporarily as fallback
[ ] Remove/disable old YAML logic once Python entities are validated
[ ] Leave dashboard/card YAML intact
```

---

## Recommendation

Next implementation target:

```text
Workflow Python v0.1 read-only lifecycle engine
```

After that, build packaging readiness and lifecycle actions before moving deeper into BIAB or hardware control.
