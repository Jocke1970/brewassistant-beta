# BrewZilla Equipment Learning

Status: v1 passive evidence model / v2 BF timing advisor plan  
Last synced: 2026-07-23

This document describes the persistent BrewZilla equipment-learning layer.

The purpose is to make BrewAssistant learn the behavior of a specific BrewZilla setup over repeated runs instead of relying only on generic hard-coded profiles.

The current implementation is intentionally passive. It records evidence and exposes diagnostics. It must not silently change BrewZilla control behavior or rewrite Brewfather recipes/profiles.

## Why this exists

The earlier `brewzilla_learning.py` layer mostly answered:

```text
What is happening right now?
```

It calculated delta to target, temperature rate, mash/wort difference, overshoot risk and recommendations. That is useful analysis, but it is not enough to build equipment-specific brewing profiles.

The equipment-learning layer answers a different question:

```text
What has this specific BrewZilla repeatedly shown us under similar conditions?
```

The next advisor layer answers:

```text
Given what this setup has shown, what Brewfather timing/profile values should the brewer consider for the next batch?
```

## Separation of responsibilities

```text
Analysis / Advice:
  live snapshot, current delta/rate/risk, immediate profile recommendation

Equipment Learning:
  persistent evidence grouped by equipment, context, volume, grain and phase

BF Timing / Profile Advisor:
  human-reviewable Brewfather timing/profile suggestions for future batches

Profile Suggestion:
  candidate profile change for later operator review
```

The learning model does **not** auto-apply profile changes.

## Storage

The model is stored with Home Assistant storage using:

```text
DATA_KEY:    brewzilla_equipment_learning
STORAGE_KEY: brewassistant_brewzilla_equipment_learning
```

It is loaded at integration startup and updated during supervised active hot-side stages.

### Storage roles

```text
Home Assistant storage:
  source of truth for machine-readable learning history and rolling models

Sensors:
  current summary, dashboard status, latest segment and latest suggestions

Optional export files:
  human-readable per-batch learning reports and offline analysis artifacts
```

The stored model should remain independent from live control. Accepted future overrides should be stored separately from built-in defaults and should require explicit operator review/apply.

## Sampling

The v1 layer samples automatically every 30 seconds while the runtime/stage is relevant.

Current active states:

```text
live
running
paused
prepared
awaiting_snapshot
awaiting_confirm
```

Current learning stages:

```text
ramp
mash_hold
boil
```

Duplicate auto-snapshots are ignored when the runtime/temperature/utilization signature has not changed.

## Profile buckets

Evidence is grouped into profile keys like:

```text
brewzilla_gen4_35l|Real mash|vol:10-13L|grain:3-5kg|ramp
```

Bucket dimensions:

```text
equipment_id
learning_context: Real mash / Water only / Unknown
volume bucket: mash water or pre-boil volume
grain bucket: grain amount
stage kind: ramp / mash_hold / boil
```

This lets BA distinguish, for example:

```text
water-only plumbing test
small real mash 9-13 L
larger real mash 16+ L
low-grain vs high-grain mash
```

Future advisor buckets may add:

```text
ambient temperature bucket
start-water temperature bucket
season / room-condition bucket
RCL quality bucket
sensor-source quality bucket
```

Those buckets are advisory context only. They should improve confidence and explainability, not split the evidence so aggressively that every batch becomes unique and unlearnable.

## Observation fields

Each recorded observation may include:

```text
observed_at
runtime_state
stage
step
next_step
stage_kind
learning_context
batch_context_source
grain_amount_kg
mash_water_l
pre_boil_volume_l
target_temperature
mash_temperature
wort_temperature
mash_gap_to_target
wort_over_target
mash_wort_lag
heat_utilization
pump_utilization
heater_on
pump_on
temp_rate_c_per_min
overshoot_risk
advice_phase
suggested_heat_utilization
advice_local_profile_heat_utilization
advice_thermal_mix_active
advice_thermal_mix_heat_cap
advice_thermal_mix_reason
```

Planned v2 timing-advisor observations should also capture, where available:

