# Dashboard

## Overview

The BrewAssistant dashboard is built around expandable premium cards.

Each major module follows this pattern:

```text
Top card
  status, icon, short summary, enable/power button

Collapsed mode
  only the top card is visible

Expanded mode
  metric tiles, actions and details become visible
```

## Current dashboard modules

### Problem Center

Shows system health and active problem count.

Recommended placement: top of dashboard.

### FWK / Fermentation Process

Used during fermentation. Contains:

- recipe/runtime status
- gravity
- fermentation temperature
- planned temperature
- days left
- Start Batch
- Spunding
- Dry Hop
- Cold Crash
- Transfer to Keg
- expandable details

Enable helper:

```yaml
input_boolean.fwk_process_card_enabled
```

Details helper:

```yaml
input_boolean.fwk_show_details
```

### Fermentation Chamber

Climate-control overview for fermentation chamber.

Typical core entity:

```yaml
climate.fermentation_chamber
```

### Kegerator

Premium kegerator card with:

- Current
- Target
- Delta
- Cooling
- Temps
- System

Section helper:

```yaml
input_select.kegerator_card_section
```

Recommended options:

```yaml
options:
  - none
  - temps
  - status
```

### Hot Side

Brew day workflow card.

Enable helper:

```yaml
input_boolean.brewassistant_hot_side_enabled
```

Settings helper:

```yaml
input_boolean.brewassistant_hot_side_show_settings
```

## Dashboard style

The visual style uses:

- dark gradient cards
- rounded corners
- high-contrast icons
- contextual colors:
  - green = OK / stable / done
  - blue = cooling / chill
  - amber/orange = warm / active hot side / warning
  - red = critical / reset / problem

## Mobile strategy

No separate mobile dashboard is required for now. The current approach is:

- use one dashboard
- use collapsible sections
- use 2-column grids where text would otherwise be cut
- avoid duplicate mobile-only maintenance
