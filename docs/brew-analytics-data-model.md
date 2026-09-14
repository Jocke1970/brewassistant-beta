# BrewAssistant Brew Analytics Data Model

Status: design baseline / implementation pending  
Last synced: 2026-09-15

This document defines the storage contract for BrewAssistant completed-batch analytics.

Read together with:

- [`brew-analytics-roadmap.md`](brew-analytics-roadmap.md)
- [`brew-analytics-metrics.md`](brew-analytics-metrics.md)
- [`brewzilla-equipment-learning.md`](brewzilla-equipment-learning.md)

## Design rule

Never store only the final calculated number.

Persist enough raw evidence that a later BrewAssistant version can recalculate derived metrics with improved formulas without losing the original brewday result.

```text
raw measurement
  + source/provenance
  + measurement basis
  + calculation version
  = reproducible analytics
```

## Storage roles

Suggested Home Assistant storage:

```text
DATA_KEY:    brew_analytics
STORAGE_KEY: brewassistant_brew_analytics
```

Suggested top-level model:

```yaml
schema_version: 1
calculation_version: 1
batches: {}
profiles: {}
recommendations: {}
```

The exact storage key is not fixed until implementation, but schema versioning is mandatory.

## Batch identity

One physical brewday must map to one stable analytics batch record.

Preferred identifiers, in order:

```text
1. canonical BrewAssistant brewday/session id
2. Brewfather batch id + physical brewday session id
3. generated BA UUID when no upstream stable id exists
```

Never use recipe name alone as identity.

Example:

```yaml
batch_id: "ba_20260915_7f4d..."
brewday_session_id: "..."
brewfather_batch_id: "..."
recipe_name: "Norrlands Djup Clone"
```

## Three data layers

Every batch contains three distinct layers.

### 1. Targets

Values planned before brewing.

Examples:

```text
target batch volume
target OG
target pre-boil volume
target pre-boil gravity
target post-boil volume
target mash efficiency
target brewhouse efficiency
target boil-off
```

Targets are useful for comparison, but they are not measurements.

### 2. Measurements

Values physically observed or explicitly entered.

Examples:

```text
actual pre-boil volume
actual pre-boil gravity
actual post-boil volume
actual OG
actual fermenter volume
actual mash water
actual sparge water
actual boil duration
```

### 3. Derived values

Values calculated from targets and/or measurements.

Examples:

```text
boil-off L/h
transfer loss
normalized efficiency delta
BA-calculated mash efficiency
BA-calculated brewhouse efficiency
historical profile recommendation
```

Derived values must always carry a calculation version.

## Measurement object

A measurement should not be stored as a naked float when provenance matters.

Suggested structure:

```yaml
pre_boil_volume_l:
  value: 26.8
  unit: L
  observed_at: "2026-09-15T18:42:00+02:00"
  source: brewfather_measured
  source_entity: null
  method: manual_entry
  temperature_basis: near_boiling
  quality: operator_confirmed
  notes: null
```

Not every field needs every attribute in serialized storage if defaults are well-defined, but the model should preserve these concepts.

## Measurement provenance

Suggested `source` enum:

```text
operator_manual
brewfather_measured
brewfather_target
brewday_runtime
home_assistant_sensor
rapt_cloud_link
brewzilla_device
derived
imported_history
unknown
```

Suggested quality flags:

```text
operator_confirmed
automatic_boundary_capture
stable_sensor_reading
single_sensor_sample
estimated
inferred
stale_source
incomplete_context
```

Multiple flags may be needed.

## Volume basis

Volume without temperature context can create false losses.

Suggested `temperature_basis` values:

```text
cold
ambient
mash_temperature
near_boiling
hot_post_boil
unknown
```

Where possible also store:

```yaml
measurement_temperature_c: 98.5
```

Do not normalize raw stored values in place. If a normalized cold-equivalent or hot-equivalent volume is needed, store it as a derived value.

## Gravity basis

Suggested fields:

```yaml
pre_boil_sg:
  value: 1.044
  source: operator_manual
  instrument: hydrometer
  sample_temperature_c: 20.0
  corrected_to_c: 20.0
  wort_state: unfermented
```

Instrument enum may include:

```text
hydrometer
refractometer
rapt_pill
other_digital
unknown
```

For unfermented wort, refractometer readings may be usable when converted correctly. Fermented-wort correction is outside the first hot-side analytics scope.

## Equipment context

Suggested batch context:

```yaml
equipment:
  equipment_id: brewzilla_gen4_35l
  equipment_name: BrewZilla Gen4 35L
  configuration_revision: null

method:
  id: biab_no_sparge
  bag_used: true
  malt_pipe_used: false
  sparge_used: false
```

If the physical setup changes materially, `configuration_revision` should let analytics avoid pretending the old and new setup are identical.

Examples of material changes:

```text
new dip tube
new CFC
new transfer hose layout
new malt pipe or false bottom
major sensor relocation
major heating/control change
```

## Recipe / batch context

Suggested fields:

```yaml
recipe:
  name: "Norrlands Djup Clone"
  source: brewfather
  source_recipe_id: null
  grain_weight_kg: 5.20
  fermentables_potential_available: false
  target_og: 1.054
  target_fg: 1.012

batch:
  target_volume_l: 21.0
  target_volume_basis: fermenter
  boil_time_min: 60
```

