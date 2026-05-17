# BrewAssistant Python Core v0.5 Test Plan

This checklist is intended for after updating `/config/custom_components/brewassistant/` from the PR branch and restarting Home Assistant.

v0.5 scope:

- Options flow for changing configured source entities after setup.
- Automatic integration reload when options are saved.
- Pill stale/readiness signals from the smart recommendation layer.
- Verification that v0.4 smart recommendation entities still work after the v0.5 update.

---

## 0. Before updating

Current expected stable entities from v0.3/v0.4:

```text
sensor.brewassistant_liquid_temperature
sensor.brewassistant_liquid_temperature_source
sensor.brewassistant_recipe_target_temperature
sensor.brewassistant_temperature_delta
sensor.brewassistant_status_summary
sensor.brewassistant_process_status
sensor.brewassistant_process_next_step
sensor.brewassistant_smart_heat_recommendation
sensor.brewassistant_smart_cooling_recommendation
sensor.brewassistant_smart_fan_recommendation
sensor.brewassistant_smart_heat_block_reason_core
sensor.brewassistant_smart_suggested_heat_pulse_minutes
sensor.brewassistant_smart_recommendation_mode
binary_sensor.brewassistant_smart_heat_permitted_core
binary_sensor.brewassistant_smart_cooling_recommended_core
binary_sensor.brewassistant_smart_fan_recommended_core
```

Known manual entity registry cleanup from v0.4:

```text
sensor.brewassistant_2 -> sensor.brewassistant_smart_heat_recommendation
sensor.brewassistant_3 -> sensor.brewassistant_smart_cooling_recommendation
sensor.brewassistant_4 -> sensor.brewassistant_smart_fan_recommendation
sensor.brewassistant_5 -> sensor.brewassistant_smart_heat_block_reason_core
sensor.brewassistant_6 -> sensor.brewassistant_smart_suggested_heat_pulse_minutes
sensor.brewassistant_7 -> sensor.brewassistant_smart_recommendation_mode
binary_sensor.brewassistant_2 -> binary_sensor.brewassistant_smart_heat_permitted_core
binary_sensor.brewassistant_3 -> binary_sensor.brewassistant_smart_cooling_recommended_core
binary_sensor.brewassistant_4 -> binary_sensor.brewassistant_smart_fan_recommended_core
```

---

## 1. Update and restart

1. Replace the whole folder:

```text
/config/custom_components/brewassistant/
```

2. Restart Home Assistant fully.

3. Check the integration version in `manifest.json` if needed:

```text
0.5.0
```

---

## 2. Base core sanity check

Run in Developer Tools -> Template:

```jinja
# BrewAssistant v0.5 base sanity check

Liquid:
{{ states('sensor.brewassistant_liquid_temperature') }}

Source:
{{ states('sensor.brewassistant_liquid_temperature_source') }}

Target:
{{ states('sensor.brewassistant_recipe_target_temperature') }}

Delta:
{{ states('sensor.brewassistant_temperature_delta') }}

Gravity:
{{ states('sensor.brewassistant_gravity') }}

Status:
{{ states('sensor.brewassistant_status_summary') }}
```

Expected in current cold crash scenario:

```text
Liquid: numeric value
Source: RAPT Pill
Target: 2.0
Delta: positive while liquid is above cold crash target
Gravity: 1.004-ish
Status: Cold crash ... RAPT Pill ... SG ...
```

---

## 3. Process mirror check

```jinja
# BrewAssistant v0.5 process mirror check

Process:
{{ states('sensor.brewassistant_process_status') }}

Next:
{{ states('sensor.brewassistant_process_next_step') }}

Current action:
{{ states('sensor.brewassistant_process_current_action_stage') }}

Next action:
{{ states('sensor.brewassistant_process_next_action_stage') }}

Summary:
{{ states('sensor.brewassistant_process_summary') }}

Reason:
{{ state_attr('sensor.brewassistant_process_status', 'process_reason') }}

YAML process:
{{ state_attr('sensor.brewassistant_process_status', 'yaml_process_status') }}
```

Expected while cold crash helper/target is active:

```text
Process: Cold crash
Next: Maintain cold crash and positive pressure
Current action: cold_crash
Next action: transfer
```

---

## 4. Smart recommendation check

