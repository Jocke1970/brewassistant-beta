# Roadmap

This document outlines the suggested BrewAssistant v4 roadmap.

---

## v4.0 documentation cleanup

Goal: create a clean documentation foundation.

Tasks:

```text
[ ] Replace old docs with v4 README
[ ] Add setup guide
[ ] Add structure guide
[ ] Add entity guide
[ ] Add state-machine guide
[ ] Add manual-mode guide
[ ] Add dashboard guide
[ ] Add Brewfather integration guide
[ ] Add legacy migration guide
```

---

## v4.1 entity namespace cleanup

Goal: reduce or remove `fwk_*` naming.

Tasks:

```text
[ ] Inventory all current fwk_* entities
[ ] Create migration map
[ ] Add brew_process_* entities
[ ] Add brew_batch_* entities
[ ] Add brew_recipe_* entities
[ ] Update dashboard YAML
[ ] Keep temporary compatibility aliases
[ ] Remove old names when safe
```

---

## v4.2 dashboard refresh

Goal: align dashboards with backend v4 naming and state model.

Tasks:

```text
[ ] Fermentation top card
[ ] Fermentation detail card
[ ] Chamber card
[ ] Manual mode card
[ ] Notifications card
[ ] Kegerator card
[ ] Debug/runtime card
```

---

## v4.3 manual mode improvements

Goal: make manual cider/bucket fermentation tracking strong enough to use standalone.

Tasks:

```text
[ ] Manual OG/SG/FG helpers
[ ] Gravity stability logic
[ ] Last reading timestamp
[ ] Manual next-step sensor
[ ] Manual reminder notifications
[ ] Manual dashboard card
```

---

## v4.4 Brewfather runtime improvements

Goal: make Brewfather data more robust and dashboard-safe.

Tasks:

```text
[ ] Normalize active batch data
[ ] Normalize primary target temp
[ ] Normalize cold crash temp
[ ] Normalize target FG
[ ] Improve fallback handling
[ ] Add debug sensor for data source
[ ] Add Brewfather docs/examples
```

---

## v4.5 chamber automation polish

Goal: make fermentation chamber control safe, visible and semi-automatic.

Tasks:

```text
[ ] Apply recipe target script
[ ] Delta sensors
[ ] Chamber status sensor
[ ] Heating/cooling/idle display
[ ] Compressor/fan support where relevant
[ ] Better safety/override controls
```

---

## v4.6 notifications polish

Goal: make alerts useful without being noisy.

Tasks:

```text
[ ] Master notification toggle
[ ] Warning toggle
[ ] Persistent notification toggle
[ ] Manual mode reminders
[ ] Cold crash readiness notification
[ ] Transfer readiness notification
[ ] Chamber warning notification
```

---

## v5 / future: hot-side and BrewZilla

Goal: add brew-day support without polluting fermentation logic.

Potential tasks:

```text
[ ] BrewZilla/RAPT data model
[ ] Hot-side state machine
[ ] Mash step tracking
[ ] Boil timer
[ ] Hop addition reminders
[ ] Brewfather BrewTracker research
[ ] Brew day dashboard
```

---

## Long-term ideas

```text
[ ] Recipe import/export helpers
[ ] BeerXML workflow support
[ ] Packaging/kegging checklist module
[ ] Cleaning checklist module
[ ] Inventory/shopping module
[ ] Label/print document generation
[ ] Multi-batch support
```

