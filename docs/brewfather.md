# Brewfather Integration

BrewAssistant can use Brewfather as both a recipe source and an active Brewday runtime source.

The current Python Core branch treats Brewfather Brew Tracker as an external timeline source and normalizes it into stable BrewAssistant runtime entities. Dashboards should normally consume `sensor.brewassistant_brewday_*` entities instead of parsing raw Brewfather JSON directly.

---

## Purpose

Brewfather data can provide:

- Active recipe/batch name.
- Batch status.
- Fermentation schedule and target temperatures.
- Brewday stage/step timeline.
- Mash/boil/chill progress.
- Current and next Brew Tracker actions.
- OG/FG values.
- Batch notes or history.

---

## Runtime model

Recommended runtime flow:

```text
Brewfather integration entities
        ↓
sensor.brewfather_brew_tracker_raw
        ↓
BrewAssistant Brewday Runtime Core
        ↓
sensor.brewassistant_brewday_*
        ↓
Stage Engine / BrewZilla orchestration / Dashboard / Notifications
```

BrewAssistant should be the normalization layer. Dashboard cards should not depend on many raw Brewfather attributes unless they are explicitly debug cards.

---

## Brew Tracker RAW timeline

During BrewZilla testing, `sensor.brewfather_brew_tracker_step` was observed to lag behind Brewfather's web UI.

BrewAssistant therefore resolves the active Brew Tracker step from:

```text
sensor.brewfather_brew_tracker_raw.attributes.data.stages
stage.remainingSeconds
step.time anchors
```

The convenience step sensor is useful as a fallback/debug signal, but should not be considered the authoritative source for active Brewday control.

Runtime diagnostics expose:

```text
raw_step_index
resolved_step_index
raw_step_name
snapshot_age_seconds
```

These are useful in a RAW timeline/debug card.

---

## Human-friendly step labels

Brewfather may create multiple internal tracker steps with the same recipe step name. For example, a ramp and a hold can both be named:

```text
Step 6 - 55C final low-temp sync
```

BrewAssistant converts these into clearer runtime labels:

```text
Ramp to 55°C
Hold 55°C · 2 min
```

The original Brewfather text remains available through `raw_step_name` for diagnostics.

---

## Refresh policy

BrewAssistant includes a smart Brewfather refresh policy.

The intent is to keep real brewday API usage gentle while still being responsive around step changes.

```text
Normal real batch:
- Mash / boil / other active stage: about every 5 minutes
- Chilling: about every 2 minutes
- Idle/setup/cleanup: about every 10 minutes

Test batch / short-step recipe:
- about every 30 seconds

Step ending soon:
- about every 15 seconds

Awaiting snapshot:
- about every 15 seconds with a bounded burst limit

Minimum cooldown:
- 10 seconds
```

Manual refresh remains available as:

```text
brewassistant.force_brewfather_refresh
```

---

## Brewday / BrewZilla direct flow

The verified MVP path is documented separately:

```text
docs/brewday-brewzilla.md
```

Summary:

```text
Brewfather RAW Brew Tracker
        ↓
BrewAssistant RAW runtime resolver
        ↓
BrewAssistant brewday runtime sensors
        ↓
BrewZilla orchestration helper
        ↓
BrewZilla target / heater / pump actions
```

A low-temperature water test verified the 30 → 35 → 40 → 45 → 50 → 55°C target sequence without technical flow deviations.

---

## Fermentation runtime data

Fermentation values may still be normalized from Brewfather recipe/batch data, for example:

```text
sensor.recipe_runtime_name
sensor.recipe_runtime_status
sensor.recipe_runtime_primary_temp
sensor.recipe_runtime_cold_crash_temp
sensor.recipe_runtime_fermentation_start
```

Older/future namespace ideas include:

```text
sensor.brew_recipe_name
sensor.brew_recipe_source
sensor.brew_recipe_status
sensor.brew_recipe_primary_temp
sensor.brew_recipe_cold_crash_temp
sensor.brew_recipe_fermentation_start
number.brew_recipe_target_gravity
```

These may remain as compatibility entities until the Python runtime fully owns fermentation recipe normalization.

---

## Chamber integration

A common semi-automatic fermentation flow remains:

```text
Brewfather fermentation target temperature
→ runtime target sensor
→ chamber apply script / future Python supervisor
→ climate.fermentation_chamber
```

Older/common script name:

```text
script.fwk_apply_brewfather_target
```

Recommended future direction:

```text
Python fermentation runtime / supervisor
→ climate.fermentation_chamber
```

---

## Dashboard guidance

Normal dashboards should use:

```text
sensor.brewassistant_brewday_runtime_state
sensor.brewassistant_brewday_runtime_stage
sensor.brewassistant_brewday_runtime_step
sensor.brewassistant_brewday_runtime_next_step
sensor.brewassistant_brewday_target_temperature
sensor.brewassistant_brewday_live_time_remaining_minutes
sensor.brewassistant_brewday_live_progress
sensor.brewassistant_brewday_snapshot_age_minutes
```

Debug dashboards may use:

```text
sensor.brewfather_brew_tracker_raw
```

Recommended debug displays:

```text
RAW stage/step index
resolved step index
raw_step_name
remainingSeconds
progressPercent
snapshot age
full RAW checklist/timeline
```

---

## Troubleshooting

If Brewfather data does not appear or seems stale:

1. Confirm `sensor.brewfather_brew_tracker_raw` exists.
2. Confirm the Brew Tracker batch is enabled and active in Brewfather.
3. Confirm `sensor.brewfather_brew_tracker_status` is `running`, `paused` or `completed`.
4. Compare `raw_step_index` and `resolved_step_index` in BrewAssistant runtime attributes.
5. Check `snapshot_age_seconds` / `sensor.brewassistant_brewday_snapshot_age_minutes`.
6. Call `brewassistant.force_brewfather_refresh` for diagnostics.
7. Confirm dashboard cards use `sensor.brewassistant_brewday_*` entities, not outdated helper or raw entities unless they are debug cards.
