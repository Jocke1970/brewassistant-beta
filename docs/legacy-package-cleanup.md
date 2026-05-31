# Legacy package cleanup checklist

BrewAssistant is moving backend/runtime logic from Home Assistant package YAML into the Python custom integration under `custom_components/brewassistant/`.

This checklist is for deciding which old `packages/*.yaml` files can be deleted from a local Home Assistant install and, later, from the repository.

## Cleanup rule

```text
Python custom integration = backend, runtime, calculations, safety, orchestration
Dashboard YAML             = presentation and explicit operator actions
Legacy packages            = temporary compatibility only
```

Do not delete a package until all dashboard references, automations and scripts using its entities have been migrated or intentionally replaced.

## Likely delete candidates

These packages are likely to be removable once the Python entities and current dashboard cards have been verified.

| Package | Recommendation | Reason / replacement direction |
| --- | --- | --- |
| `packages/brewassistant_hot_side_module.yaml` | Delete candidate | Superseded by Python Brewday Runtime, Brewday Stage Engine, BrewZilla orchestration and current Brewday/BrewZilla cards. |
| `packages/brewassistant_biab_module.yaml` | Delete candidate / archive | Superseded for active BrewZilla beta flow by Python Manual Brewday + BrewZilla runtime. Keep only if old BIAB calibration helpers are still actively used. |
| `packages/brewassistant_manual_mode.yaml` | Delete candidate after verification | Python Manual Brewday runtime owns prepare/start/pause/next/mash/boil/whirlpool/cooling/finish/reset. |
| `packages/brewassistant_brewfather_adapter.yaml` | Delete candidate after dashboard migration | Python Brewfather RAW Brew Tracker resolver is now the active runtime source. |
| `packages/brewassistant_brewfather_multiple_batches_module.yaml` | Archive/delete candidate | Multi-batch YAML flow is not the active beta path. Revisit only if multi-batch support is reintroduced in Python. |
| `packages/brewassistant_health_module.yaml` | Delete candidate / reimplement later | Health snapshot should be Python-owned or dashboard-only; avoid old helper-only health logic. |
| `packages/brewassistant_notifications_module.yaml` | Keep until notification migration | Still useful until hop/CFC/brewday/fermentation notifications are Python or automation-backed with current entities. |
| `packages/cleaning/brewassistant_cleaning_module.yaml` | Keep if still used | Cleaning workflow has not been migrated to Python in the beta path. |

## Keep for now

These packages may still contain useful active logic until their Python replacements are explicitly verified.

| Package | Current guidance |
| --- | --- |
| `packages/brewassistant_fermentation_module.yaml` | Keep until fermentation runtime/control is fully Python-owned and current dashboards no longer depend on legacy helpers. |
| `packages/brewassistant_chamber_module.yaml` | Keep until chamber/fermentation climate entities are replaced or mapped to Python-backed equivalents. |
| `packages/brewassistant_kegerator_module.yaml` | Keep until serving/kegerator dashboards and climate-supervisor cards no longer use package-owned helpers. |
| `packages/brewassistant_notifications_module.yaml` | Keep until notifications are reworked around Python sensors/events. |
| `packages/cleaning/brewassistant_cleaning_module.yaml` | Keep if cleaning dashboards/scripts still exist locally. |

## Already removed

| Package | Replacement |
| --- | --- |
| `packages/brewassistant_counterflow_chiller.yaml` | Replaced by Python CFC backend: `switch.brewassistant_counterflow_chiller_enabled`, `number.brewassistant_counterflow_chiller_sanitize_minutes`, `number.brewassistant_counterflow_chiller_pump_utilization`, `button.brewassistant_counterflow_chiller_ready`. |

## Deletion verification checklist

Before deleting any package:

```text
[ ] Search dashboards for entities created by the package.
[ ] Search automations/scripts for package-owned helpers.
[ ] Confirm Python custom integration exposes equivalent entities.
[ ] Confirm current dashboard cards load with no missing entities.
[ ] Restart Home Assistant cleanly.
[ ] Check Settings → System → Repairs.
[ ] Check logs for template/entity errors.
[ ] Run a dry brewday/dashboard test.
[ ] Delete or archive the package.
[ ] Restart again and verify no orphan references remain.
```

## Suggested local deletion order

Start with the hot-side/BrewZilla beta replacements first, because that is where Python coverage is strongest.

```text
1. Remove/disable brewassistant_hot_side_module.yaml
2. Remove/disable brewassistant_brewfather_multiple_batches_module.yaml if unused
3. Remove/disable brewassistant_manual_mode.yaml after Manual Brewday Python verification
4. Remove/disable brewassistant_brewfather_adapter.yaml after Brewfather RAW resolver verification
5. Archive brewassistant_biab_module.yaml only after BIAB calibration is no longer used
6. Migrate notifications
7. Migrate fermentation/chamber/kegerator/cleaning later
```

For local testing, prefer moving a file to an `_disabled/` folder first rather than deleting it permanently.
