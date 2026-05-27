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
brewassistant_fermentation_*           Fermentation runtime, stats and air-target recommendations
brewassistant_source_*                 Source diagnostics
brewassistant_climate_*                Climate Supervisor and dynamic air-target logic
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

## Climate Supervisor entities

Climate Supervisor is the active control path for carbonation/serving air-target management.

Primary entity:

```text
switch.brewassistant_climate_supervisor_enabled
```

Raw/controlled entities:

```text
climate.kegerator_kylskap
sensor.kyl_temperatur_4
sensor.brewassistant_carbonation_status
sensor.brewassistant_carbonation_temperature
switch.kegerator
```

Important attributes on `switch.brewassistant_climate_supervisor_enabled`:

```text
mode
status
action
reason
base_target_temperature
effective_air_target
air_temperature
air_delta
cooling_demand
controller_entity
controller_state
controller_target_temperature
target_delta
carbonation_active
carbonation_status
carbonation_temperature
legacy_guard_enabled
last_control_action
last_evaluation
summary
```

Current states/status examples:

```text
strong_cooling
cooling
mild_cooling
hold
hold_warm
relax
standby
unavailable
```

Current rule:

```text
Climate Supervisor adjusts climate.kegerator_kylskap target.
climate.kegerator_kylskap controls switch.kegerator.
BrewAssistant does not directly control switch.kegerator during normal supervisor operation.
```

Deprecated/parked entity:

```text
switch.brewassistant_kegerator_guard_enabled
```

This should remain off during normal operation.

---

## Temperature Stats entities

Temperature Stats provides rolling average/trend sensors for kegerator air, chamber air, fermentation liquid and air/liquid delta.

Current entities:

```text
sensor.brewassistant_kegerator_air_temperature_average
sensor.brewassistant_fermentation_chamber_air_temperature_average
sensor.brewassistant_fermentation_liquid_temperature_average
sensor.brewassistant_fermentation_air_liquid_delta_average
```

Common attributes:

```text
current
average_5m
average_15m
average_30m
minimum_30m
maximum_30m
trend_c_per_hour
trend_label
sample_count
source_entity
source_status
sample_allowed
fermentation_scope_active
real_liquid_source_available
summary
```

Important scope rule:

```text
Kegerator air and chamber air may always sample.
Fermentation liquid and air/liquid delta only sample when a real liquid source exists and fermentation/cold-crash scope is active.
Fallback chamber air is not sampled as liquid.
```

Possible source states:

```text
sampling
fallback_not_sampled
out_of_scope_not_sampled
not_sampled
```

---

## Fermentation Air Target entities

The Fermentation Air Target Engine is read-only. It calculates a recommended chamber-air target for future fermentation/cold-crash supervision.

Current entities:

```text
sensor.brewassistant_fermentation_effective_air_target
sensor.brewassistant_fermentation_climate_demand
sensor.brewassistant_fermentation_climate_mode
sensor.brewassistant_fermentation_air_target_reason
sensor.brewassistant_fermentation_liquid_delta
sensor.brewassistant_fermentation_air_liquid_delta
sensor.brewassistant_fermentation_air_target_summary
```

Important attributes on `sensor.brewassistant_fermentation_effective_air_target`:

```text
ready
scope_active
mode
demand
reason
liquid_temperature
liquid_target_temperature
liquid_delta
liquid_trend_c_per_hour
chamber_air_temperature
air_liquid_delta
effective_air_target
air_target_delta
real_liquid_source_available
liquid_source
liquid_source_entity
target_mode
process_status
process_stage
summary
source
control
```

Current modes:

```text
standby
fermentation
cold_crash
```

Current demand examples:

```text
standby
unavailable
strong_cooling
cooling
mild_cooling
nudge_cooling
settle
hold
relax
ease_cooling
hold_warm
warm_or_relax
```

Scope-safe standby behavior:

```text
mode = standby
demand = standby
effective_air_target = unknown
liquid_delta = unknown
air_liquid_delta = unknown
ready = false
scope_active = false
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

Current restart semantics:

```text
Finish → Start
= starts a new run from Setup / Prepare equipment

Finish → Reset → Prepare/Start
= clean new session
```

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
prep
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
prepared/setup/prepare equipment maps to Prepare, not Strike Water.
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
started_at and age_days are persisted across Home Assistant restarts.
```

Validated example:

```text
started_at = 2026-05-24T08:20:00+00:00
age_days = 2.53
estimated = 1.11 vol
progress = 16.8 %
```

Current open design question:

```text
progress_percent currently needs validation: level-percent vs separate level/process progress.
```

---

## Fermentation entities

Fermentation currently has coordinator-owned process/scope sensors, rolling stats, read-only air-target recommendations and older smart recommendation sensors, with a planned Python-owned Timed Fermentation Runtime later.

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
