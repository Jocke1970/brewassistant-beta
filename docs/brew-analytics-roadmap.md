# BrewAssistant Brew Analytics / Equipment Calibration Roadmap

Status: design baseline / implementation pending  
Last synced: 2026-09-15

This document defines the roadmap for persistent brew-result analytics and equipment-profile calibration in BrewAssistant.

It complements [`brewzilla-equipment-learning.md`](brewzilla-equipment-learning.md).

The existing BrewZilla Equipment Learning layer focuses primarily on live thermal behavior, phase timing, utilization and equipment-specific control/profile evidence. Brew Analytics answers a different but related question:

```text
Given completed brew measurements over time, what does this brewing setup actually deliver?
```

The long-term goal is to let BrewAssistant build an evidence-based model of the brewer's real equipment behavior by batch size and brewing method, then produce explicit, reviewable equipment-profile recommendations.

## Core principles

```text
raw measurement first
  -> derived metric second
  -> aggregate evidence third
  -> recommendation last
```

Brew Analytics is advisory.

It must not silently:

```text
- rewrite a Brewfather recipe
- rewrite a Brewfather equipment profile
- change an active BrewZilla target
- change heat or pump utilization
- change water volumes during an active brew
- discard or rewrite historical raw measurements
```

Future profile changes must use an explicit operator review / APPLY / DENY flow.

## Relationship to Brewfather

Brewfather equipment profiles distinguish several separate physical concepts that Brew Analytics should preserve:

```text
Batch Volume
Brewhouse Efficiency
Mash Efficiency
Boil Off
Trub / Chiller Loss
Fermenter Loss
Mash-Tun Deadspace
Mash-Tun Loss
Grain Absorption
Water / Grain Ratio
Mash / Sparge calculation method
```

Brewfather defines mash efficiency at the pre-boil boundary and brewhouse efficiency at the fermenter boundary. BrewAssistant should therefore never treat them as interchangeable metrics.

Reference:

- https://docs.brewfather.app/getting-started/setting-up-your-equipment-profile
- https://docs.brewfather.app/getting-started/your-first-batch

## Brewing-method dimension

Analytics must not assume that one BrewZilla has one universal efficiency number.

At minimum, results should distinguish:

```text
normal
  malt pipe + sparging

biab
  bag + sparging

no_sparge
  malt pipe + full-volume mash

biab_no_sparge
  bag + full-volume mash
```

The operator-facing labels may be localized, but stored identifiers should remain stable English identifiers.

## Batch-size dimension

Store exact measured and target volumes. Do not throw away continuous data just because aggregation uses buckets.

The initial target profile sizes for BrewZilla Gen4 35 L are:

```text
5 L
6 L
8 L
9 L
15 L
18 L
20 L
21 L
23 L
```

Future aggregation may use either exact nominal profiles or neighboring volume buckets when sample counts are low.

Example profile key:

```text
brewzilla_gen4_35l|biab_no_sparge|target:21L
```

Example fallback bucket:

```text
brewzilla_gen4_35l|biab_no_sparge|vol:20-23L
```

## Target architecture

A future code layout may look like:

```text
custom_components/brewassistant/analytics/
  __init__.py
  models.py
  storage.py
  measurements.py
  calculations.py
  aggregation.py
  confidence.py
  recommendations.py
  report.py
  sensors.py
```

The exact file structure is not fixed by this roadmap. The ownership boundary is.

### Analytics owns

```text
- normalized completed-batch measurement records
- versioned derived calculations
- historical aggregates
- confidence / evidence quality
- calibration candidates
- human-readable batch analytics reports
```

### Analytics does not own

```text
- Brewday live-stage control
- BrewZilla safety/control
- active Brewfather recipe ownership
- Cooling hardware ownership
- Fermentation control
```

It may read normalized outputs from those domains.

## Data-source priority

Every measurement must retain provenance.

Suggested priority:

```text
1. explicit operator-entered measured value
2. Brewfather measured batch value
3. authoritative HA sensor captured at a defined process boundary
4. derived value from other measured values
5. recipe/profile target value
```

A target must never be relabeled as a measurement.

## Phase 0 — Documentation and contracts

Status: this document set.

Deliverables:

```text
[x] roadmap
[x] raw/derived data-model contract
[x] calculation and metric definitions
[x] relationship to existing Equipment Learning layer
[x] no-silent-apply safety contract
```

## Phase 1 — Batch result capture

Goal: persist one normalized analytics record per physical brewday.

Required first-pass fields:

```text
batch/session identity
equipment identity
recipe/profile identity if available
brewing method
target batch volume
actual fermenter volume
target OG
actual OG
pre-boil gravity
pre-boil volume
post-boil volume
boil duration
mash water
sparge water
grain amount
Brewfather target mash efficiency
Brewfather target brewhouse efficiency
Brewfather actual efficiency values when exposed
source/provenance for every measured value
```

Acceptance criteria:

```text
[ ] completed brew can be stored without requiring every optional field
[ ] missing measurements remain null/unknown, never zero-filled
[ ] record survives HA restart
[ ] raw record is immutable except through an explicit correction path
[ ] session/batch identity prevents accidental duplicate finalization
```

## Phase 2 — Derived metrics

Initial metrics:

```text
actual/observed mash efficiency
actual/observed brewhouse efficiency
normalized target-vs-actual efficiency delta
boil-off L/h
boil-off %/h
transfer / trub / chiller loss
fermenter yield ratio
volume deltas by process boundary
gravity-point deltas by process boundary
estimated grain absorption when sufficient measurements exist
```

Every derived value must include:

```text
calculation_version
input fields used
quality / completeness flags
```

Acceptance criteria:

