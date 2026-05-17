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
[ ] Add custom integration guide
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

## v4.2 Python Core foundation

Goal: introduce a Home Assistant custom integration that can run beside the existing YAML packages.

Tasks:

```text
[x] Add custom_components/brewassistant skeleton
[x] Add config flow
[x] Add read-only coordinator
[x] Normalize liquid temperature and chamber fallback
[x] Normalize effective target temperature
[x] Use cold crash target when cold crash is active
[x] Normalize SG/gravity
[x] Add runtime-ready and fallback binary sensors
[x] Add dashboard support sensors for target mode, status, severity and summary
[ ] Add options flow for changing source entities after setup
[ ] Add automated tests
```

---

## v4.3 dashboard refresh

Goal: align dashboards with backend v4 naming, Python Core entities and state model.

Tasks:

```text
[x] Fermentation Process card reads Python Core live values
[x] Fermentation Status card reads Python Core live values
[x] Fermentation Process card reads Python Core v0.3 process mirror
[x] Fermentation Status / Control card reads Python Core v0.3 process mirror
[x] Debug/runtime card
[ ] Fermentation top card cleanup
[ ] Chamber card
[ ] Manual mode card
[ ] Notifications card
[ ] Kegerator card
[ ] Reduce repeated JavaScript/Jinja status logic in dashboard YAML
```

---

## v4.4 dashboard logic migration

Goal: move display decision logic out of Lovelace cards and into Python support sensors.

Tasks:

```text
[x] Temperature target mode sensor
[x] Temperature status sensor
[x] Temperature severity sensor
[x] Status summary sensor
[x] Problem level sensor
[x] Icon hint attributes for dashboard use
[x] Color/severity hint attributes for dashboard use
[x] Process summary sensor
[x] Smart recommendation summary sensor
[ ] Next recommended action sensor
[ ] Compact health snapshot sensor
```

---

## v4.5 process state migration

Goal: move fermentation process state machine decisions from YAML templates into Python.

Tasks:

```text
[x] Mirror existing process status in Python
[x] Mirror existing next step in Python
[x] Mirror current action stage in Python
[x] Mirror next action stage in Python
[x] Add read-only comparison signals between YAML and Python process state
[x] Switch fermentation dashboards to Python process entities after validation
[ ] Keep YAML process package as compatibility layer during migration
```

---

## v4.6 smart fermentation recommendations

Goal: move smart fermentation logic into Python as read-only recommendations before any hardware control is moved.

Tasks:

```text
[x] Heat needed recommendation
[x] Heat permitted recommendation
[x] Cooling recommended state
[x] Fan assist recommended state
[x] Heat block reason
[x] Suggested heat pulse length
[ ] Pill stale detection
[x] Rising-too-fast detection
[x] Read-only debug summary
```

---

## v4.7 smart fermentation control

Goal: only after v4.6 has been validated, move safe hardware control into the custom integration.

Tasks:

```text
[ ] Expose control switch/entity
[ ] Expose mode select
[ ] Expose tuning numbers
[ ] Add services/buttons for controlled actions
[ ] Apply climate target safely
[ ] Control heat mat safely
[ ] Control fan assist safely
[ ] Preserve manual override and emergency off paths
```

---

## v4.8 manual mode improvements

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

## v4.9 Brewfather runtime improvements

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

## v4.10 chamber automation polish

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

## v4.11 notifications polish

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

