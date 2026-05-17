# BrewAssistant Python Core v0.2

This is the first cautious step toward moving BrewAssistant business logic from YAML/Jinja packages into a Home Assistant custom integration.

The goal is **not** to replace the existing package modules yet. The goal is to expose clean, normalized entities that the existing dashboards can start using.

---

## Current scope

v0.2 is still read-only.

It reads existing Home Assistant entities and exposes normalized BrewAssistant entities:

- `sensor.brewassistant_liquid_temperature`
- `sensor.brewassistant_liquid_temperature_source`
- `sensor.brewassistant_chamber_temperature`
- `sensor.brewassistant_recipe_target_temperature`
- `sensor.brewassistant_temperature_delta`
- `sensor.brewassistant_temperature_target_mode`
- `sensor.brewassistant_temperature_status`
- `sensor.brewassistant_temperature_severity`
- `sensor.brewassistant_source_summary`
- `sensor.brewassistant_status_summary`
- `sensor.brewassistant_problem_level`
- `sensor.brewassistant_gravity`
- `binary_sensor.brewassistant_temperature_fallback_active`
- `binary_sensor.brewassistant_runtime_ready`

---

## Default source entities

The config flow defaults to the current BrewAssistant setup:

| Purpose | Default entity |
| --- | --- |
| Liquid temperature | `sensor.yellow_pill_temperature` |
| Chamber temperature fallback | `sensor.kyl_temperatur_4` |
| Recipe target temperature | `sensor.brew_recipe_active_target_temp` |
| Cold crash active helper | `input_boolean.brew_cold_crash_active` |
| Cold crash target temperature | `input_number.cold_crash_temp_target` |
| Gravity | `sensor.yellow_pill_gravity` |

These can be changed during setup.

---

## Temperature source logic

1. Use the configured liquid temperature entity when it has a valid numeric state.
2. Fall back to the configured chamber temperature entity when liquid temperature is unavailable.
3. Mark fallback active when chamber fallback is used.
4. Use cold crash target when cold crash is active and the cold crash target is valid.
5. Otherwise use the recipe/runtime target temperature.
6. Calculate delta as `liquid_temperature - effective_target_temperature`.

---

## v0.2 dashboard support logic

v0.2 adds dashboard-friendly status sensors so cards do not need to duplicate the same JavaScript/Jinja logic.

Examples:

- `sensor.brewassistant_temperature_target_mode` returns `Recipe` or `Cold crash`.
- `sensor.brewassistant_temperature_status` returns states such as `On target`, `Slight offset`, `Temp offset`, `Fallback active`, or `Unavailable`.
- `sensor.brewassistant_temperature_severity` returns `ok`, `info`, `warning`, or `problem`.
- `sensor.brewassistant_status_summary` returns a compact display line with target mode, liquid temp, target, delta, source, and SG when available.
- `sensor.brewassistant_problem_level` gives dashboards a simple top-level health signal.

These are display/support signals only. They do not control any hardware.

---

## Installation for testing

Copy the folder below into Home Assistant:

```text
custom_components/brewassistant/
```

Restart Home Assistant, then add the integration from:

```text
Settings -> Devices & services -> Add integration -> BrewAssistant
```

---

## Migration philosophy

Keep this split:

```text
Python custom integration = logic, normalization, state machine, calculations
YAML packages/dashboard = UI, layout, manual presentation tweaks
```

Future versions can move more logic in this order:

1. Fermentation temperature source, fallback and delta.
2. Dashboard status summaries and severity hints.
3. Smart fermentation recommendations and safety/block reasons.
4. Brewfather runtime normalization.
5. BIAB calculations and brew day state.
6. Buttons/services for actions such as applying target temperature.

---

## Current limitations

- No climate or switch control yet.
- No Brewfather API calls yet.
- No services/buttons yet.
- No options flow yet, so source entities are chosen during first setup.
- No automated test suite yet.

This is intentionally small so it can be tested safely beside the existing YAML modules.