Do not assume every recipe exposes fermentable yield/potential data. Absolute efficiency calculations must report insufficient data if the required potential extract is unavailable and no authoritative upstream efficiency value exists.

## Water context

Suggested raw fields:

```yaml
water:
  mash_water_l: 26.0
  sparge_water_l: 0.0
  top_up_kettle_l: 0.0
  top_up_fermenter_l: 0.0
  mash_tun_deadspace_l: 0.0
  mash_tun_loss_l: 0.0
```

These values are necessary to estimate grain absorption and reconcile process volumes.

Unknown must remain `null`; do not substitute `0.0` unless zero is an actual known process value.

## Process-boundary measurements

Initial canonical boundaries:

```text
mash_water_loaded
mash_complete
pre_boil
post_boil_hot
post_chill_kettle
fermenter_transfer_complete
```

Not every brew will have all boundaries.

Suggested fields:

```yaml
measurements:
  pre_boil_volume_l: {...}
  pre_boil_sg: {...}
  post_boil_volume_l: {...}
  post_boil_sg: {...}
  original_gravity_sg: {...}
  fermenter_volume_l: {...}
```

## Imported Brewfather values

If Brewfather exposes calculated actual values, preserve them separately rather than overwriting BA calculations.

Example:

```yaml
upstream_results:
  brewfather_actual_mash_efficiency_pct: 78.4
  brewfather_actual_brewhouse_efficiency_pct: 73.1
```

BA may also calculate:

```yaml
derived:
  ba_mash_efficiency_pct:
    value: 78.2
    calculation_version: 1
  ba_brewhouse_efficiency_pct:
    value: 72.9
    calculation_version: 1
```

Differences become diagnostics, not silent replacements.

## Derived-value object

Suggested structure:

```yaml
boiloff_l_per_h:
  value: 3.18
  calculation_version: 1
  quality: high
  inputs:
    - pre_boil_volume_l
    - post_boil_volume_l
    - boil_duration_min
  notes: "same hot-volume basis"
```

## Abnormal-process flags

Historical analytics needs to know when a batch was not representative.

Suggested flags:

```text
aborted
partial_batch
major_spill
large_unplanned_topup
large_unplanned_dilution
measurement_error_suspected
sensor_failure
stuck_mash_or_flow_issue
recipe_changed_during_brew
incorrect_grain_bill
unknown_transfer_loss
experimental_hardware
```

A flagged batch is retained forever unless explicitly deleted by the operator.

The aggregate layer may exclude or down-weight it with an explanation.

## Analytics profile key

Exact profile key:

```text
<equipment>|<configuration_revision>|<method>|target:<volume>L
```

Example:

```text
brewzilla_gen4_35l|rev:1|biab_no_sparge|target:21L
```

Fallback volume buckets may be derived dynamically:

```text
vol:5-9L
vol:15-18L
vol:20-23L
```

These bucket boundaries are not fixed by this document. Exact raw volumes remain authoritative.

## Profile aggregate

Suggested shape:

```yaml
profile_key: "brewzilla_gen4_35l|rev:1|biab_no_sparge|target:21L"
updated_at: "..."
batch_ids:
  - "..."
metrics:
  brewhouse_efficiency_pct:
    count: 8
    mean: 72.9
    median: 73.1
    stddev: 1.4
    min: 70.8
    max: 75.0
    last_n_mean: 73.4
  boiloff_l_per_h:
    count: 7
    mean: 3.18
    stddev: 0.16
confidence:
  state: high
  reasons:
    - "8 comparable batches"
    - "7 complete measurement sets"
```

Aggregates are disposable caches. They must be reproducible from raw batch records.

## Recommendation record

Recommendation history must be persistent and auditable.

Suggested shape:

```yaml
recommendation_id: "..."
created_at: "..."
profile_key: "..."
field: brewhouse_efficiency_pct
current_value: 75.0
recommended_value: 73.0
raw_model_value: 72.9
confidence: high
sample_count: 8
calculation_version: 1
state: pending
source_batch_ids:
  - "..."
```

Suggested states:

```text
pending
accepted
rejected
superseded
reverted
```

Acceptance does not imply automatic Brewfather mutation. It only records operator intent unless a separate adapter/apply path explicitly performs a write.

## Correction policy

Raw history must be correctable because measurement-entry mistakes happen.

Corrections should preserve audit history.

Suggested model:

```yaml
corrections:
  - corrected_at: "..."
    field: measurements.fermenter_volume_l
    previous_value: 20.1
    new_value: 20.8
    reason: "wrong sight-glass reading entered"
    actor: operator
```

After correction:

```text
- recompute derived metrics
- recompute affected aggregates
- supersede stale recommendations if necessary
```

## Retention

Completed-batch raw analytics should not be tied to Home Assistant recorder retention.

Recorder history is useful for live sensor forensics, but Brew Analytics needs its own persistent compact result model so a 14-day or 30-day recorder purge does not destroy long-term equipment learning.

## Privacy / export

Exports should contain brewing process data only unless explicitly requested.

Suggested export scopes:

```text
single batch
single equipment profile
all analytics history
```

JSON is the canonical machine-readable export. Markdown/CSV may be added for human inspection.
