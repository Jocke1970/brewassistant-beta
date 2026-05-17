# BrewAssistant Python Core v0.9 Test Plan

v0.9 adds read-only Brewfather/runtime normalization.

Goal:

```text
Expose normalized runtime recipe/status/targets/FG from configurable Home Assistant entities.
```

---

## 1. Update and restart

1. Replace the whole folder:

```text
/config/custom_components/brewassistant/
```

2. Restart Home Assistant fully.

3. Confirm version if needed:

```text
0.9.0
```

---

## 2. Base sanity check

```jinja
# BrewAssistant v0.9 base sanity check

Core summary:
{{ states('sensor.brewassistant_status_summary') }}

Source health:
{{ states('sensor.brewassistant_source_health_summary') }}

Next action:
{{ states('sensor.brewassistant_next_recommended_action') }}

Runtime source:
{{ states('sensor.brewassistant_runtime_source_status') }}
```

Expected:

```text
Existing v0.8 values should still work.
```

---

## 3. Runtime normalization check

```jinja
# BrewAssistant v0.9 runtime normalization check

Recipe name:
{{ states('sensor.brewassistant_runtime_recipe_name') }}

Runtime status:
{{ states('sensor.brewassistant_runtime_status') }}

Primary target:
{{ states('sensor.brewassistant_runtime_primary_target_temperature') }} °C

Cold crash target:
{{ states('sensor.brewassistant_runtime_cold_crash_target_temperature') }} °C

Target FG:
{{ states('sensor.brewassistant_runtime_target_fg') }}

Source status:
{{ states('sensor.brewassistant_runtime_source_status') }}

Brewfather available:
{{ states('binary_sensor.brewassistant_runtime_brewfather_available') }}
```

Expected when current runtime entities exist:

```text
Recipe name: active recipe name or No active recipe
Runtime status: Fermenting / current status / Unknown
Primary target: numeric or unknown
Cold crash target: numeric or unknown
Target FG: numeric or unknown
Source status: OK/Partial/Unavailable · x/5 runtime sources available
Brewfather available: on when recipe name or runtime status exists
```

---

## 4. Runtime attributes check

```jinja
# BrewAssistant v0.9 runtime attributes check

Source status:
{{ states('sensor.brewassistant_runtime_source_status') }}

Available:
{{ state_attr('sensor.brewassistant_runtime_source_status', 'available_count') }} / {{ state_attr('sensor.brewassistant_runtime_source_status', 'total_count') }}

Recipe entity:
{{ state_attr('sensor.brewassistant_runtime_source_status', 'runtime_recipe_name_entity_entity') }}
Available: {{ state_attr('sensor.brewassistant_runtime_source_status', 'runtime_recipe_name_entity_available') }}

Status entity:
{{ state_attr('sensor.brewassistant_runtime_source_status', 'runtime_status_entity_entity') }}
Available: {{ state_attr('sensor.brewassistant_runtime_source_status', 'runtime_status_entity_available') }}

Primary target entity:
{{ state_attr('sensor.brewassistant_runtime_source_status', 'runtime_primary_target_entity_entity') }}
Available: {{ state_attr('sensor.brewassistant_runtime_source_status', 'runtime_primary_target_entity_available') }}

Cold crash target entity:
{{ state_attr('sensor.brewassistant_runtime_source_status', 'runtime_cold_crash_target_entity_entity') }}
Available: {{ state_attr('sensor.brewassistant_runtime_source_status', 'runtime_cold_crash_target_entity_available') }}

Target FG entity:
{{ state_attr('sensor.brewassistant_runtime_source_status', 'runtime_target_fg_entity_entity') }}
Available: {{ state_attr('sensor.brewassistant_runtime_source_status', 'runtime_target_fg_entity_available') }}
```

---

## 5. Options flow check

Open:

```text
Settings -> Devices & services -> BrewAssistant -> Configure
```

Confirm the new runtime fields appear:

```text
Runtime recipe name source
Runtime status source
Runtime primary target source
Runtime cold crash target source
Runtime target FG source
```

Save without changing anything.

Then rerun the runtime normalization check.

---

## 6. Entity registry check

If new v0.9 entities get numbered ids, find them by name:

```jinja
# BrewAssistant v0.9 real runtime entities

{% for s in states.sensor %}
  {% if s.entity_id is search('brewassistant') and (
        s.entity_id is search('runtime_')
        or s.name | lower is search('runtime')
      ) %}
{{ s.entity_id }} = {{ s.name }} = {{ s.state }}
  {% endif %}
{% endfor %}

{% for s in states.binary_sensor %}
  {% if s.entity_id is search('brewassistant') and (
        s.entity_id is search('runtime_')
        or s.name | lower is search('runtime')
      ) %}
{{ s.entity_id }} = {{ s.name }} = {{ s.state }}
  {% endif %}
{% endfor %}
```

Correct entity ids:

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

## 7. Notes

Some runtime source entities may legitimately be unavailable depending on the active Brewfather/YAML setup.

`binary_sensor.brewassistant_runtime_brewfather_available` should be `on` when at least recipe name or runtime status is available.

---

## 8. Rollback plan

If v0.9 causes issues, restore the previous v0.8 custom component folder and restart Home Assistant.

v0.9 is still read-only. No hardware control is added.
