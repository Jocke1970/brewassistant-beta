# BrewZilla Gen4 35L Brewfather profile reference

Status: reference snapshot / source workbook v2  
Last synced: 2026-09-15

This directory contains a GitHub-friendly, diffable snapshot of the BrewZilla Gen4 35L Brewfather profile workbook used by BrewAssistant planning and Brew Analytics documentation.

The companion workbook is `BrewZilla_Gen4_35L_Brewfather_profiler_v2.xlsx`. Because the repository connector used for this documentation pass does not directly upload the local binary workbook, the workbook sheets are preserved here as CSV snapshots so changes can be reviewed and versioned in GitHub.

## Current batch-size / method policy

```text
5–9 L
  BIAB
  BIAB No Sparge

~15 L
  Normal / malt pipe + sparge
  BIAB
  No Sparge / malt pipe + full-volume mash
  BIAB No Sparge

17–23 L
  Normal / malt pipe + sparge
  No Sparge / malt pipe + full-volume mash
```

For the currently maintained nominal sizes (5, 6, 8, 9, 15, 18, 20, 21 and 23 L), this produces 20 maintained profile combinations.

## Files

- `grundvarden.csv` — global assumptions, method defaults and batch-size notes
- `profilmatris.csv` — the 20 maintained Brewfather equipment-profile combinations
- `oversikt.csv` — workbook overview
- `brewfather-falt.csv` — field guide for Brewfather settings
- `kalibrering.csv` — calibration notes / workflow
- `kallor.csv` — source/reference sheet

Read together with:

- `../../brew-analytics-batch-method-policy.md`
- `../../brew-analytics-roadmap.md`
- `../../brew-analytics-data-model.md`
- `../../brew-analytics-metrics.md`

## Authority boundary

These are starting/profile-planning values, not immutable equipment truth. Brew Analytics should preserve actual brew measurements and recommend later calibration changes from evidence. No profile value in this reference may silently become live BrewZilla control or silently rewrite a Brewfather profile.