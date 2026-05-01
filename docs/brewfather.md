# Brewfather Integration

BrewAssistant can use Brewfather data as a recipe/runtime source.

The goal is not to make the dashboard depend directly on many raw Brewfather entities. Instead, BrewAssistant should normalize Brewfather data into stable runtime sensors.

---

## Purpose

Brewfather data can provide:

- Active recipe name.
- Batch status.
- Fermentation start date.
- Primary fermentation target temperature.
- Cold crash target temperature.
- Fermentation schedule/steps.
- OG/FG values.
- Batch notes or history.

---

## Runtime layer

Recommended internal sensors:

```text
sensor.brew_recipe_name
sensor.brew_recipe_source
sensor.brew_recipe_status
sensor.brew_recipe_primary_temp
sensor.brew_recipe_cold_crash_temp
sensor.brew_recipe_fermentation_start
number.brew_recipe_target_gravity
```

Existing runtime names may include:

```text
sensor.recipe_runtime_name
sensor.recipe_runtime_status
sensor.recipe_runtime_source
sensor.recipe_runtime_primary_temp
sensor.recipe_runtime_cold_crash_temp
sensor.recipe_runtime_fermentation_start
```

These can remain as compatibility entities or be migrated to the `brew_recipe_*` namespace.

---

## Chamber integration

A common semi-automatic flow:

```text
Brewfather target temperature
→ runtime target sensor
→ chamber apply script
→ climate.fermentation_chamber
```

Recommended script name:

```text
script.brew_chamber_apply_recipe_target
```

Legacy/common older name:

```text
script.fwk_apply_brewfather_target
```

---

## Brewfather step temperatures

Fermentation steps may include:

```text
Primary fermentation temperature
Temperature ramp
Diacetyl rest
Cold crash temperature
```

BrewAssistant should normalize this into a small set of reliable runtime values rather than requiring every dashboard card to parse raw Brewfather JSON.

---

## BrewTracker / brew day

Brewfather includes brew-day style data through BrewTracker/API concepts.

Potential future use:

- Mash step progress.
- Boil timing.
- Hop addition reminders.
- Brew day notes.
- Hot-side status.

This should live in a separate hot-side module, not in the fermentation workflow.

Recommended future module:

```text
brewassistant_hot_side_workflow.yaml
```

---

## Recommended architecture

```text
Raw Brewfather data
        ↓
brewassistant_runtime.yaml
        ↓
sensor.brew_recipe_*
        ↓
brewassistant_workflow.yaml
brewassistant_chamber.yaml
        ↓
Dashboard cards
```

---

## Troubleshooting

If Brewfather data does not appear:

1. Confirm the raw Brewfather integration entities exist.
2. Confirm active batch status.
3. Confirm the runtime template can find the correct batch.
4. Check whether data is stored in attributes instead of state.
5. Check Home Assistant template logs.
6. Confirm dashboard cards use runtime entities, not outdated raw or legacy entities.