```text
recipe_name
batch_id_or_session_id
planned_step_duration_min
planned_step_target_temperature
segment_start_at
segment_end_at
segment_start_temperature
segment_target_temperature
actual_time_to_target_min
actual_time_to_stable_min
max_mash_temperature
max_wort_temperature
max_mash_overshoot_c
max_wort_overshoot_c
avg_rate_c_per_min
room_temperature_c
water_start_temperature_c
RCL_stale_seconds_total
RCL_refresh_count
primary_temperature_source
safety_temperature_source
```

## Segment model

For each profile bucket, BA keeps rolling stats such as:

```text
count
first_seen_at
last_seen_at
avg_mash_wort_lag_c
avg_temp_rate_c_per_min
avg_mash_gap_to_target_c
avg_wort_over_target_c
max_mash_overshoot_c
max_wort_over_target_c
rate_by_heat_utilization
thermal_mix_low_cap_cases
```

`rate_by_heat_utilization` groups observed ramp/hold rates into heat-utilization buckets such as `050%`, `060%`, `070%`.

Future v2 segment models should also keep planned-vs-actual timing stats:

```text
planned_duration_min_avg
actual_time_to_target_min_avg
actual_time_to_stable_min_avg
actual_minus_planned_min_avg
suggested_bf_duration_min
confidence
sample_count_by_recipe_family
sample_count_by_environment_bucket
```

## Segment types for BF timing advisor

The BF timing advisor should reason over explicit physical segments, not just generic Brewfather steps.

Initial segment types:

```text
heatstrike
mash_in_drop
mash_ramp
mash_hold
mash_out
boil_ramp
boil
```

Example segment definitions:

```text
heatstrike:
  start: strike target is latched/applied
  done: mash/BLE gate reaches strike readiness or ready_for_mash_in is reached

mash_in_drop:
  start: Mash-In Started
  done: mash temperature stabilizes near first mash target or Mash-In Complete starts circulation

mash_ramp:
  start: target changes from one mash rest to a higher mash rest
  done: mash/BLE reaches target or stabilizes within tolerance

boil_ramp:
  start: runtime enters boil ramp / boil target intent
  done: boil is detected or kettle temperature reaches practical boil threshold
```

The advisor should preserve both:

```text
planned duration from Brewfather
actual duration measured by BrewAssistant
```

That lets BA explain whether a Brewfather step is too short, too long or already close enough.

## BF timing recommendations

The advisor should create human-reviewable suggestions such as:

```text
Heatstrike 22 -> 71.8°C:
  planned: 30 min
  observed: 28-31 min
  suggestion: keep 30 min
  confidence: medium/high

Mash ramp 66 -> 72°C:
  planned: 9 min
  observed time to stable mash: 9-10 min
  suggestion: use 10 min or keep 9 min and accept slight lag
  confidence: medium

Boil ramp:
  planned: unknown
  observed: insufficient data
  suggestion: collect another run
  confidence: low
```

The suggestion should include enough context for the brewer to judge whether it applies:

```yaml
context:
  equipment_id: brewzilla_gen4_35l
  learning_context: Real mash
  volume_bucket: vol:10-13L
  grain_bucket: grain:2-3kg
  room_temperature_c: 22.4
  water_start_temperature_c: 21.8
  rcl_quality: partial_stale_periods
```

## Profile suggestion v1

The first v1 suggestion is deliberately narrow and tied to the real-mash issue seen during testing:

```text
Real mash is active
stage is ramp or mash_hold
thermal mix is active
mash is at least 2°C below target
wort/internal is less than 5°C above target
profile heat cap has collapsed to <=10%
live advice still suggests high heat, or has no better suggestion
```

When that pattern is observed, BA may create a candidate suggestion:

```text
thermal_mix.ramp_mash_priority_floor      -> 45 %
thermal_mix.mash_hold_mash_priority_floor -> 30 %
```

The suggestion is marked:

```text
candidate_requires_operator_apply
```

It is evidence only. It does not mutate the active profile.

## Sensors

The v1 layer exposes high-level state through existing BrewZilla learning sensors:

