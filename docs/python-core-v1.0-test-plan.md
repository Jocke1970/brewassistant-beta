# BrewAssistant Python Core v1.0 Test Plan

v1.0 marks the read-only core as stable.

Goal:

```text
Verify that BrewAssistant Core exposes stable read-only sensors for core fermentation status, source health, smart recommendations, next action and Brewfather/runtime normalization.
```

---

## 1. Update and restart

1. Replace the whole folder:

```text
/config/custom_components/brewassistant/
```

2. Restart Home Assistant fully.

3. Confirm version:

```text
1.0.0
```

---

## 2. Core version check

```jinja
# BrewAssistant v1.0 core version check

Core version:
{{ states('sensor.brewassistant_core_version') }}

Milestone:
{{ state_attr('sensor.brewassistant_core_version', 'milestone') }}

Hardware control:
{{ state_attr('sensor.brewassistant_core_version', 'hardware_control') }}

Safe mode:
{{ state_attr('sensor.brewassistant_core_version', 'safe_mode') }}

Notes:
{{ state_attr('sensor.brewassistant_core_version', 'notes') }}
```

Expected:

```text
Core version: 1.0.0
Milestone: Read-only Core Stable
Hardware control: False
Safe mode: read_only
```

---

## 3. Read-only core summary check

```jinja
# BrewAssistant v1.0 read-only core summary

Status summary:
{{ states('sensor.brewassistant_status_summary') }}

Process summary:
{{ states('sensor.brewassistant_process_summary') }}

Smart summary:
{{ states('sensor.brewassistant_smart_recommendation_summary') }}

Source health:
{{ states('sensor.brewassistant_source_health_summary') }}

Runtime source:
{{ states('sensor.brewassistant_runtime_source_status') }}

Next action:
{{ states('sensor.brewassistant_next_recommended_action') }}
```

Expected:

```text
All values should be meaningful and not unknown/unavailable.
```

---

## 4. Runtime check

```jinja
# BrewAssistant v1.0 runtime check

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

Brewfather available:
{{ states('binary_sensor.brewassistant_runtime_brewfather_available') }}
```

Expected current example:

```text
Recipe name: FWK Creative Extra Light - Summer IPL v3 (NovaLager)
Runtime status: Fermenting
Primary target: 15.0 °C
Cold crash target: 2.0 °C
Brewfather available: on
```

---

## 5. Source health check

```jinja
# BrewAssistant v1.0 source health check

Health summary:
{{ states('sensor.brewassistant_source_health_summary') }}

Health level:
{{ states('sensor.brewassistant_source_health_level') }}

Liquid source:
{{ states('sensor.brewassistant_configured_liquid_temp_entity') }} · {{ states('binary_sensor.brewassistant_source_liquid_temp_available') }}

Gravity source:
{{ states('sensor.brewassistant_configured_gravity_entity') }} · {{ states('binary_sensor.brewassistant_source_gravity_available') }}
```

Expected:

```text
Health summary: OK · 6/6 sources available
Health level: ok
```

---

## 6. Debug card check

Optional new stable card:

```text
dashboards/cards/brewassistant_core_debug_card_v1.yaml
```

Check:

```text
[ ] Top card renders
[ ] Core version shows 1.0.0
[ ] Runtime section shows recipe/status/targets
[ ] Source health shows OK or useful warning
[ ] Next action shows current recommendation
[ ] No red Lovelace YAML errors
```

Existing v2 card remains available:

```text
dashboards/cards/brewassistant_core_debug_card.yaml
```

---

## 7. Options flow check

Open:

```text
Settings -> Devices & services -> BrewAssistant -> Configure
```

Confirm source/runtime fields appear. Save without changing anything.

Then rerun sections 2-4.

---

## 8. Entity registry check

If new entities appear with numbered ids, find them by name:

```jinja
# BrewAssistant v1.0 real core version entity

{% for s in states.sensor %}
  {% if s.entity_id is search('brewassistant') and (
        s.entity_id is search('core_version')
        or s.name | lower is search('core version')
      ) %}
{{ s.entity_id }} = {{ s.name }} = {{ s.state }}
  {% endif %}
{% endfor %}
```

Correct entity id:

```text
sensor.brewassistant_core_version
```

---

## 9. Rollback plan

If v1.0 causes issues, restore the previous v0.9 custom component folder and restart Home Assistant.

v1.0 is still read-only. No hardware control is added.
