# BrewAssistant BrewZilla Batch-Size / Method Policy

Status: design baseline / implementation pending  
Last synced: 2026-09-15

This document defines the intended default brewing-method envelope for BrewZilla Gen4 35 L profile selection and Brew Analytics aggregation.

It complements:

- `brew-analytics-roadmap.md`
- `brew-analytics-data-model.md`
- `brew-analytics-metrics.md`
- `brewzilla-equipment-learning.md`

## Default batch-size classes

For the currently maintained BrewZilla Gen4 35 L profile set:

```text
Small batch
  nominal profiles: 5 L, 6 L, 8 L, 9 L
  preferred methods:
    - BIAB
    - BIAB No Sparge

Medium batch
  nominal profile: ~15 L
  supported methods:
    - Normal / malt pipe + sparge
    - BIAB
    - No Sparge / malt pipe + full-volume mash
    - BIAB No Sparge

Large batch
  range: 17-23 L
  maintained nominal profiles: 18 L, 20 L, 21 L, 23 L
  preferred methods:
    - Normal / malt pipe + sparge
    - No Sparge / malt pipe + full-volume mash
```

This produces 20 actively maintained Brewfather-profile combinations from the current nominal batch sizes.

## Important interpretation

The size-class policy is a practical BrewZilla profile-selection rule, not a statement that an excluded combination is physically impossible.

BrewAssistant should distinguish between:

```text
maintained/recommended profile combination
experimental or explicitly operator-selected combination
invalid measurement
```

An experimental batch should still be recordable in Brew Analytics. It must not silently contaminate a maintained profile aggregate unless the operator deliberately maps it into that comparison group.

## Stable method identifiers

Use stable internal identifiers:

```text
normal
biab
no_sparge
biab_no_sparge
```

Operator-facing meaning:

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

## Analytics aggregation rule

Exact raw batch volume remains authoritative.

The default comparison envelope is:

```text
5-9 L:
  compare BIAB with BIAB evidence
  compare BIAB No Sparge with BIAB No Sparge evidence

~15 L:
  all four methods may build independent profiles

17-23 L:
  compare Normal/malt-pipe batches with Normal evidence
  compare No Sparge/malt-pipe batches with No Sparge evidence
```

Do not collapse BIAB and malt-pipe data into one efficiency model merely because target volume is similar.

## Confidence / fallback behavior

When an exact nominal profile has too few batches, analytics may use neighboring volume evidence only when:

```text
- equipment configuration matches
- brewing method matches
- the fallback relationship is shown explicitly
- confidence is reduced appropriately
```

Examples:

```text
18 L Normal may borrow weak prior context from 20/21 L Normal.
8 L BIAB No Sparge may borrow weak prior context from 5/6/9 L BIAB No Sparge.
15 L BIAB must not borrow 20/21 L Normal merely to increase sample count.
```

## Profile recommendation policy

Profile recommendations should target the maintained combination actually used.

Examples:

```text
5 L BIAB No Sparge
15 L BIAB
15 L Normal
21 L Normal
23 L No Sparge
```

BrewAssistant must not generate a routine profile recommendation for a size/method combination that is outside the maintained envelope unless the operator explicitly marks that combination as intentional/experimental.

## Current nominal profile matrix

```text
5 L   -> BIAB | BIAB No Sparge
6 L   -> BIAB | BIAB No Sparge
8 L   -> BIAB | BIAB No Sparge
9 L   -> BIAB | BIAB No Sparge
15 L  -> Normal | BIAB | No Sparge | BIAB No Sparge
18 L  -> Normal | No Sparge
20 L  -> Normal | No Sparge
21 L  -> Normal | No Sparge
23 L  -> Normal | No Sparge
```

## Safety / authority boundary

This policy guides profile selection and analytics grouping only.

It must not:

```text
- block manual brewing
- change BrewZilla live control
- rewrite a Brewfather profile silently
- reinterpret historical raw measurements
```

Any future profile change remains subject to explicit operator review / APPLY / DENY.
