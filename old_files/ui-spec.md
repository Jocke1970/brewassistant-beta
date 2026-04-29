# BrewAssistant – UI Specification

## Design Style

Current style:

- premium dark cards
- high contrast text
- soft gradients
- rounded corners
- compact but readable status labels
- expandable details

## Main BrewAssistant Card

File:

- `brewassistant_main_card_dark_v1.yaml`

Shows:

- recipe name
- process status
- next step
- SG
- fermentation temperature
- batch age
- attenuation
- Brewfather planned summary

Includes:

- details toggle
- current action card
- next action card
- manual workflow buttons
- expanded diagnostic details

## Chamber Card

File:

- `brewassistant_chamber_card_v1_2_semiauto.yaml`

Shows:

- fermentation chamber status
- recipe target
- suggested chamber range
- chamber target range
- live vs recipe delta
- recipe vs chamber delta
- alignment status

Includes:

- power button
- Apply Brewfather Target button
- details sections
- diagnostics

## Kegerator Card

File:

- `brewassistant_kegerator_card_v1_1_premium.yaml`

Shows:

- kegerator climate state
- current temperature from climate attribute
- target temperature from climate attribute
- calculated delta
- cooling status
- fan/status details

Includes expandable sections:

- Modes
- Temps
- Status

## UI Rules

- avoid light backgrounds with light text
- keep top cards dark and high contrast
- use `climate.*` attributes directly when they are the source of truth
- keep details hidden unless needed
- keep action cards focused on the current step
