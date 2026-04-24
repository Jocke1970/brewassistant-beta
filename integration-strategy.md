# BrewAssistant – Integration Strategy

## Current Integrations

## Brewfather

Primary entity:

- `sensor.brewfather_all_batches_data`

Used for:

- recipe name
- batch status
- batch number
- fermentation start
- fermentation end
- fermentation steps
- primary fermentation temperature
- cold crash temperature
- days left

Known current limitation:

- OG and FG are not yet confirmed from Brewfather data
- `measuredOg` may be `null`
- readings may be empty

Therefore:

- OG and FG remain fallback-backed for now

## RAPT / Yellow Pill

Current live entities:

- `sensor.yellow_pill_temperature`
- `sensor.yellow_pill_gravity_2`

Used for:

- live fermentation temperature
- live gravity
- attenuation
- gravity points left
- stability logic

Note:

- when the Pill is not in liquid, gravity values may be unrealistic

## Fermentation Chamber

Entity:

- `climate.fermentation_chamber`

Known attributes:

- `current_temperature`
- `target_temp_low`
- `target_temp_high`
- `hvac_action`
- `hvac_modes`
- `preset_mode`

Used for:

- chamber midpoint
- chamber span
- recipe vs chamber delta
- alignment status
- semiauto target application

## Kegerator

Entity:

- `climate.kegerator_kylskap`

Known attributes:

- `current_temperature`
- `temperature`
- `hvac_action`
- `hvac_modes`
- `min_temp`
- `max_temp`

Used for:

- current temperature
- target temperature
- delta
- cooling/action status

## Source Priority

Recipe runtime:

1. Brewfather all batches data
2. fallback helpers

Live runtime:

1. Yellow Pill / RAPT sensors
2. fallback / unavailable handling

Chamber target:

1. Brewfather/runtime active recipe target
2. manual fallback target

## Safety Principle

BrewAssistant should observe first, suggest second, and only apply settings with explicit semiauto or guarded auto-apply logic.
