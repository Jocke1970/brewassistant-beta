# BrewAssistant Python Core v0.6 Test Plan

v0.6 adds read-only source health diagnostics.

Goal:

```text
Show exactly which configured entities BrewAssistant reads, and whether each source exists and has a usable state.
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
0.6.0
```

---

## 2. Base sanity check

```jinja
# BrewAssistant v0.6 base sanity check

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

Summary:
{{ states('sensor.brewassistant_smart_recommendation_summary') }}
```

Expected:

```text
Existing v0.5 values should still work.
```

---

## 3. Source health summary check

```jinja
# BrewAssistant v0.6 source health summary check

Health summary:
{{ states('sensor.brewassistant_source_health_summary') }}

Health level:
{{ states('sensor.brewassistant_source_health_level') }}

Available:
{{ state_attr('sensor.brewassistant_source_health_summary', 'sources_available') }} / {{ state_attr('sensor.brewassistant_source_health_summary', 'sources_total') }}

Liquid source:
{{ state_attr('sensor.brewassistant_source_health_summary', 'liquid_temp_entity_entity') }}
Available: {{ state_attr('sensor.brewassistant_source_health_summary', 'liquid_temp_entity_available') }}
Reason: {{ state_attr('sensor.brewassistant_source_health_summary', 'liquid_temp_entity_reason') }}

Gravity source:
{{ state_attr('sensor.brewassistant_source_health_summary', 'gravity_entity_entity') }}
Available: {{ state_attr('sensor.brewassistant_source_health_summary', 'gravity_entity_available') }}
Reason: {{ state_attr('sensor.brewassistant_source_health_summary', 'gravity_entity_reason') }}
```

Expected when all configured sources are valid:

```text
Health level: ok
Health summary: OK · 6/6 sources available
```

---

## 4. Configured source entity check

```jinja
# BrewAssistant v0.6 configured entities

Liquid temp entity:
{{ states('sensor.brewassistant_configured_liquid_temp_entity') }}

Chamber temp entity:
{{ states('sensor.brewassistant_configured_chamber_temp_entity') }}

Recipe target entity:
{{ states('sensor.brewassistant_configured_recipe_target_entity') }}

Cold crash active entity:
{{ states('sensor.brewassistant_configured_cold_crash_active_entity') }}

Cold crash target entity:
{{ states('sensor.brewassistant_configured_cold_crash_target_entity') }}

Gravity entity:
{{ states('sensor.brewassistant_configured_gravity_entity') }}
```

Expected current setup:

```text
Liquid temp entity: sensor.yellow_pill_temperature
Chamber temp entity: sensor.kyl_temperatur_4
Gravity entity: sensor.yellow_pill_gravity
```

Other entity ids depend on current options/config.

---

## 5. Availability binary sensors

```jinja
# BrewAssistant v0.6 source availability flags

Liquid temp available:
{{ states('binary_sensor.brewassistant_source_liquid_temp_available') }}

Chamber temp available:
{{ states('binary_sensor.brewassistant_source_chamber_temp_available') }}

Recipe target available:
{{ states('binary_sensor.brewassistant_source_recipe_target_available') }}

Cold crash active available:
{{ states('binary_sensor.brewassistant_source_cold_crash_active_available') }}

Cold crash target available:
{{ states('binary_sensor.brewassistant_source_cold_crash_target_available') }}

Gravity available:
{{ states('binary_sensor.brewassistant_source_gravity_available') }}
```

Expected if all configured sources exist and are usable:

```text
All: on
```

---

## 6. Entity registry check

If new v0.6 entities show as numbered `sensor.brewassistant_8`, etc., search by name:

```jinja
# BrewAssistant v0.6 source health real entities

{% for s in states.sensor %}
  {% if s.entity_id is search('brewassistant') and (
        s.entity_id is search('source_health')
        or s.entity_id is search('configured_')
        or s.name | lower is search('source health')
        or s.name | lower is search('configured')
      ) %}
{{ s.entity_id }} = {{ s.name }} = {{ s.state }}
  {% endif %}
{% endfor %}

{% for s in states.binary_sensor %}
  {% if s.entity_id is search('brewassistant') and (
        s.entity_id is search('source_')
        or s.name | lower is search('source')
      ) %}
{{ s.entity_id }} = {{ s.name }} = {{ s.state }}
  {% endif %}
{% endfor %}
```

Rename only if needed.

---

## 7. Safe negative test, optional

Only do this if you want to verify diagnostics:

1. Open BrewAssistant -> Configure.
2. Temporarily change `Gravity source` to a fake entity:

```text
sensor.fake_gravity_test
```

3. Save.
4. Confirm:

```text
source_health_level = warning/problem
source_gravity_available = off
reason = entity missing
```

5. Change it back to:

```text
sensor.yellow_pill_gravity
```

6. Save again.

---

## 8. Rollback plan

If v0.6 causes issues, restore the previous v0.5 custom component folder and restart Home Assistant.

v0.6 is still read-only. No hardware control is added.