```text
sensor.brewassistant_brewzilla_equipment_learning_summary
sensor.brewassistant_brewzilla_equipment_learning_observations
sensor.brewassistant_brewzilla_equipment_learning_segments
sensor.brewassistant_brewzilla_equipment_learning_profile_key
sensor.brewassistant_brewzilla_equipment_learning_suggestion
```

The regular BrewZilla learning sensors also carry the equipment-learning snapshot in attributes.

Future advisor-facing sensors should expose short states with detailed attributes:

```text
sensor.brewassistant_brewzilla_learning_bf_suggestions
sensor.brewassistant_brewzilla_learning_current_segment
sensor.brewassistant_brewzilla_learning_last_segment_result
sensor.brewassistant_brewzilla_learning_batch_report
sensor.brewassistant_brewzilla_learning_confidence
```

Example state/attributes:

```yaml
state: "2 suggestions · confidence medium"
attributes:
  suggestions:
    heatstrike_time_min: 30
    ramp_66_72_time_min: 9
    boil_ramp_time_min: null
  confidence:
    heatstrike: high
    ramp_66_72: medium
    boil_ramp: low
  evidence:
    observations_total: 42
    segment_count: 5
    batches: 2
```

## Optional export files

A future export service may write reports under `/config/brewassistant/learning/`:

```text
/config/brewassistant/learning/brewzilla_learning_summary.json
/config/brewassistant/learning/batches/YYYY-MM-DD_<batch_slug>.json
/config/brewassistant/learning/batches/YYYY-MM-DD_<batch_slug>.md
```

The JSON file is for machine-readable backup and offline analysis. The Markdown file is for the brewer.

Example report content:

```text
BrewAssistant Learning Report
Batch: Test batch
Heatstrike: planned 30 min, observed 29.4 min, suggestion keep 30 min
Ramp 66 -> 72°C: planned 9 min, observed 9.8 min, suggestion 10 min
Boil ramp: insufficient data
```

## Expected summary states

Possible high-level summaries:

```text
Learning disabled
No equipment observations yet
N observations / M profile buckets
N observations / M profile buckets · suggestion: ...
N BF timing suggestions · confidence medium
```

## Safety philosophy

Equipment learning is passive.

It must not:

```text
- change target temperature
- change heat utilization
- change pump utilization
- turn heater or pump on/off
- override abort/safe-down logic
- silently rewrite profile parameters
- silently rewrite Brewfather recipe or equipment-profile timings
```

It may:

```text
- observe live advice/control state
- persist evidence
- aggregate profile buckets
- create candidate suggestions
- expose diagnostics through sensors
- export human-readable batch reports
```

Any future APPLY/DENY flow must be explicit, reversible and separate from the built-in defaults.

## Future work

Planned next steps:

```text
- add APPLY/DENY flow for learned profile suggestions
- store accepted profile overrides separately from built-in defaults
- add dashboard card for equipment learning
- add BF timing advisor sensors for heatstrike, mash ramps, mash-out and boil ramp
- add optional JSON/Markdown learning-report export after a supervised batch
- add phase models for heat-strike, mash-in drop, mash ramps, mash holds, mash-out and boil ramp
- calculate strike target offset from observed mash-in drop
- calculate practical taper points per batch size and grain load
- calculate recommended Brewfather step durations from planned-vs-actual segment data
- track ambient temperature and start-water temperature when HA sensors are available
- track RCL quality and stale periods per session
- compare predicted vs actual target hit and overshoot
```

## What to check after a test

After a supervised brew test, check:

```yaml
brewzilla_equipment_learning_observations: ...
brewzilla_equipment_learning_segments: ...
brewzilla_equipment_learning_profile_key: ...
brewzilla_equipment_learning_suggestion: ...
```

For future BF timing advisor validation, also check:

```yaml
current_segment: heatstrike | mash_ramp | mash_out | boil_ramp | boil
planned_duration_min: ...
actual_time_to_target_min: ...
actual_time_to_stable_min: ...
suggested_bf_duration_min: ...
confidence: low | medium | high
```

A suggestion is useful only if its evidence matches the actual brew context. Water-only observations should not be treated as real-mash profile data.