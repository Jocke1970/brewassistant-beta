# BrewAssistant v0.2.0-beta.6 release notes

## Summary

v0.2.0-beta.6 is the current safety and operator-attention beta baseline.

This release focuses on safer supervised BrewZilla control, clearer operator confirmation flows, Brewday Advice notifications, and more conservative advice when batch context is missing.

## Highlights

- ABORT lockout prevents normal BrewZilla orchestration from immediately re-applying a previous runtime state.
- ABORT safe-state enforcement keeps the BrewZilla command surface in a stopped/safe state during lockout.
- Brewday Advice creates a persistent notification when a new pending recommendation appears.
- Brewday Advice notification is dismissed after APPLY, DENY or when the pending recommendation clears.
- Advice APPLY now stores BA-owned desired heat/pump utilization state.
- BrewZilla orchestration can reassert BA-owned utilization values if RAPT Cloud Link or BrewZilla reports a reverted value during active BA control.
- Brewfather Brewday Runtime is gated strictly on Brew Tracker status `active`.
- Strike/mash-in Brewday Advice now requires batch context instead of guessing smart heat-utilization corrections.
- Brewfather Brew Tracker raw data can provide batch context such as grain amount, mash water, sparge water and pre-boil volume.
- Manual batch-context helper entity names are supported if created locally.
- Event Log secondary sensors keep lightweight attributes instead of duplicating the full event list.

## Operator model

BrewAssistant remains a supervised beta integration.

The operator should stay present during BrewZilla, water-run and brewday tests, verify physical hardware behavior, and treat BrewAssistant recommendations as advisory unless explicitly confirmed.

## YAML policy

Python backend:
logic, safety guards, orchestration, recommendations, notifications and batch-context interpretation

Dashboard YAML:
cards/dashboards, visual presentation and explicit operator actions

Automation YAML:
not part of the mainline repo pattern

## Brewday Advice batch context

Brewday Advice can now expose and use batch-context fields:

- `grain_amount_kg`
- `mash_water_l`
- `sparge_water_l`
- `pre_boil_volume_l`
- `grain_temperature_c`
- `batch_context_source`
- `batch_context_available`
- `needs_batch_context`

When Brewfather Brew Tracker raw data is available, BrewAssistant can parse grain and water context from tracker stage/step descriptions.

For Manual Brew, matching helper entities can be created locally later and used as manual overrides.

## Next validation targets

- Confirm Brewday Advice notification behavior during a real pending recommendation.
- Validate BA-owned heat/pump utilization APPLY and reassert behavior during supervised testing.
- Validate Brewfather-derived batch context during active Brew Tracker runs.
- Continue supervised BrewZilla Direct Control testing from the ABORT-safe baseline.
- Validate CFC/chilling flow with real temperature and pump data.
- Run first full serious all-grain batch from start to transfer.
