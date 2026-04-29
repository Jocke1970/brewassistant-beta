# BrewAssistant v4

BrewAssistant v4 is a modular Home Assistant package setup for brewing workflows.

The goal is simple:

- each module should be able to run on its own
- UI/dashboard YAML should stay separate from backend packages
- existing `fwk_*` entities are preserved for compatibility
- adapters may feed modules, but modules should not require adapters

## Current modules

```text
/config/packages/brewassistant/

brewassistant_fermentation_module.yaml
brewassistant_chamber_module.yaml
brewassistant_kegerator_module.yaml
brewassistant_hot_side_module.yaml
brewassistant_brewfather_adapter.yaml
brewassistant_health_module.yaml
brewassistant_notifications_module.yaml
brewassistant_cleaning_module.yaml
```

## Recommended dashboard layout

UI cards are not stored inside package modules.

Recommended structure:

```text
/config/lovelace/brewassistant/

brewassistant_main_dashboard.yaml
cards/fermentation_process_card.yaml
cards/chamber_card.yaml
cards/kegerator_card.yaml
cards/hot_side_card.yaml
cards/health_card.yaml
```

## Important design rule

`*_enabled` helpers are module switches.

Example:

```text
input_boolean.brewassistant_fermentation_enabled
input_boolean.brewassistant_chamber_enabled
input_boolean.brewassistant_kegerator_enabled
input_boolean.brewassistant_hot_side_enabled
```

Legacy UI toggles, such as `input_boolean.fwk_process_card_enabled`, may still control only the dashboard/card state.

