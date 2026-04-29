# Installation Guide

## Path

Place package files here:

```text
/config/packages/brewassistant/
```

Make sure packages are enabled in `configuration.yaml`:

```yaml
homeassistant:
  packages: !include_dir_named packages
```

If using nested folders:

```yaml
homeassistant:
  packages: !include_dir_named packages/brewassistant
```

Use the structure that matches your current Home Assistant setup.

## Safe install order

Recommended install order:

```text
1. brewassistant_fermentation_module.yaml
2. brewassistant_chamber_module.yaml
3. brewassistant_kegerator_module.yaml
4. brewassistant_brewfather_adapter.yaml
5. brewassistant_hot_side_module.yaml
6. brewassistant_health_module.yaml
7. brewassistant_notifications_module.yaml
8. brewassistant_cleaning_module.yaml
```

Restart Home Assistant between modules when testing.

## Legacy files

Do not keep old package files active together with the v4 split. Duplicate entities may occur.

Legacy files replaced by v4 include:

```text
brewassistant_helpers_total.yaml
BREWASSISTANT WORKFLOW.yaml
BREWASSISTANT RUNTIME.yaml
BREWASSISTANT CHAMBER.yaml
BREWASSISTANT NOTIFICATIONS.yaml
BREWASSISTANT SMART AUTOMATION LAYER V2.yaml
BREWASSISTANT - SMART FERMENTATION CONTROL v1_0,yaml
BREWASSISTANT BULLETPROOF FERMENTATION CONTROL v1_1.yaml
brewassistant_kegerator_fan_control.yaml
BrewAssistant Hot Side Workflow v1_0.yaml
BrewAssistant Hot Side Workflow v1_1 Patch.yaml
BrewAssistant Brewfather Mapping Patch v1_0.yaml
BrewAssistant Brewfather Events Mapping Patch v1_0.yaml
rewassistant_health_backend_v2.yaml
```

## First checks after restart

Check Developer Tools → States for:

```text
input_boolean.brewassistant_fermentation_enabled
input_boolean.brewassistant_chamber_enabled
input_boolean.brewassistant_kegerator_enabled
input_boolean.brewassistant_hot_side_enabled
sensor.fwk_process_status
sensor.recipe_runtime_name
binary_sensor.kegerator_compressor_active
```

## Expected startup states

When nothing is active yet:

```text
Fermentation card disabled → Off / Standby
Fermentation enabled but no batch → Idle
Chamber off → Off / Chamber off
Kegerator → active if fridge entity exists
Brewfather adapter without active recipe → manual_fallback
Health → OK if installed modules are healthy
```
