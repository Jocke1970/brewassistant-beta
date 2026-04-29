# Troubleshooting

## A card shows unavailable but the sensor exists

Check whether the card is using a different entity in `name`, `label`, or JavaScript templates.

Example issue:

```yaml
name: |
  [[[
    return states['sensor.recipe_runtime_name']?.state ?? 'BrewAssistant';
  ]]]
```

If the entity exists but is `unavailable`, the fallback is not used.

Use explicit fallback:

```yaml
name: |
  [[[
    const n = states['sensor.recipe_runtime_name']?.state;
    if (!n || ['unknown','unavailable','none',''].includes(n)) return 'BrewAssistant';
    return n;
  ]]]
```

## Icons do not show in button-card grid buttons

Likely the icon area is too small or clipped.

Useful style block:

```yaml
show_icon: true
show_name: true
styles:
  grid:
    - grid-template-areas: '"i" "n"'
    - grid-template-columns: 1fr
    - grid-template-rows: 32px 18px
  img_cell:
    - height: 30px
    - align-self: center
  icon:
    - width: 22px
```

## `binary_sensor.kegerator_compressor_active` is unavailable

Confirm this source sensor exists:

```text
sensor.extra_koksmaskin_switch_0_power
```

If it exists and reads `0.0`, the compressor binary sensor should normally be `off`.

## `sensor.recipe_runtime_target_fg` is unknown

Check:

```text
input_number.fwk_recipe_fg
```

If this helper exists, make sure `sensor.recipe_runtime_target_fg` has fallback logic for it.

## `sensor.fwk_current_action_stage` and `sensor.fwk_next_action_stage` show none

This is acceptable when no actionable stage is active.

Better UI text can be added later, such as:

```text
No active action
Waiting for workflow
```

## Details button is unavailable

Current UI expects:

```text
input_boolean.fwk_show_details
```

Add it to the fermentation module if missing.

## Hot Side buttons do not trigger anything

Check whether the UI calls scripts or input buttons.

Recommended UI path:

```text
UI button → script.brewassistant_hot_side_next
```

Alternative path:

```text
UI button → input_button.press → input_button.brewassistant_hot_side_next
```

Avoid mixing both unless the backend explicitly supports both.
