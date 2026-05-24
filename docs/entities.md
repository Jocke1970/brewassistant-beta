# Entity Guide

This document describes the preferred BrewAssistant v4 entity model.

BrewAssistant is moving toward Python-owned normalized entities under the `brewassistant_*` namespace. Older `fwk_*`, `brew_process_*`, helper-driven and package-template entities may still exist in local Home Assistant installs, but they should not be used as the source of truth for new backend logic.

---

## Naming principles

Preferred current direction:

```text
sensor.brewassistant_*                 Python-owned normalized sensors
binary_sensor.brewassistant_*          Python-owned binary state
switch.brewassistant_*                 Explicit safe user toggles / safety switches
number.brewassistant_*                 Python-owned numeric controls
select.brewassistant_*                 Python-owned select controls
button.brewassistant_*                 Future explicit action buttons
```

Recommended module namespaces:

```text
brewassistant_brewday_*                Brewday Runtime and Stage Engine
brewassistant_brewzilla_*              BrewZilla runtime/orchestration
brewassistant_wort_*                   Wort cooling and pitch-readiness
brewassistant_carbonation_*            Carbonation calculations and serving guidance
brewassistant_fermentation_*           Future fermentation runtime
brewassistant_source_*                 Source diagnostics
```

Legacy namespaces:

```text
fwk_*                                  old Fresh Wort Kit namespace
brew_process_*                         older process namespace
brew_batch_*                           older batch namespace
brew_recipe_*                          older recipe/runtime namespace
input_boolean/input_number helpers     old workflow mirrors or local inputs
```

---

## Brewday Runtime entities

Brewday Runtime describes the active runtime source and current planned step.

Current examples:

```text
sensor.brewassistant_brewday_runtime_summary
sensor.brewassistant_brewday_runtime_state
sensor.brewassistant_brewday_runtime_stage
sensor.brewassistant_brewday_runtime_step
sensor.brewassistant_brewday_runtime_next_step
sensor.brewassistant_brewday_live_time_remaining_minutes
sensor.brewassistant_brewday_live_progress
```

Runtime sources:

```text
Brewfather Brew Tracker
Manual Brewday
None
```

Manual Brewday is Python-owned and no longer depends on old helper mirrors.

---

## Brewday Stage Engine entities

Stage Engine interprets the current active brewday stage from Runtime and BrewZilla telemetry.

Current entities:

```text
sensor.brewassistant_brewday_stage
sensor.brewassistant_brewday_stage_reason
sensor.brewassistant_brewday_stage_status_line
sensor.brewassistant_brewday_stage_icon
sensor.brewassistant_brewday_stage_group
sensor.brewassistant_brewday_stage_priority
sensor.brewassistant_brewday_stage_suggested_action
sensor.brewassistant_brewday_stage_control_hint
sensor.brewassistant_brewday_stage_remaining_minutes
sensor.brewassistant_brewday_stage_progress
sensor.brewassistant_brewday_stage_temperature
sensor.brewassistant_brewday_stage_target_temperature
sensor.brewassistant_brewday_stage_power
```

Typical stage groups:

```text
idle
mash
boil
post_boil
cooling
wrap_up
```

Important behavior:

```text
Current active stage/step determines current stage.
next_step should not wake future stages early.
```

---

## Manual Brewday services

Manual Brewday is controlled through Python services:

```text
brewassistant.manual_brewday_prepare
brewassistant.manual_brewday_start
brewassistant.manual_brewday_pause
brewassistant.manual_brewday_next
brewassistant.manual_brewday_start_mash
brewassistant.manual_brewday_start_boil
brewassistant.manual_brewday_start_whirlpool
brewassistant.manual_brewday_start_cooling
brewassistant.manual_brewday_finish
brewassistant.manual_brewday_reset
```

These services replace older helper/script-driven manual controls.

---

## BrewZilla entities

Current normalized BrewZilla examples:

```text
sensor.brewassistant_brewzilla_connection_state
sensor.brewassistant_brewzilla_runtime_state
sensor.brewassistant_brewzilla_current_temperature
sensor.brewassistant_brewzilla_target_temperature
sensor.brewassistant_brewzilla_temperature_delta
sensor.brewassistant_brewzilla_power
sensor.brewassistant_brewzilla_heat_utilization
sensor.brewassistant_brewzilla_pump_utilization
```

Safety/orchestration entities:

```text
switch.brewassistant_brewzilla_orchestration_enabled
switch.brewassistant_brewzilla_apply_target_temp
switch.brewassistant_brewzilla_allow_heater_control
switch.brewassistant_brewzilla_allow_pump_control
switch.brewassistant_brewzilla_allow_boil_mode
switch.brewassistant_brewzilla_safe_mode
sensor.brewassistant_brewzilla_orchestration_mode
sensor.brewassistant_brewzilla_control_reason
sensor.brewassistant_brewzilla_requested_target
sensor.brewassistant_brewzilla_applied_target
sensor.brewassistant_brewzilla_target_delta
```

