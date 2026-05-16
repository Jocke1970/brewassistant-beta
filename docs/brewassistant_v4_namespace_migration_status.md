# BrewAssistant v4 Namespace Migration Status

_Last updated: 2026-05-16_

This document tracks the ongoing migration away from the older `fwk_*` namespace toward the BrewAssistant v4 naming pattern.

The current strategy is intentionally conservative:

1. Keep existing `fwk_*` backend logic as source of truth for now.
2. Add transitional `brew_*` aliases/wrappers.
3. Move dashboard YAML to aliases first.
4. Rename backend helpers/templates/scripts later, after UI behavior is verified.

---

## Current status

### Done

- Added transitional base alias package:
  - `packages/brewassistant_namespace_aliases.yaml`
- Added main-card helper alias package:
  - `packages/brewassistant_namespace_aliases_main_card_helpers.yaml`
- Migrated the active fermentation process dashboard to alias entities:
  - `dashboards/brewassistant_fermentation_process.yaml`
- Migrated fermentation control / status dashboard references where needed:
  - `dashboards/brewassistant_fermentation_control.yaml`
- Migrated smart fermentation dashboard references where needed:
  - `dashboards/brewassistant_smart_fermentation.yaml`
- Removed old dashboard files from active `dashboards/` to avoid future confusion:
  - `dashboards/brewassistant_main_card.yaml`
  - `dashboards/brewassistant_fermentation_chamber_card.yaml`

### Active fermentation dashboard files

These are the current active fermentation/dashboard files as of this migration pass:

- `dashboards/brewassistant_fermentation_process.yaml`
- `dashboards/brewassistant_fermentation_control.yaml`
- `dashboards/brewassistant_smart_fermentation.yaml`

### Legacy dashboard files removed from active folder

The following old files were removed from active `dashboards/`. They remain recoverable from Git history if needed.

- `dashboards/brewassistant_main_card.yaml`
  - Replaced by: `dashboards/brewassistant_fermentation_process.yaml`
- `dashboards/brewassistant_fermentation_chamber_card.yaml`
  - Replaced by:
    - `dashboards/brewassistant_fermentation_control.yaml`
    - `dashboards/brewassistant_smart_fermentation.yaml`

---

## Alias packages

### `packages/brewassistant_namespace_aliases.yaml`

Purpose: base compatibility layer for the main process/fermentation/chamber namespace.

Provides aliases/wrappers such as:

- `input_boolean.brew_process_card_enabled`
- `sensor.brew_process_status`
- `sensor.brew_process_next_step`
- `sensor.brew_process_planned_summary`
- `sensor.brew_process_current_action_stage`
- `sensor.brew_process_next_action_stage`
- `sensor.brew_batch_age_days`
- `sensor.brew_batch_age_hours`
- `sensor.brew_fermentation_live_sg`
- `sensor.brew_fermentation_live_temp`
- `sensor.brew_fermentation_attenuation`
- `sensor.brew_fermentation_gravity_points_left`
- `sensor.brew_fermentation_sg_last_updated`
- `sensor.brew_recipe_active_target_temp`
- `sensor.brew_chamber_target_midpoint`
- `sensor.brew_chamber_target_span`
- `sensor.brew_chamber_recipe_delta`
- `sensor.brew_chamber_live_vs_recipe_delta`
- `sensor.brew_chamber_action`
- `sensor.brew_chamber_summary`
- `sensor.brew_chamber_suggested_range`
- `script.brew_batch_start`
- `script.brew_process_mark_spunding_installed`
- `script.brew_process_mark_dry_hop_added`
- `script.brew_cold_crash_start`
- `script.brew_process_mark_transferred_to_keg`
- `script.brew_chamber_apply_brewfather_target`

### `packages/brewassistant_namespace_aliases_main_card_helpers.yaml`

Purpose: helper aliases needed by remaining process/main-card style UI references.

Provides aliases/sync for:

- `input_boolean.brew_batch_active`
- `input_boolean.brew_transferred_to_keg`
- `input_boolean.brew_show_details`
- `sensor.brew_fermentation_pace`

---

## Dashboard migration status

### Migrated / current

| File | Status | Notes |
|---|---|---|
| `dashboards/brewassistant_fermentation_process.yaml` | Migrated | Uses `brew_process_*`, `brew_fermentation_*`, `brew_batch_*`, and wrapper scripts. |
| `dashboards/brewassistant_fermentation_control.yaml` | Migrated | Remaining process references moved to alias layer. |
| `dashboards/brewassistant_smart_fermentation.yaml` | Migrated | Remaining `fwk_*` traces were replaced manually with alias names. |
| `dashboards/brewassistant_biab_card.yaml` | Not part of `fwk_*` migration | Uses `brewassistant_biab_*` naming. |

### Removed / legacy

| File | Status | Replacement |
|---|---|---|
| `dashboards/brewassistant_main_card.yaml` | Removed from active folder | `dashboards/brewassistant_fermentation_process.yaml` |
| `dashboards/brewassistant_fermentation_chamber_card.yaml` | Removed from active folder | `dashboards/brewassistant_fermentation_control.yaml` + `dashboards/brewassistant_smart_fermentation.yaml` |

---

## Backend status

Backend/package entities are **not fully renamed yet**.

For now, old `fwk_*` entities still act as source of truth. The `brew_*` layer mirrors or wraps those entities for the UI.

This is expected and intentional.

### Do not remove yet

Do not remove `fwk_*` helpers/templates/scripts until:

1. All active dashboards are confirmed working with aliases.
2. Home Assistant has been restarted and verified.
3. Automations/scripts using `fwk_*` have been inventoried.
4. Backend rename PRs are done module-by-module.
5. Alias packages can be removed safely at the very end.

---

## Known caveats

### GitHub code search

GitHub code search has returned inconsistent results during this migration. It reported no `fwk_*` matches even when direct file inspection showed old references in legacy dashboard files.

For that reason, use direct file inspection or local grep before making backend rename decisions.

Recommended local checks:

```bash
grep -R "fwk_" -n dashboards packages docs .github 2>/dev/null
```

For dashboards only:

```bash
grep -R "fwk_" -n dashboards 2>/dev/null
```

For packages/backend only:

```bash
grep -R "fwk_" -n packages 2>/dev/null
```

---

## Recommended next steps

### 1. Verify active dashboards in Home Assistant

Confirm the current active cards still render correctly:

- `brewassistant_fermentation_process.yaml`
- `brewassistant_fermentation_control.yaml`
- `brewassistant_smart_fermentation.yaml`
- `brewassistant_biab_card.yaml`

### 2. Run local grep

Run:

```bash
grep -R "fwk_" -n dashboards packages docs .github 2>/dev/null
```

Then classify results into:

- Active dashboard references
- Backend/template/script references
- Documentation references
- Legacy/history references

### 3. Backend inventory PR

Create a follow-up backend inventory document or issue that lists all remaining backend `fwk_*` entities by file.

### 4. Backend migration later

Do backend migration module-by-module, not globally.

Recommended order:

1. Process/workflow sensors
2. Batch helpers
3. Fermentation metrics
4. Chamber alignment sensors
5. Script/service wrappers
6. Remove alias packages only after full verification

---

## Final migration goal

Final desired state:

- Active dashboards use only `brew_*`, `brewassistant_*`, and domain-specific module names.
- Backend helpers/templates/scripts are renamed away from `fwk_*`.
- Alias packages are removed after all consumers have moved.
- Documentation reflects BrewAssistant v4 naming consistently.

Until then, the alias layer is the safety net.