```jinja
# BrewAssistant v0.5 smart recommendation check

Heat:
{{ states('sensor.brewassistant_smart_heat_recommendation') }}

Cooling:
{{ states('sensor.brewassistant_smart_cooling_recommendation') }}

Fan:
{{ states('sensor.brewassistant_smart_fan_recommendation') }}

Block reason:
{{ states('sensor.brewassistant_smart_heat_block_reason_core') }}

Suggested pulse:
{{ states('sensor.brewassistant_smart_suggested_heat_pulse_minutes') }} min

Mode:
{{ states('sensor.brewassistant_smart_recommendation_mode') }}

Heat permitted:
{{ states('binary_sensor.brewassistant_smart_heat_permitted_core') }}

Cooling recommended:
{{ states('binary_sensor.brewassistant_smart_cooling_recommended_core') }}

Fan recommended:
{{ states('binary_sensor.brewassistant_smart_fan_recommended_core') }}
```

Expected while liquid is above cold crash target and smart fermentation is disabled:

```text
Heat: No heat needed
Cooling: Cooling would help
Fan: Fan assist recommended for cooling
Block reason: Smart fermentation disabled
Heat permitted: off
Cooling recommended: on
Fan recommended: on
```

---

## 5. Pill stale check

```jinja
# BrewAssistant v0.5 pill stale check

Pill status:
{{ states('sensor.brewassistant_smart_pill_status_core') }}

Pill age:
{{ states('sensor.brewassistant_smart_pill_temp_age_minutes_core') }} min

Pill stale:
{{ states('binary_sensor.brewassistant_smart_pill_stale_core') }}

Summary:
{{ states('sensor.brewassistant_smart_recommendation_summary') }}
```

Expected when RAPT Pill is updating normally:

```text
Pill status: Pill fresh · <age> min
Pill stale: off
```

Expected when RAPT/Pill temp has not updated for more than 120 minutes:

```text
Pill status: Pill stale · <age> min
Pill stale: on
```

---

## 6. Options flow check

1. Go to:

```text
Settings -> Devices & services -> BrewAssistant -> Configure
```

2. Confirm that the options form shows:

```text
Liquid temperature source
Chamber temperature fallback
Recipe/runtime target temperature
Cold crash active helper
Cold crash target temperature helper
Gravity source
```

3. Save without changing anything.

4. Confirm that base core still works after the integration reloads.

Use the base sanity check from section 2.

---

## 7. Safe options-flow test

To verify that options actually apply:

1. Change only `Gravity source` to the same current entity if already correct:

```text
sensor.yellow_pill_gravity
```

2. Save.

3. Confirm:

```jinja
{{ states('sensor.brewassistant_gravity') }}
```

Still returns current SG.

Do not test with fake/nonexistent entities unless intentionally validating fallback behavior.

---

## 8. If entities get numbered again

If new entities appear as `sensor.brewassistant_2`, `sensor.brewassistant_3`, etc., it is an entity registry naming issue.

Use names and states to map them back. Example from v0.4:

```text
Smart heat recommendation -> sensor.brewassistant_smart_heat_recommendation
Smart cooling recommendation -> sensor.brewassistant_smart_cooling_recommendation
Smart fan recommendation -> sensor.brewassistant_smart_fan_recommendation
Smart heat block reason -> sensor.brewassistant_smart_heat_block_reason_core
Smart suggested heat pulse -> sensor.brewassistant_smart_suggested_heat_pulse_minutes
Smart recommendation mode -> sensor.brewassistant_smart_recommendation_mode
```

---

## 9. If options flow is missing

Check these files are updated in Home Assistant:

```text
/config/custom_components/brewassistant/config_flow.py
/config/custom_components/brewassistant/__init__.py
/config/custom_components/brewassistant/manifest.json
/config/custom_components/brewassistant/translations/sv.json
/config/custom_components/brewassistant/translations/en.json
```

Then restart Home Assistant.

---

## 10. If smart pill entities are missing

Check these files are updated in Home Assistant:

```text
/config/custom_components/brewassistant/smart_recommendations.py
/config/custom_components/brewassistant/sensor.py
/config/custom_components/brewassistant/binary_sensor.py
```

Then restart Home Assistant.

---

## 11. Rollback plan

If v0.5 causes trouble:

1. Restore the previous working `custom_components/brewassistant/` folder from before v0.5.
2. Restart Home Assistant.
3. The YAML modules should continue working because Python Core is still read-only.

No hardware control has been added in v0.5.