External hardware examples may still be used as raw sources:

```text
switch.brewzilla
switch.brewzilla_heater
switch.brewzilla_pump
number.brewzilla_target_temperature
```

---

## Wort Cooling entities

Counterflow Wort Cooling uses Python sensors and is scope-gated by Stage Engine.

Current entities:

```text
sensor.brewassistant_wort_cooling_status
sensor.brewassistant_wort_cooling_summary
sensor.brewassistant_wort_cooling_reference_temperature
sensor.brewassistant_wort_cooling_target_temperature
sensor.brewassistant_wort_cooling_delta
sensor.brewassistant_wort_cooling_rate
sensor.brewassistant_wort_cooling_eta_minutes
sensor.brewassistant_wort_pitch_ready
```

Typical states:

```text
standby
heater_off_required
pump_on_required
cooling_needed
cooling
below_target
pitch_ready
no_reference_temperature
no_target
```

Important behavior:

```text
Stage is not cooling/pitch
→ standby

Wort above target + pump off
→ pump_on_required

Heater on during cooling
→ heater_off_required
```

---

## Carbonation entities

Carbonation is Python-runtime backed and used by the Carbonation Cockpit UI.

Current sensors:

```text
sensor.brewassistant_carbonation_status
sensor.brewassistant_carbonation_method
sensor.brewassistant_carbonation_target_volumes
sensor.brewassistant_carbonation_temperature
sensor.brewassistant_carbonation_recommended_pressure_bar
sensor.brewassistant_carbonation_recommended_pressure_psi
sensor.brewassistant_carbonation_actual_pressure_bar
sensor.brewassistant_carbonation_actual_pressure_psi
sensor.brewassistant_carbonation_equilibrium_volumes
sensor.brewassistant_carbonation_estimated_volumes
sensor.brewassistant_carbonation_progress_percent
sensor.brewassistant_carbonation_started_at
sensor.brewassistant_carbonation_age_days
sensor.brewassistant_carbonation_summary
```

Current controls:

```text
number.brewassistant_carbonation_pressure_bar
number.brewassistant_carbonation_target_volumes
number.brewassistant_carbonation_start_volumes
select.brewassistant_carbonation_method
```

Current services:

```text
brewassistant.carbonation_start
brewassistant.carbonation_update
brewassistant.carbonation_pause
brewassistant.carbonation_reset
```

Important behavior:

```text
sensor.kyl_temperatur_4 is the default carbonation temperature source.
Legacy input_number.brewassistant_carbonation_pressure_bar is not a backend pressure fallback.
Actual pressure is owned by number.brewassistant_carbonation_pressure_bar / Python runtime.
```

Current open design question:

```text
progress_percent currently needs validation: level-percent vs separate level/process progress.
```

---

## Fermentation entities

Fermentation currently has coordinator-owned process/scope sensors and older smart recommendation sensors, with a planned Python-owned Timed Fermentation Runtime later.

Current examples:

```text
sensor.brewassistant_liquid_temperature
sensor.brewassistant_liquid_temperature_source
sensor.brewassistant_chamber_temperature
sensor.brewassistant_recipe_target_temperature
sensor.brewassistant_temperature_delta
sensor.brewassistant_temperature_status
sensor.brewassistant_temperature_severity
sensor.brewassistant_problem_level
sensor.brewassistant_process_status
sensor.brewassistant_process_current_action_stage
sensor.brewassistant_process_next_action_stage
sensor.brewassistant_status_summary
sensor.brewassistant_smart_recommendation_summary
sensor.brewassistant_smart_heat_recommendation
sensor.brewassistant_smart_cooling_recommendation
sensor.brewassistant_smart_fan_recommendation
```

Scope guard behavior:

```text
No active fermentation/batch context
→ process_status: Idle
→ process_current_action_stage: none
→ temperature_status: Standby
→ temperature_severity: ok
→ problem_level: ok
```

A stale cold-crash helper alone should not keep fermentation warnings active.

---

## Source diagnostics

BrewAssistant exposes source/diagnostic sensors for configured source entities and health information.

Examples:

```text
sensor.brewassistant_source_health_summary
sensor.brewassistant_source_health_level
sensor.brewassistant_gravity_last_updated
sensor.brewassistant_batch_started_at
sensor.brewassistant_batch_age_hours
sensor.brewassistant_batch_age_days
```

---

## Migration guidance

Do not rename everything blindly.

Recommended approach:

1. Keep working dashboards stable.
2. Let Python entities take canonical `sensor.brewassistant_*` names.
3. If old YAML/template entities block canonical names locally, rename old entities with a `_yaml` suffix.
4. Update dashboard cards to read Python entities.
5. Remove old helper/template dependencies after validation.
6. Keep dashboard YAML as presentation only.

---

## Design rule

If a piece of logic affects brewing decisions, place it in Python.

If it only affects how something looks, place it in the dashboard card.