```text
[ ] formula implementations have unit tests
[ ] hot vs cold volume basis is explicit
[ ] missing required inputs produce unavailable/insufficient_data
[ ] imported Brewfather actual efficiency and BA-calculated efficiency can coexist
```

## Phase 3 — Historical aggregation

Goal: answer what the setup repeatedly delivers under comparable conditions.

Aggregate by:

```text
equipment
brewing method
batch-size profile/bucket
optionally grain-load bucket
optionally recipe gravity family
```

Expose at minimum:

```text
sample count
median
mean
standard deviation / robust spread
minimum / maximum
last N average
last observation
trend direction
measurement-quality summary
```

Do not silently delete outliers. Keep the raw observation and mark it as excluded or down-weighted in a specific aggregate model.

Acceptance criteria:

```text
[ ] one bad batch does not destroy the long-term profile
[ ] operator can inspect which batches contribute to a recommendation
[ ] Water-only tests never contaminate real-wort efficiency aggregates
```

## Phase 4 — Confidence model

A recommendation requires more than a sample count.

Confidence should consider:

```text
number of comparable batches
measurement completeness
measurement provenance
spread / repeatability
age of evidence
method consistency
batch-volume similarity
recipe/gravity similarity where relevant
known abnormal process flags
```

Suggested user-facing states:

```text
insufficient
low
medium
high
```

Confidence must be explainable:

```text
High confidence: 8 comparable 20-23 L BIAB No Sparge batches,
7 complete measurement sets, low spread, no recent systematic drift.
```

## Phase 5 — Equipment-profile recommendations

Initial candidate fields:

```text
brewhouse efficiency
mash efficiency
boil-off L/h
trub/chiller/transfer loss
grain absorption
```

Potential later fields:

```text
water/grain ratio guidance
mash-volume limits
batch-size-specific efficiency curves
strike/timing values from BrewZilla Equipment Learning
```

Recommendation example:

```yaml
equipment: brewzilla_gen4_35l
method: biab_no_sparge
batch_profile_l: 21
field: brewhouse_efficiency
current_profile_value: 75.0
observed_recommendation: 72.9
confidence: high
samples: 8
spread: 1.4
state: candidate_requires_operator_apply
```

Rules:

```text
- no automatic promotion from candidate to active profile
- round recommendations sensibly; do not chase noise
- use a stability threshold before proposing small changes
- explain evidence and excluded batches
- recommendations remain reversible
```

## Phase 6 — Dashboard and reports

Suggested sensors:

```text
sensor.brewassistant_analytics_current_batch
sensor.brewassistant_analytics_last_batch_summary
sensor.brewassistant_analytics_brewhouse_efficiency
sensor.brewassistant_analytics_mash_efficiency
sensor.brewassistant_analytics_boiloff
sensor.brewassistant_analytics_transfer_loss
sensor.brewassistant_analytics_profile_confidence
sensor.brewassistant_analytics_profile_recommendation
```

Suggested dashboard areas:

```text
Current brew measurements
Last brew result
Historical efficiency by method / batch size
Equipment-profile calibration
Evidence / confidence
Pending profile candidates
```

Optional export:

```text
/config/brewassistant/analytics/batches/YYYY-MM-DD_<batch_slug>.json
/config/brewassistant/analytics/batches/YYYY-MM-DD_<batch_slug>.md
/config/brewassistant/analytics/equipment/brewzilla_gen4_35l.json
```

## Phase 7 — Brewfather-assisted calibration

Only after the analytics model is stable.

Possible flows:

```text
BA recommendation
  -> operator reviews
  -> BA produces a Brewfather-profile change set
  -> operator confirms
  -> adapter/API layer applies or exports it where technically supported
```

If direct profile writes are unavailable or undesirable, BA may instead show a field-by-field change sheet.

Example:

```text
BrewZilla Gen4 35L — BIAB No Sparge — 21 L

Brewhouse Efficiency: 75.0 -> 73.0 %
Mash Efficiency:      80.0 -> 78.5 %
Boil Off:              3.5 -> 3.2 L/h
Trub/Chiller Loss:     2.5 -> 2.3 L
Grain Absorption:      0.70 -> 0.67 L/kg
```

## Phase 8 — Predictive equipment model

Long-term / go-bananas territory.

Potential models:

```text
expected efficiency as a function of batch size
expected efficiency as a function of grain load
sparge vs no-sparge impact
BIAB vs malt-pipe impact
high-gravity penalty
expected pre-boil volume and gravity
expected post-boil volume
predicted fermenter yield
anomaly detection before a brew is finalized
```

Possible future output:

```text
Recipe target: 21.0 L @ 1.054
Method: BIAB No Sparge
Historical comparable batches: 9

BA prediction:
  fermenter volume 20.7-21.1 L
  OG 1.053-1.055
  BH efficiency 72.4-73.8 %

Current Brewfather profile predicts 75.0 %.
Suggested profile efficiency: 73 %.
```

## Cross-link to BrewZilla Equipment Learning

The two learning domains should eventually meet, but they must stay conceptually separate:

```text
BrewZilla Equipment Learning
  -> how the hardware heats, stabilizes and times physical phases

Brew Analytics / Equipment Calibration
  -> what volume, gravity, losses and efficiency the completed process delivers
```

Combined later:

```text
physical-process evidence
+ completed-batch yield evidence
= equipment-specific predictive brew model
```

## First implementation milestone

Do not begin with prediction or profile writes.

The highest-value first slice is:

```text
1. define immutable completed-batch record
2. ingest target + measured Brewfather/Brewday values
3. persist raw values with provenance
4. calculate a small verified metric set
5. show last-batch summary
6. prove two sequential brews aggregate correctly
```

Only after this works should BA start proposing equipment-profile changes.
