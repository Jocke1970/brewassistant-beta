# BrewAssistant Python Core v0.8 Test Plan

v0.8 adds a read-only next recommended action sensor.

Goal:

```text
Expose one compact sensor that dashboards and notifications can use for the next useful action.
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
0.8.0
```

---

## 2. Base sanity check

```jinja
# BrewAssistant v0.8 base sanity check

Source health:
{{ states('sensor.brewassistant_source_health_summary') }}

Smart summary:
{{ states('sensor.brewassistant_smart_recommendation_summary') }}

Process:
{{ states('sensor.brewassistant_process_status') }}

Next action:
{{ states('sensor.brewassistant_next_recommended_action') }}
```

Expected:

```text
Existing v0.6 values should still work.
```

---

## 3. Next action check

```jinja
# BrewAssistant v0.8 next action check

Action:
{{ states('sensor.brewassistant_next_recommended_action') }}

Category:
{{ state_attr('sensor.brewassistant_next_recommended_action', 'category') }}

Priority:
{{ state_attr('sensor.brewassistant_next_recommended_action', 'priority') }}

Reason:
{{ state_attr('sensor.brewassistant_next_recommended_action', 'reason') }}

Icon:
{{ state_attr('sensor.brewassistant_next_recommended_action', 'icon') }}
```

Expected in the current cold crash scenario where liquid is above target and cooling/fan is recommended:

```text
Action: Cooling + fan recommended
Category: smart_fermentation
Priority: info
Reason: Cooling would help · Fan assist recommended for cooling
Icon: mdi:fan-chevron-up
```

If cooling is no longer recommended and process is still cold crash:

```text
Action: Maintain cold crash
Category: process
Priority: ok
```

---

## 4. Negative source-health priority check, optional

Only do this if you want to verify action priority:

1. Open BrewAssistant -> Configure.
2. Temporarily set Gravity source to:

```text
sensor.fake_gravity_test
```

3. Save.
4. Confirm next action becomes source-health related:

```text
Check source configuration
```

5. Change Gravity source back to:

```text
sensor.yellow_pill_gravity
```

6. Save again.

---

## 5. Entity registry check

If the next action sensor appears under a weird id, search by name:

```jinja
# BrewAssistant v0.8 real next action entity

{% for s in states.sensor %}
  {% if s.entity_id is search('brewassistant') and (
        s.entity_id is search('next_recommended')
        or s.name | lower is search('next recommended')
      ) %}
{{ s.entity_id }} = {{ s.name }} = {{ s.state }}
  {% endif %}
{% endfor %}
```

Correct entity id:

```text
sensor.brewassistant_next_recommended_action
```

---

## 6. Rollback plan

If v0.8 causes issues, restore the previous v0.6 custom component folder and restart Home Assistant.

v0.8 is still read-only. No hardware control is added.
