# BrewAssistant Python Core v0.4

This is the first cautious step toward moving BrewAssistant business logic from YAML/Jinja packages into a Home Assistant custom integration.

The goal is **not** to replace the existing package modules yet. The goal is to expose clean, normalized entities that the existing dashboards can start using.

---

## Current scope

v0.4 is still read-only.

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
- `sensor.brewassistant_process_status`
- `sensor.brewassistant_process_next_step`
- `sensor.brewassistant_process_current_action_stage`
- `sensor.brewassistant_process_next_action_stage`
- `sensor.brewassistant_process_summary`
- `sensor.brewassistant_gravity`
- `binary_sensor.brewassistant_temperature_fallback_active`
- `binary_sensor.brewassistant_runtime_ready`

v0.4 staging also adds the helper module:

- `custom_components/brewassistant/smart_recommendations.py`

This module builds read-only smart fermentation recommendation snapshots. The helper module is committed, but the coordinator/entity wiring is intentionally staged separately so it can be reviewed carefully before Home Assistant loads new entities from it.

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

v0.2 added dashboard-friendly status sensors so cards do not need to duplicate the same JavaScript/Jinja logic.

Examples:

- `sensor.brewassistant_temperature_target_mode` returns `Recipe` or `Cold crash`.
- `sensor.brewassistant_temperature_status` returns states such as `On target`, `Slight offset`, `Temp offset`, `Fallback active`, or `Unavailable`.
- `sensor.brewassistant_temperature_severity` returns `ok`, `info`, `warning`, or `problem`.
- `sensor.brewassistant_status_summary` returns a compact display line with target mode, liquid temp, target, delta, source, and SG when available.
- `sensor.brewassistant_problem_level` gives dashboards a simple top-level health signal.

---

## v0.3 process mirror logic

v0.3 adds read-only process mirror sensors.

Examples:

- `sensor.brewassistant_process_status`
- `sensor.brewassistant_process_next_step`
- `sensor.brewassistant_process_current_action_stage`
- `sensor.brewassistant_process_next_action_stage`
- `sensor.brewassistant_process_summary`

The process mirror currently prioritizes obvious high-confidence states such as:

- Cold crash helper active or cold crash target mode.
- YAML process state reporting ready for transfer, ready for cold crash, dry hop, spunding or finished.
- Brewfather/runtime status reporting fermenting.

---

## v0.4 smart recommendation staging

v0.4 starts moving smart fermentation decision support into Python.

The first staged module can evaluate:

- Smart fermentation enabled/disabled.
- Selected smart fermentation mode.
- Current liquid temperature, target and delta.
- Whether the batch appears below or above target.
- Whether heating would be useful.
- Whether cooling/fan assist would be useful.
- Whether a rising trend, cooldown, fallback source, manual override or warm chamber should block a heat suggestion.
- Suggested heat pulse length as a recommendation only.

The planned entity layer for this module is:

- `sensor.brewassistant_smart_recommendation_summary`
- `sensor.brewassistant_smart_heat_recommendation`
- `sensor.brewassistant_smart_cooling_recommendation`
- `sensor.brewassistant_smart_fan_recommendation`
- `sensor.brewassistant_smart_heat_block_reason_core`
- `sensor.brewassistant_smart_suggested_heat_pulse_minutes`
- `sensor.brewassistant_smart_recommendation_mode`
- `binary_sensor.brewassistant_smart_heat_needed_core`
- `binary_sensor.brewassistant_smart_heat_permitted_core`
- `binary_sensor.brewassistant_smart_cooling_recommended_core`
- `binary_sensor.brewassistant_smart_fan_recommended_core`
- `binary_sensor.brewassistant_smart_rising_too_fast_core`

These will remain read-only recommendation/support entities.

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
3. Process state mirror.
4. Smart fermentation recommendations and safety/block reasons.
5. Brewfather runtime normalization.
6. BIAB calculations and brew day state.
7. Buttons/services for actions such as applying target temperature.

---

## Current limitations

- No climate or switch control yet.
- No Brewfather API calls yet.
- No services/buttons yet.
- No options flow yet, so source entities are chosen during first setup.
- No automated test suite yet.

This is intentionally small so it can be tested safely beside the existing YAML modules.
