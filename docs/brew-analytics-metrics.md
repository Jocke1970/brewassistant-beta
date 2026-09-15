# BrewAssistant Brew Analytics Metrics

Status: design baseline / implementation pending  
Last synced: 2026-09-15

This document defines the first-pass metric vocabulary and calculation rules for BrewAssistant Brew Analytics.

Read together with:

- [`brew-analytics-roadmap.md`](brew-analytics-roadmap.md)
- [`brew-analytics-data-model.md`](brew-analytics-data-model.md)
- [`brewzilla-equipment-learning.md`](brewzilla-equipment-learning.md)

## General rule

A metric name must identify what was actually measured or calculated.

Do not label an estimate as an authoritative actual value.

Examples:

```text
brewfather_actual_brewhouse_efficiency_pct
ba_calculated_brewhouse_efficiency_pct
ba_normalized_brewhouse_efficiency_estimate_pct
```

These may all exist at once.

## Brewfather boundary definitions

Brewfather treats:

```text
Mash Efficiency
  -> efficiency of the mash process up to pre-boil, including sparging

Brewhouse Efficiency
  -> overall efficiency through the fermenter boundary, including losses to fermenter
```

BrewAssistant should retain those same process boundaries.

References:

- https://docs.brewfather.app/getting-started/setting-up-your-equipment-profile
- https://docs.brewfather.app/getting-started/your-first-batch

## Gravity points

For normalized comparisons:

```text
gravity_points = (SG - 1.000) * 1000
```

Examples:

```text
1.050 -> 50 points
1.062 -> 62 points
```

For simple extract-content comparisons within the same unit system:

```text
wort_points = gravity_points * volume_l
```

This is useful for target-vs-actual normalization, but it is not by itself an absolute malt-extract efficiency calculation.

## Absolute mash efficiency

Absolute mash efficiency requires the extract potential of the fermentables.

Conceptually:

```text
mash_efficiency = extracted_pre_boil_sugars / theoretical_fermentable_potential
```

Inputs generally require:

```text
pre-boil gravity
pre-boil volume
fermentable weights
yield/potential for each fermentable
```

Implementation rule:

```text
If complete fermentable potential is unavailable:
  do not invent absolute mash efficiency.
```

Preferred source order:

```text
1. Brewfather actual mash-efficiency value, if available from the batch
2. BA absolute calculation from complete fermentable-potential data
3. unavailable
```

A target-relative estimate may be shown separately, but must not be named `actual_mash_efficiency`.

## Absolute brewhouse efficiency

Conceptually:

```text
brewhouse_efficiency = extract reaching fermenter / theoretical_fermentable_potential
```

Inputs generally require:

```text
fermenter volume
OG at fermenter boundary
fermentable weights
yield/potential for each fermentable
```

As with mash efficiency, if potential extract is unavailable, BA must not fabricate an absolute result.

Preferred source order:

```text
1. Brewfather actual brewhouse-efficiency value, if available
2. BA absolute calculation from complete fermentable-potential data
3. target-relative normalized estimate, clearly named as an estimate
4. unavailable
```

## Target-relative brewhouse-efficiency estimate

This is useful when Brewfather target efficiency and target output are known but complete fermentable potential is not available.

For an unchanged recipe and a fermenter-volume-target profile:

```text
normalized_actual_efficiency
  = target_efficiency
    * (actual_gravity_points * actual_fermenter_volume)
    / (target_gravity_points * target_fermenter_volume)
```

Example:

```text
target BH efficiency = 75.0 %
target OG            = 1.050
target fermenter     = 21.0 L
actual OG            = 1.052
actual fermenter     = 20.5 L

estimate
  = 75.0 * (52 * 20.5) / (50 * 21.0)
  ~= 76.1 %
```

This estimate is only valid when the target and actual values describe the same recipe/extract basis.

Do not use it when:

```text
- the grain bill changed materially
- fermenter top-up/dilution changed and is not accounted for
- extract/sugar additions changed after the target was generated
- target batch basis is Kettle rather than Fermenter
- actual OG and actual volume refer to different process points
```

Suggested metric name:

```text
ba_normalized_brewhouse_efficiency_estimate_pct
```

## Efficiency delta

When authoritative or compatible target/actual efficiency values exist:

```text
efficiency_delta_pct_points = actual_efficiency_pct - target_efficiency_pct
```

Use percentage points, not percent change.

Example:

```text
target 75.0 %
actual 72.9 %
delta  -2.1 percentage points
```

## Boil-off rate — L/h

When pre-boil and post-boil volumes share the same thermal basis:

```text
boiloff_l = pre_boil_volume_l - post_boil_volume_l
boiloff_l_per_h = boiloff_l / (boil_duration_min / 60)
```

Example:

```text
pre-boil   27.0 L
post-boil  23.8 L
boil       60 min

boil-off = 3.2 L/h
```

Required validity checks:

```text
- same volume temperature basis, or normalized first
- no untracked kettle top-up during boil
- no large sample/removal loss included in the volume difference
- actual boil duration known
```

## Boil-off rate — percent/hour

Optional comparison metric:

```text
boiloff_pct_per_h
  = boiloff_l_per_h / pre_boil_volume_l * 100
```

Absolute L/h remains the primary equipment-profile metric because Brewfather equipment profiles use a boil-off volume rate.

## Thermal volume normalization

Brewfather's normal equipment-profile calculation commonly accounts for about 4% hot/cold expansion/shrinkage.

BrewAssistant should not silently assume that every raw volume is cold or hot.

Suggested rule:

```text
raw volume remains unchanged
normalized volume is derived separately
```

If a configurable expansion factor is used:

```text
cold_equivalent_volume
  = hot_volume / (1 + expansion_fraction)
```

Example with 4%:

```text
24.0 L hot -> 23.08 L cold-equivalent
```

The exact factor should be a versioned/configurable calculation input, not a magic value hidden inside unrelated formulas.

## Transfer / trub / chiller loss

For a Brewfather-equivalent fermenter-target profile, this should approximate wort that does not reach the fermenter after boil/chill/transfer.

Preferred direct measurement:

```text
transfer_loss_l
  = cooled_kettle_volume_before_transfer
    - fermenter_volume_after_transfer
```

If only hot post-boil volume exists:

```text
1. normalize hot post-boil volume to the fermenter-volume basis
2. subtract fermenter volume
```

This value may include:

```text
kettle trub
hop material
CFC hold-up
hoses/pipes
unrecoverable transfer residue
```

For the initial BrewZilla/CFC use case, this maps naturally to Brewfather `Trub/Chiller Loss` when the measurement boundaries match Brewfather's definition.

Do not include fermenter packaging loss in this metric.

## Fermenter loss

Packaging-side metric:

```text
fermenter_loss_l
  = volume_into_fermenter - packaged_volume
```

This is useful for Brewfather profile calibration but belongs to a later fermentation/packaging analytics slice if packaged volume is not currently captured reliably.

## Fermenter yield ratio

A simple process-output diagnostic:

```text
fermenter_yield_ratio
  = actual_fermenter_volume / target_fermenter_volume
```

Example:

```text
20.6 / 21.0 = 0.981 = 98.1 %
```

This is not an efficiency metric. It measures volume attainment only.

## Grain absorption

Conceptually:

```text
grain_absorption_l_per_kg
  = water retained by grain / grain_weight_kg
```

For a simple no-sparge, single-vessel process with well-defined boundaries, an estimate may be derived from:

```text
water_into_mash
- recoverable wort leaving mash
- known mash-tun loss
- known other water removals/additions
```

divided by grain weight.

For sparged processes the accounting is more complex because mash water and sparge water must be reconciled against pre-boil volume and known losses.

Implementation rule:

```text
Do not calculate grain absorption unless water accounting is complete enough to explain the volume balance.
```

Suggested result state:

```text
available
insufficient_water_accounting
unknown_grain_weight
abnormal_process
```

Brewfather recommends different starting ranges for one-vessel and BIAB configurations, which is another reason BrewAssistant must aggregate this metric by brewing method rather than globally.

## Mash volume balance

Diagnostic only:

```text
total_hot_side_water_input
  = mash_water
  + sparge_water
  + kettle_topup
```

A first-pass reconciliation can compare this against:

```text
pre_boil_volume
+ estimated_grain_retention
+ mash_tun_loss
+ known samples/removals
```

The residual is useful for finding bad measurements, but should not be forced to zero by silently changing one of the measured inputs.

## Process extract conservation check

