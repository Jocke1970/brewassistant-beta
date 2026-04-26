# BrewAssistant – Acceptance Criteria

## Functional v1

A functional v1 is considered working when:

- helpers load without duplicate warnings
- runtime sensors load
- workflow sensors load
- chamber sensors load
- smart automation sensors load
- dashboard cards render without major visual issues

## Brewfather Runtime

Expected behavior:

- when Brewfather is online:
  - recipe name comes from Brewfather
  - status comes from Brewfather
  - primary temp comes from Brewfather fermentation step
  - cold crash temp comes from Brewfather fermentation step
  - source is `brewfather_all_batches_data`

- when Brewfather is offline:
  - runtime falls back safely
  - dashboard still works
  - no templates should break

## Chamber

Expected behavior:

- chamber midpoint is calculated from target low/high
- recipe active target is shown
- recipe vs chamber delta is calculated
- live vs recipe delta is calculated
- alignment status is readable
- Apply Brewfather Target sets chamber range safely

## Kegerator

Expected behavior:

- current temp is read from `climate.kegerator_kylskap.attributes.current_temperature`
- target temp is read from `climate.kegerator_kylskap.attributes.temperature`
- delta is calculated directly in the card
- cooling status is shown
- details sections open/close correctly

## Notifications

Expected behavior:

- process notifications are generated at relevant state transitions
- chamber mismatch warnings do not spam immediately
- notification lock can be reset with batch reset

## UI

Expected behavior:

- main card text is readable
- chamber card text is readable
- kegerator card text is readable
- dark mode style is consistent
- expanded details are optional
