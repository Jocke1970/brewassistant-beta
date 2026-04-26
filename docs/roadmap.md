# BrewAssistant – Roadmap

## Current Phase: Functional v1

Completed:

- Project structure
- Core helpers
- Runtime layer
- Workflow engine
- Notifications v1
- Brewfather-aware runtime
- Chamber intelligence
- Semiauto chamber target application
- Premium fermentation dashboard
- Premium chamber card
- Premium kegerator card

## v1.1 – Stabilization

Goals:

- clean up entity registry suffixes
- verify all runtime entities after Brewfather reconnect
- verify chamber semiauto target application
- validate notifications
- confirm kegerator target/current/delta behavior

Tasks:

- verify `sensor.recipe_runtime_primary_temp`
- verify `sensor.recipe_runtime_cold_crash_temp`
- verify `sensor.fwk_recipe_active_target_temp`
- verify `sensor.fwk_chamber_alignment_status`
- verify `script.fwk_apply_brewfather_target`
- verify kegerator climate attributes

## v1.2 – UI Polish

Goals:

- unify card style
- dark mode consistency
- better mobile layout
- less noisy detail sections

Tasks:

- improve main BrewAssistant card
- refine chamber card
- refine kegerator card
- possibly split desktop/mobile views

## v1.3 – Notifications Tuning

Goals:

- reduce notification spam
- improve action timing
- add more useful chamber and workflow alerts

Potential additions:

- notify when chamber target differs from recipe for more than X minutes
- notify when live temp drifts from recipe
- notify when Brewfather target changes
- notify when cold crash target is ready to apply

## v2.0 – Smart Automation Layer

Initial version already created.

Next improvements:

- actionable notifications
- confirmation workflows
- cold crash semiauto flow
- apply suggested chamber target from notification
- stricter safety rules
- optional full auto mode only after validation

## v2.1 – Fermentation Intelligence

Potential features:

- SG trend
- SG drop rate
- estimated days to FG
- stalled fermentation detection
- near-terminal prediction
- dry hop timing refinement

## v2.2 – Kegerator Intelligence

Potential features:

- compressor runtime tracking
- fan cycle recommendations
- temp stability scoring
- serving/storage/cold-crash mode dashboards
- keg aging / carbonation tracking

## v3.0 – Repository Release

Goals:

- clean GitHub-ready repo
- examples
- screenshots
- install guide
- package documentation
- troubleshooting guide