For unfermented wort, gravity points times volume can be used as a rough consistency check between process boundaries.

Example:

```text
pre_boil_points  = pre_boil_gravity_points * pre_boil_volume
post_boil_points = post_boil_gravity_points * post_boil_volume
```

In an idealized boil with no sugar additions/removals, these should be broadly similar after accounting for measurement/temperature basis.

Large mismatch can trigger:

```text
measurement_inconsistency
untracked_sugar_addition
volume_basis_mismatch
gravity_sample_error
```

Do not treat this as exact mass-balance chemistry in v1.

## Batch-size / method aggregates

The first useful profile metrics are:

```text
mash_efficiency_pct
brewhouse_efficiency_pct
boiloff_l_per_h
transfer_loss_l
grain_absorption_l_per_kg
```

Aggregate dimensions:

```text
equipment_id
configuration_revision
method
nominal batch size or volume bucket
```

Possible later dimensions:

```text
grain-load bucket
high-gravity / normal-gravity family
hop-load family
ambient conditions
```

Avoid over-bucketing early data.

## Robust statistics

Store or calculate both conventional and robust summaries where practical.

Recommended:

```text
count
mean
median
standard deviation
median absolute deviation (MAD)
min
max
last-N mean
```

A future recommendation engine should prefer robust central tendency when one batch is obviously abnormal.

Do not delete the abnormal batch.

## Trend detection

A simple first implementation may compare:

```text
long-term median
vs
last 3-5 comparable batches
```

Possible states:

```text
stable
improving
declining
insufficient_data
```

Avoid claiming a trend from two batches.

## Confidence model

Confidence is multidimensional.

Inputs:

```text
sample_count
measurement_completeness
measurement_quality
spread
recency
method consistency
volume similarity
abnormal-batch fraction
```

Initial user-facing states:

```text
insufficient
low
medium
high
```

Example starting policy, subject to implementation testing:

```text
insufficient: fewer than 2 usable comparable batches
low:          2-3 usable batches or weak/incomplete measurements
medium:       4-7 usable batches with reasonable repeatability
high:         8+ usable batches with good completeness and low/moderate spread
```

Sample count alone must not force high confidence.

## Recommendation rounding

Recommendations should not chase decimal noise.

Initial display/application rounding may be:

```text
Brewhouse efficiency: nearest 1 percentage point
Mash efficiency:      nearest 0.5 or 1 percentage point
Boil-off:              nearest 0.1 L/h
Transfer loss:         nearest 0.1 L
Grain absorption:      nearest 0.05 L/kg
```

Store the unrounded model value separately.

Example:

```yaml
raw_model_value: 72.86
recommended_value: 73.0
```

## Stability threshold before suggesting changes

A recommendation should be suppressed when the expected benefit is smaller than normal process noise.

Example initial thresholds:

```text
BH efficiency change < 1 percentage point -> usually keep current
Mash efficiency change < 1 percentage point -> usually keep current
Boil-off change < 0.2 L/h -> usually keep current
Transfer loss change < 0.2 L -> usually keep current
```

These are roadmap defaults, not immutable constants.

## Candidate recommendation example

```yaml
metric: brewhouse_efficiency_pct
profile_key: brewzilla_gen4_35l|rev:1|biab_no_sparge|target:21L
current_profile_value: 75.0
raw_model_value: 72.86
recommended_value: 73.0
confidence: high
usable_batches: 8
excluded_batches: 1
spread_pct_points: 1.4
state: candidate_requires_operator_apply
```

## Validation strategy

Before recommendations are enabled, validate formulas against known batches where Brewfather already shows actual measured efficiency.

For each validation batch compare:

```text
Brewfather actual mash efficiency
vs BA calculated mash efficiency

Brewfather actual brewhouse efficiency
vs BA calculated brewhouse efficiency

Brewfather equipment-profile boil-off/loss expectations
vs BA derived physical measurements
```

Differences must be explainable before BA presents itself as a Brewfather calibration authority.

## Explicit non-goals for v1

Do not attempt in the first implementation:

```text
- automatic recipe optimization
- malt-lot yield correction
- advanced sugar mass chemistry
- automatic Brewfather profile writes
- autonomous BrewZilla control changes from efficiency history
- automatic deletion of statistical outliers
```

The first goal is trustworthy, reproducible equipment evidence.
