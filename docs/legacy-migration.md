# Legacy Migration

BrewAssistant v4 should gradually move away from the old `fwk_*` namespace.

The old namespace came from a Fresh Wort Kit focused workflow. BrewAssistant has grown into a more general brewing assistant, so v4 should use generic names.

---

## Migration goal

Move from:

```text
fwk_*
```

to clearer namespaces:

```text
brew_process_*
brew_batch_*
brew_recipe_*
brew_chamber_*
brew_manual_*
brew_notification_*
brew_hot_side_*
```

---

## Why migrate?

The `fwk_*` namespace is limiting because BrewAssistant now supports or plans to support:

- Fresh Wort Kits.
- Cider.
- Manual hydrometer batches.
- Brewfather fermentation schedules.
- RAPT Pill gravity/temperature.
- Fermentation chamber automation.
- Kegerator workflows.
- BrewZilla/RAPT hot-side workflows.

A generic namespace makes the project easier to share and maintain.

---

## Important warning

Do not update backend packages only.

Dashboard cards must also be migrated. Otherwise the backend may be clean while the UI still points to old `fwk_*` entities.

Search both:

```text
packages/*.yaml
dashboards/*.yaml
```

---

## Suggested migration order

1. Document current entities.
2. Add new v4 entities as aliases or replacements.
3. Update dashboard cards to use new names.
4. Test all cards and automations.
5. Remove legacy aliases only after confirming nothing uses them.

---

## Suggested mapping

| Legacy entity | New direction |
| --- | --- |
| `sensor.fwk_process_status` | `sensor.brew_process_status` |
| `sensor.fwk_next_step` | `sensor.brew_process_next_step` |
| `sensor.fwk_current_action_stage` | `sensor.brew_process_current_action_stage` |
| `sensor.fwk_next_action_stage` | `sensor.brew_process_next_action_stage` |
| `sensor.fwk_planned_summary` | `sensor.brew_process_planned_summary` |
| `input_boolean.fwk_batch_active` | `input_boolean.brew_batch_active` |
| `input_boolean.fwk_transferred_to_keg` | `input_boolean.brew_batch_packaged` |
| `input_boolean.fwk_cold_crash_active` | `input_boolean.brew_batch_cold_crash_active` |
| `binary_sensor.fwk_ready_for_cold_crash` | `binary_sensor.brew_process_ready_for_cold_crash` |
| `binary_sensor.fwk_ready_for_transfer` | `binary_sensor.brew_process_ready_for_transfer` |
| `script.fwk_start_batch` | `script.brew_batch_start` |
| `script.fwk_reset_batch` | `script.brew_batch_reset` |
| `script.fwk_apply_brewfather_target` | `script.brew_chamber_apply_recipe_target` |

---

## Compatibility strategy

During migration, it can be useful to keep old names as compatibility aliases.

Example concept:

```text
sensor.fwk_process_status
```

can temporarily mirror:

```text
sensor.brew_process_status
```

This allows dashboards to be migrated gradually.

---

## Search checklist

Search the repository for:

```text
fwk_
recipe_runtime_
manual_batch_
brewassistant_notifications_
brewassistant_chamber_
```

Then classify each hit as:

```text
Keep
Rename
Alias temporarily
Delete
```

---

## Dashboard migration checklist

For each dashboard card:

```text
[ ] Top card entity
[ ] Label JavaScript templates
[ ] Button tap actions
[ ] Conditional cards
[ ] Mushroom chips
[ ] ApexCharts series
[ ] Bar-card entities
[ ] Expander contents
[ ] Debug/raw data sections
```

---

## Final cleanup checklist

Before deleting legacy entities:

```text
[ ] No dashboard references old names
[ ] No automations reference old names
[ ] No scripts reference old names
[ ] No notification templates reference old names
[ ] No README/docs examples reference old names as current
[ ] Home Assistant restart is clean
[ ] Logs show no template errors
```

