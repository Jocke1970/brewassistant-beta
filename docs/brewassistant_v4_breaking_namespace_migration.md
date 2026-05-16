# BrewAssistant v4 Breaking Namespace Migration

This branch is intended to perform the broad namespace migration from legacy `fwk_*` to `brew_*`.

## Goal

Move BrewAssistant away from the old Fresh Wort Kit specific `fwk_*` namespace and make `brew_*` the backend/source-of-truth namespace.

## Why this is breaking-ish

This migration intentionally does not preserve old Home Assistant entity state/history for `fwk_*` helpers.

Home Assistant may create new `brew_*` entities and old `fwk_*` entities may remain in the entity registry until manually cleaned up.

## Migration script

Run from repository root:

```bash
bash tools/migrate_fwk_to_brew_namespace.sh
```

The script will:

1. Remove transitional namespace alias files.
2. Replace `fwk_` with `brew_` in the main package files.
3. Print remaining `fwk_` references under `packages/`.
4. Show `git status`.

## Alias files removed by the migration

The alias files are transitional bridge files and should not remain after `brew_*` becomes source-of-truth:

- `packages/brewassistant_namespace_aliases.yaml`
- `packages/brewassistant_namespace_aliases_main_card_helpers.yaml`
- `packages/brewassistant_namespace_aliases_notifications.yaml`
- `packages/brewassistant_namespace_aliases_fermentation.yaml`
- `packages/brewassistant_namespace_aliases_chamber.yaml`

Keeping them after a global rename risks self-referential template loops.

## Target package files

The script migrates:

- `packages/brewassistant_notifications_module.yaml`
- `packages/brewassistant_chamber_module.yaml`
- `packages/brewassistant_fermentation_module.yaml`
- `packages/brewassistant_brewfather_adapter.yaml`

## Test plan

After running the script and committing the result:

1. Copy/update the branch in Home Assistant.
2. Run YAML validation / restart HA.
3. Check that package loading succeeds.
4. Check key entities:
   - `input_boolean.brew_batch_active`
   - `sensor.brew_process_status`
   - `binary_sensor.brew_process_ready_for_cold_crash`
   - `sensor.brew_live_sg` or final live SG entity after migration
   - `script.brew_start_batch` or final script entity after migration
5. Check fermentation dashboard cards.
6. If it burns, revert to previous working branch/main.

## Notes

This is intentionally not a surgical alias migration. It is a larger breaking cleanup step.

Old `fwk_*` entity history and helper states are considered expendable for this migration.
