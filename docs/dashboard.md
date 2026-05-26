# Dashboard Guide

BrewAssistant dashboards should be premium, readable and useful, but they should not own the brewing logic.

Backend packages decide the state. Dashboards display it.

---

## Dashboard goals

A BrewAssistant dashboard should show:

- Current batch.
- Current phase/status.
- Current temperature and target.
- Gravity and target FG.
- Next recommended action.
- Important automation toggles.
- Manual action buttons.
- Warnings and notifications.

---

## Recommended dashboard sections

```text
Fermentation Overview
Process Details
Chamber Control
Manual Mode
Kegerator / Climate Supervisor
Carbonation Cockpit
Notifications
Brewfather Runtime
BrewZilla / Hot Side    # optional/future
```

---

## Top card pattern

Most BrewAssistant dashboards should use a top summary card.

Recommended content:

```text
Batch name
Current status
Next step
Liquid temperature
Target temperature
Gravity
Target FG
Automation status
Power/enable toggle
Expand/details toggle
```

---

## Detail card pattern

Detailed sections should be hidden behind expanders or toggles by default.

Recommended detail sections:

```text
Process logic
Temperature details
Gravity details
Chamber details
Automation controls
Raw runtime data
Debug/diagnostic data
```

---

## Climate Supervisor card

Climate Supervisor replaces the experimental Kegerator Guard card.

Recommended placement:

```text
Near Carbonation Cockpit
or
At the top of the Kegerator / Serving section
```

The card should display:

```text
switch.brewassistant_climate_supervisor_enabled
sensor.kyl_temperatur_4
climate.kegerator_kylskap
switch.kegerator
base_target_temperature
effective_air_target
air_delta
status
action
reason
last_control_action
legacy_guard_enabled
```

Healthy UI behavior:

```text
Air above target
→ status: cooling / strong_cooling
→ effective target lower than base target
→ climate target follows effective target

Air near target
→ status: hold
→ effective target equals base target

Air below target
→ status: relax / hold_warm
→ effective target higher than base target
→ thermostat lets compressor rest
```

The UI must not directly toggle `switch.kegerator` as part of normal supervisor flow. `climate.kegerator_kylskap` owns compressor control.

Legacy `switch.brewassistant_kegerator_guard_enabled` should be off and removed from normal dashboards.

---

## Dashboard entity rule

Dashboard YAML must be updated whenever backend entity names change.

Example migration issue:

```text
Backend renamed sensor.fwk_process_status
but dashboard still references sensor.fwk_process_status
```

This causes the UI to look broken even if the backend is clean.

During migration, always check both:

```text
packages/*.yaml
dashboards/*.yaml
```

---

## Recommended visual style

Common BrewAssistant style:

- Dark theme friendly.
- White or near-white text.
- Gradient backgrounds.
- Rounded corners.
- Soft shadows.
- Clear status chips.
- Large top-level state display.
- Secondary details in smaller text.

---

## Useful Lovelace custom cards

Commonly used cards:

```text
custom:button-card
custom:mushroom-title-card
custom:mushroom-chips-card
custom:mushroom-template-card
custom:mushroom-number-card
custom:vertical-stack-in-card
custom:stack-in-card
custom:bar-card
custom:apexcharts-card
custom:expander-card
```

---

## Debugging dashboard cards

When a card does not work:

1. Check entity names.
2. Check indentation.
3. Check whether the entity is unavailable.
4. Check if the card expects a state but the value is an attribute.
5. Check browser console for custom-card errors.
6. Temporarily simplify the card.

---

## Common Home Assistant pitfalls

### Attribute vs entity

Example:

```text
Target temperature may be an attribute on climate.kegerator_kylskap,
not a standalone sensor.
```

Templates should read the correct source.

### Dark theme text visibility

Some entity/input rows may render dark text on dark backgrounds.

Fix by explicitly styling:

```text
input background
text color
secondary text color
card background
```

### Old namespace references

Search dashboard YAML for:

```text
fwk_
manual_batch_
brewassistant_
recipe_runtime_
```

Then decide what should remain and what should be migrated.

---

## Migration checklist

When changing backend entity names:

```text
[ ] Update package templates
[ ] Update scripts
[ ] Update automations
[ ] Update dashboard YAML
[ ] Update docs/entities.md
[ ] Restart Home Assistant
[ ] Check unavailable entities
[ ] Check browser dashboard errors
```
