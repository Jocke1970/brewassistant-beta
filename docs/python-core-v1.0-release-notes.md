# BrewAssistant Python Core v1.0 Release Notes

BrewAssistant Python Core v1.0 is the first stable read-only core milestone.

It does not control hardware.

No climate, switch, fan, heater, fridge, relay or compressor actions are performed by Python Core v1.0.

---

## Scope

v1.0 provides normalized read-only state for dashboards, diagnostics and future automation planning.

---

## Included layers

```text
[x] Base fermentation core
[x] Temperature source/fallback normalization
[x] Effective target temperature normalization
[x] Gravity normalization
[x] Process mirror
[x] Smart fermentation recommendations
[x] Pill stale diagnostics
[x] Options flow
[x] Source health diagnostics
[x] Debug card v2
[x] Next recommended action
[x] Brewfather/runtime normalization
[x] Core version sensor
```

---

## Main entities

### Core

```text
sensor.brewassistant_core_version
sensor.brewassistant_liquid_temperature
sensor.brewassistant_liquid_temperature_source
sensor.brewassistant_chamber_temperature
sensor.brewassistant_recipe_target_temperature
sensor.brewassistant_temperature_delta
sensor.brewassistant_gravity
sensor.brewassistant_status_summary
binary_sensor.brewassistant_runtime_ready
binary_sensor.brewassistant_temperature_fallback_active
```

### Process

```text
sensor.brewassistant_process_status
sensor.brewassistant_process_next_step
sensor.brewassistant_process_current_action_stage
sensor.brewassistant_process_next_action_stage
sensor.brewassistant_process_summary
```

### Smart recommendations

```text
sensor.brewassistant_smart_recommendation_summary
sensor.brewassistant_smart_heat_recommendation
sensor.brewassistant_smart_cooling_recommendation
sensor.brewassistant_smart_fan_recommendation
sensor.brewassistant_smart_heat_block_reason_core
sensor.brewassistant_smart_suggested_heat_pulse_minutes
sensor.brewassistant_smart_recommendation_mode
binary_sensor.brewassistant_smart_heat_needed_core
binary_sensor.brewassistant_smart_heat_permitted_core
binary_sensor.brewassistant_smart_cooling_recommended_core
binary_sensor.brewassistant_smart_fan_recommended_core
binary_sensor.brewassistant_smart_rising_too_fast_core
```

### Pill diagnostics

```text
sensor.brewassistant_smart_pill_status_core
sensor.brewassistant_smart_pill_temp_age_minutes_core
binary_sensor.brewassistant_smart_pill_stale_core
```

### Source health

```text
sensor.brewassistant_source_health_summary
sensor.brewassistant_source_health_level
sensor.brewassistant_configured_liquid_temp_entity
sensor.brewassistant_configured_chamber_temp_entity
sensor.brewassistant_configured_recipe_target_entity
sensor.brewassistant_configured_cold_crash_active_entity
sensor.brewassistant_configured_cold_crash_target_entity
sensor.brewassistant_configured_gravity_entity
binary_sensor.brewassistant_source_liquid_temp_available
binary_sensor.brewassistant_source_chamber_temp_available
binary_sensor.brewassistant_source_recipe_target_available
binary_sensor.brewassistant_source_cold_crash_active_available
binary_sensor.brewassistant_source_cold_crash_target_available
binary_sensor.brewassistant_source_gravity_available
```

### Next action

```text
sensor.brewassistant_next_recommended_action
```

### Runtime / Brewfather

```text
sensor.brewassistant_runtime_recipe_name
sensor.brewassistant_runtime_status
sensor.brewassistant_runtime_primary_target_temperature
sensor.brewassistant_runtime_cold_crash_target_temperature
sensor.brewassistant_runtime_target_fg
sensor.brewassistant_runtime_source_status
binary_sensor.brewassistant_runtime_brewfather_available
```

---

## Dashboard cards

Existing debug card:

```text
dashboards/cards/brewassistant_core_debug_card.yaml
```

New stable v1 card:

```text
dashboards/cards/brewassistant_core_debug_card_v1.yaml
```

---

## Validation history

```text
v0.5 Options Flow / Pill stale: validated
v0.6 Source Health + Entity Diagnostics: validated
v0.7 Debug Card v2: accepted for continued use
v0.8 Next Recommended Action: validated
v0.9 Brewfather Runtime Normalization: validated
v1.0 Read-only Core Stable: pending final HA verification
```

---

## Safety boundary

Python Core v1.0 is diagnostic/read-only only.

Future control work must be implemented separately and guarded by explicit enable switches, mode selection, manual override and emergency off paths.
