# BrewAssistant Python Core Install / Update

This guide covers manual installation and updates of the BrewAssistant Home Assistant custom component.

---

## Component location

Home Assistant custom component path:

```text
/config/custom_components/brewassistant/
```

Repository source path:

```text
custom_components/brewassistant/
```

---

## Manual update via VS Code / Studio Code Server

1. Download or sync the latest repository branch.
2. Copy the full folder:

```text
custom_components/brewassistant/
```

3. Replace the Home Assistant folder:

```text
/config/custom_components/brewassistant/
```

4. Restart Home Assistant fully.

---

## Logo asset

Dashboard logo target:

```text
/config/www/brewassistant/BrewAssistant_color_small.png
```

Dashboard URL:

```text
/local/brewassistant/BrewAssistant_color_small.png
```

Install/update command:

```bash
mkdir -p /config/www/brewassistant

wget -O /config/www/brewassistant/BrewAssistant_color_small.png \
https://raw.githubusercontent.com/Jocke1970/BrewAssistant/main/pictures/BrewAssistant_color_small.png
```

---

## After every update

Run this in Home Assistant Developer Tools -> Template:

```jinja
# BrewAssistant core update check

Core version:
{{ states('sensor.brewassistant_core_version') }}

Status summary:
{{ states('sensor.brewassistant_status_summary') }}

Source health:
{{ states('sensor.brewassistant_source_health_summary') }}

Runtime source:
{{ states('sensor.brewassistant_runtime_source_status') }}

Next action:
{{ states('sensor.brewassistant_next_recommended_action') }}
```

---

## Expected v1.1 result

```text
Core version: 1.1.0
Source health: OK · 6/6 sources available
Runtime source: OK · 5/5 runtime sources available
```

---

## Safety boundary

BrewAssistant Python Core v1.1 is still read-only.

No climate, switch, fan, heater, fridge, relay or compressor actions are performed by Python Core.
