# BrewAssistant v4 Fermentation Module Migration Plan

_Last updated: 2026-05-16_

This document tracks the planned migration of `packages/brewassistant_fermentation_module.yaml` from legacy `fwk_*` internal references toward the BrewAssistant v4 alias layer.

The fermentation module is the largest remaining backend/source-of-truth module and should be migrated in small, reviewable segments.

---

## Current strategy

Do **not** rename entity definitions yet.

For now:

- keep `fwk_*` entity definitions as backend/source of truth
- keep `unique_id: fwk_*` values unchanged
- keep automation IDs unchanged unless there is a specific reason to change them
- migrate internal reads/conditions/templates to existing `brew_*` aliases where safe
- migrate script consumers to wrapper scripts where safe

This avoids unnecessary Home Assistant entity churn while allowing UI and dependent modules to move toward the v4 namespace.

---

## Existing alias layers required

The following alias packages should exist before migrating the fermentation module:

- `packages/brewassistant_namespace_aliases.yaml`
- `packages/brewassistant_namespace_aliases_main_card_helpers.yaml`
- `packages/brewassistant_namespace_aliases_notifications.yaml`
- `packages/brewassistant_namespace_aliases_chamber.yaml`
- `packages/brewassistant_namespace_aliases_fermentation.yaml`

---

## PR #15 target segment

Recommended first migration segment inside `brewassistant_fermentation_module.yaml`:

- `sensor.fwk_process_status`
- `sensor.fwk_next_step`
- `sensor.fwk_next_step_clean`
- `sensor.fwk_current_action_stage`
- `sensor.fwk_next_action_stage`
- `sensor.fwk_planned_summary`

This section is mostly process presentation/state composition, not the raw workflow helper definitions.

---

## Safe replacements for first segment

### Input booleans

| Legacy | Alias |
|---|---|
| `input_boolean.fwk_process_card_enabled` | `input_boolean.brew_process_card_enabled` |
| `input_boolean.fwk_batch_active` | `input_boolean.brew_batch_active` |
| `input_boolean.fwk_transferred_to_keg` | `input_boolean.brew_transferred_to_keg` |
| `input_boolean.fwk_cold_crash_active` | `input_boolean.brew_cold_crash_active` |
| `input_boolean.fwk_dry_hop_added` | `input_boolean.brew_dry_hop_added` |
| `input_boolean.fwk_spunding_installed` | `input_boolean.brew_spunding_installed` |

### Binary sensors

| Legacy | Alias |
|---|---|
| `binary_sensor.fwk_ready_for_transfer` | `binary_sensor.brew_process_ready_for_transfer` |
| `binary_sensor.fwk_ready_for_cold_crash` | `binary_sensor.brew_process_ready_for_cold_crash` |
| `binary_sensor.fwk_dry_hop_active` | `binary_sensor.brew_process_dry_hop_active` |
| `binary_sensor.fwk_dry_hop_preview` | `binary_sensor.brew_process_dry_hop_preview` |
| `binary_sensor.fwk_spunding_active` | `binary_sensor.brew_process_spunding_active` |
| `binary_sensor.fwk_spunding_preview` | `binary_sensor.brew_process_spunding_preview` |
| `binary_sensor.fwk_transfer_active` | `binary_sensor.brew_process_transfer_active` |
| `binary_sensor.fwk_transfer_preview` | `binary_sensor.brew_process_transfer_preview` |
| `binary_sensor.fwk_cold_crash_active_card` | `binary_sensor.brew_process_cold_crash_active_card` |
| `binary_sensor.fwk_cold_crash_preview` | `binary_sensor.brew_process_cold_crash_preview` |

---

## Do not replace with self-referential aliases

Avoid replacing the definition of a source sensor with its own alias.

For example, inside the definition of `sensor.fwk_process_status`, do **not** read:

```yaml
states('sensor.brew_process_status')
```

because `sensor.brew_process_status` is an alias of `sensor.fwk_process_status`.

The same applies to:

- `sensor.brew_process_next_step`
- `sensor.brew_process_planned_summary`
- `sensor.brew_process_current_action_stage`
- `sensor.brew_process_next_action_stage`

These are consumer-facing aliases and should not be used inside the source sensor that produces them.

---

## Suggested first patch

The first patch should only change references inside the target segment.

Examples:

```diff
- {% set batch_active = is_state('input_boolean.fwk_batch_active', 'on') %}
+ {% set batch_active = is_state('input_boolean.brew_batch_active', 'on') %}
```

```diff
- {% elif is_state('binary_sensor.fwk_ready_for_transfer', 'on') %}
+ {% elif is_state('binary_sensor.brew_process_ready_for_transfer', 'on') %}
```

```diff
- {% elif is_state('binary_sensor.fwk_dry_hop_preview', 'on') %}
+ {% elif is_state('binary_sensor.brew_process_dry_hop_preview', 'on') %}
```

---

## Next segments after process status

After the process/next-step section is verified in HA, migrate these separately:

1. Action binary sensors
   - ready for cold crash
   - ready for transfer
   - spunding preview/active
   - dry hop preview/active
   - cold crash preview/active card
   - transfer preview/active

2. Script internals
   - start batch
   - mark spunding installed
   - mark dry hop added
   - start cold crash
   - mark transferred to keg
   - reset batch

3. Daily SG snapshot automation

4. Brewfather auto-start / auto-reset automation

5. Optional final backend rename, much later

---

## Recommended local workflow

Because the file is large, apply this migration locally with grep and a YAML-aware editor.

Useful focused grep:

```bash
grep -n "fwk_" packages/brewassistant_fermentation_module.yaml
```

Focused first segment:

```bash
sed -n '600,740p' packages/brewassistant_fermentation_module.yaml
```

After editing:

```bash
grep -n "fwk_" packages/brewassistant_fermentation_module.yaml
```

Then restart Home Assistant or run YAML validation before merging.

---

## Safety rule

If in doubt, prefer leaving a legacy `fwk_*` reference in place over creating a circular alias dependency.

The alias layer is a bridge, not the final backend model.
