# BrewZilla Equipment Learning

Status: v1 / passive evidence model  
Last synced: 2026-07-16

This document describes the persistent BrewZilla equipment-learning layer.

The purpose is to make BrewAssistant learn the behavior of a specific BrewZilla setup over repeated runs instead of relying only on generic hard-coded profiles.

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

## Separation of responsibilities

```text
Analysis / Advice:
  live snapshot, current delta/rate/risk, immediate profile recommendation

Equipment Learning:
  persistent evidence grouped by equipment, context, volume, grain and phase

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

## Expected summary states

Possible high-level summaries:

```text
Learning disabled
No equipment observations yet
N observations / M profile buckets
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
```

It may:

```text
- observe live advice/control state
- persist evidence
- aggregate profile buckets
- create candidate suggestions
- expose diagnostics through sensors
```

## Future work

Planned next steps:

```text
- add APPLY/DENY flow for learned profile suggestions
- store accepted profile overrides separately from built-in defaults
- add dashboard card for equipment learning
- add phase models for heat-strike, mash-in drop, mash ramps, mash holds, mash-out and boil ramp
- calculate strike target offset from observed mash-in drop
- calculate practical taper points per batch size and grain load
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

A suggestion is useful only if its evidence matches the actual brew context. Water-only observations should not be treated as real-mash profile data.
