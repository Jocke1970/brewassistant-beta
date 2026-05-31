# Counter Flow Chiller backend

BrewAssistant supports an optional Counter Flow Chiller sanitation flow during boil.

The goal is to remind the operator to connect the Counter Flow Chiller during the final part of boil, then provide an explicit **CFC Ready** action that starts BrewZilla pump circulation through the chiller.

## Why this exists

When using a Counter Flow Chiller, hot wort should be circulated through the chiller before cooling so the wort path is sanitized.

Typical operator flow:

```text
Boil running
→ CFC reminder appears before the configured sanitation window
→ operator connects hoses/chiller
→ operator presses CFC Ready
→ BrewAssistant sets pump utilization
→ BrewAssistant starts BrewZilla pump
→ hot wort circulates through CFC for final boil minutes
```

## Python-owned entities

| Entity | Purpose |
| --- | --- |
| `switch.brewassistant_counterflow_chiller_enabled` | Enables CFC sanitation reminders for the current brewday. |
| `number.brewassistant_counterflow_chiller_sanitize_minutes` | How many final boil minutes should circulate through CFC. Default: 15 min. Range: 10–25 min. |
| `number.brewassistant_counterflow_chiller_pump_utilization` | Pump utilization used when CFC Ready is pressed. Default: 100%. Range: 0–100%, step 5. |
| `button.brewassistant_counterflow_chiller_ready` | Explicit operator confirmation that CFC is connected and pump circulation should start. |

## Alert integration

CFC uses the existing brewday addition alert sensor family.

When enabled and current runtime stage is boil/kok, BrewAssistant injects a virtual candidate:

```text
next_addition_type: counterflow_chiller_sanitize
next_addition_name: Counter Flow Chiller
```

This appears as:

```text
sensor.brewassistant_brewday_addition_alert_state
sensor.brewassistant_brewday_addition_alert_message
```

The alert is suppressed after `button.brewassistant_counterflow_chiller_ready` is pressed because the CFC backend marks the chiller as ready.

## Backend files

```text
custom_components/brewassistant/counterflow_chiller.py
custom_components/brewassistant/brewday_addition_alerts.py
custom_components/brewassistant/switch.py
custom_components/brewassistant/number.py
custom_components/brewassistant/button.py
```

## Dashboard card

Suggested dashboard card:

```text
dashboards/counterflow_chiller_card_v1.yaml
```

This card should be placed near the Brewday operator card or in a hot-side tools section.

## Safety notes

CFC Ready is not automatic. It requires explicit operator action.

The button starts the BrewZilla pump and sets pump utilization, but does not change main power or heater state.

The operator should verify hose routing, clamps and return path before pressing CFC Ready.
