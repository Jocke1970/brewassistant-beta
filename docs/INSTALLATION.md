# Installation

## 1. Requirements

BrewAssistant v4 assumes Home Assistant with YAML packages enabled.

Example `configuration.yaml`:

```yaml
homeassistant:
  packages: !include_dir_named packages
```

Suggested location:

```text
/config/packages/brewassistant_helpers.yaml
```

## 2. Required custom cards

Install these through HACS:

- Button Card
- Stack In Card
- Vertical Stack In Card
- Mushroom Cards
- Card Mod

Typical Lovelace resources are handled automatically by HACS. If installing manually, ensure the resources are loaded under:

```text
Settings → Dashboards → Resources
```

## 3. Add helper package

Create or update:

```text
/config/packages/brewassistant_helpers.yaml
```

Add the required helpers, template sensors, input booleans, input selects, input numbers and input buttons.

## 4. Reload or restart

After editing package YAML:

```text
Developer Tools → YAML → Check configuration
Developer Tools → YAML → Reload template entities
```

If helpers do not appear, restart Home Assistant.

## 5. Add dashboard cards

Add the Lovelace cards manually to your dashboard using YAML mode or a Manual Card.

Recommended order:

```text
Problem Center
FWK / Fermentation Process
Fermentation Chamber
Kegerator
Hot Side
```

## 6. Verify core entities

Check that these entities exist or are intentionally mapped:

```yaml
sensor.brewassistant_health_status
sensor.brewassistant_problem_count
binary_sensor.brewassistant_any_problem_active

sensor.brewassistant_kegerator_power_w
binary_sensor.kegerator_compressor_active

input_boolean.fwk_process_card_enabled
input_boolean.fwk_show_details

input_boolean.brewassistant_hot_side_enabled
input_boolean.brewassistant_hot_side_show_settings
```

## 7. Troubleshooting

If a template sensor is `unavailable`, check:

```text
Settings → System → Logs
```

Search for:

```text
TemplateSyntaxError
Invalid config for 'template'
brewassistant
```

Common causes:

- duplicate `template:` root blocks
- `sensor:` templates accidentally placed under `binary_sensor:`
- incorrect indentation
- entity names not matching your HA instance
