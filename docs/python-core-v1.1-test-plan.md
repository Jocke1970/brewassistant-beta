# BrewAssistant Python Core v1.1 Test Plan

v1.1 is a dashboard and branding polish release on top of the stable read-only core.

No hardware control is added.

---

## 1. Update and restart

Replace the Home Assistant custom component folder with the latest repository version:

```text
/config/custom_components/brewassistant/
```

Restart Home Assistant fully.

Expected version:

```text
1.1.0
```

---

## 2. Install or update logo asset

Recommended Home Assistant logo path:

```text
/config/www/brewassistant/BrewAssistant_color_small.png
```

Dashboard URL:

```text
/local/brewassistant/BrewAssistant_color_small.png
```

Source asset:

```text
https://raw.githubusercontent.com/Jocke1970/BrewAssistant/main/pictures/BrewAssistant_color_small.png
```

---

## 3. Core update check

Run in Home Assistant Developer Tools -> Template:

```jinja
# BrewAssistant v1.1 core update check

Core version:
{{ states('sensor.brewassistant_core_version') }}

Milestone:
{{ state_attr('sensor.brewassistant_core_version', 'milestone') }}

Hardware control:
{{ state_attr('sensor.brewassistant_core_version', 'hardware_control') }}

Source health:
{{ states('sensor.brewassistant_source_health_summary') }}

Runtime source:
{{ states('sensor.brewassistant_runtime_source_status') }}

Next action:
{{ states('sensor.brewassistant_next_recommended_action') }}
```

Expected:

```text
Core version: 1.1.0
Milestone: Read-only Core Stable
Hardware control: False
Source health: OK · 6/6 sources available
Runtime source: OK · 5/5 runtime sources available
```

---

## 4. Dashboard card check

New branded card:

```text
dashboards/cards/brewassistant_core_debug_card_v1_1.yaml
```

Checklist:

```text
[ ] Card renders without Lovelace YAML errors
[ ] Logo appears in the top card
[ ] Core version shows 1.1.0
[ ] Runtime recipe and status appear
[ ] Source health appears
[ ] Next action appears
[ ] Branding setup expander appears
```

---

## 5. Logo fallback note

If the card renders but the logo does not appear:

```text
[ ] Confirm the logo file exists under /config/www/brewassistant/
[ ] Open /local/brewassistant/BrewAssistant_color_small.png in the browser
[ ] Clear browser cache or refresh the dashboard
```

---

## 6. Options flow smoke test

Open:

```text
Settings -> Devices & services -> BrewAssistant -> Configure
```

Confirm that the form opens. Save without changing anything. Then rerun the core update check.

---

## 7. Rollback plan

If v1.1 causes issues, restore the previous v1.0 custom component folder and restart Home Assistant.

v1.1 is still read-only. No hardware control is added.
