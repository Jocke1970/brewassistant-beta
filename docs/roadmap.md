# Roadmap

This document outlines the suggested BrewAssistant v4 roadmap.

---

## v4.0 documentation cleanup

Goal: create a clean documentation foundation.

Tasks:

```text
[x] Replace old docs with v4 README
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
[x] Add options flow for changing source entities after setup
[x] Add core version sensor
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
[x] Branded Python Core v1.1 dashboard card
[x] Archive legacy debug cards from active dashboard
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
[x] Next recommended action sensor
[x] Source health summary sensor
[x] Runtime source status sensor
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
[x] Pill stale detection
[x] Rising-too-fast detection
[x] Read-only debug summary
[x] Next recommended action integration
```

---

## v4.7 smart chamber target recommendation

Goal: recommend a chamber assist target/range that helps liquid temperature move toward the recipe target systematically.

This should remain read-only before any hardware control is moved.

Concept:

```text
Recipe target = desired liquid temperature
Liquid temp = actual liquid temperature
Chamber assist target = recommended chamber setpoint/range to move liquid toward target
```

Suggested entities:

```text
sensor.brewassistant_smart_chamber_assist_target
sensor.brewassistant_smart_chamber_target_low_recommended
sensor.brewassistant_smart_chamber_target_high_recommended
sensor.brewassistant_smart_chamber_strategy
sensor.brewassistant_smart_chamber_reason
binary_sensor.brewassistant_smart_chamber_adjustment_recommended
```

Tasks:

```text
[ ] Add read-only chamber assist target calculation
[ ] Add recommended chamber target low/high sensors
[ ] Add strategy sensor: cool_down / warm_up / maintain / hold / unavailable
[ ] Add reason sensor for dashboard text
[ ] Use liquid delta magnitude to choose offset from recipe target
[ ] Use temperature rate to reduce overshoot risk
[ ] Clamp recommendations to climate chamber min/max limits where known
[ ] Add dashboard display before any apply-service exists
[ ] Validate across cold crash and normal fermentation scenarios
```

Example behavior:

```text
Liquid above target -> recommend chamber below recipe target
Liquid below target -> recommend chamber above recipe target
Liquid near target -> recommend chamber near recipe target
Liquid moving too fast -> reduce offset or hold
```

---

## v4.8 smart fermentation control

Goal: only after v4.6 and v4.7 have been validated, move safe hardware control into the custom integration.

Tasks:

```text
[ ] Expose control switch/entity
[ ] Expose mode select
[ ] Expose tuning numbers
[ ] Add services/buttons for controlled actions
[ ] Apply climate target safely from recommended chamber range
[ ] Control heat mat safely
[ ] Control fan assist safely
[ ] Preserve manual override and emergency off paths
```

---

## v4.9 Brewfather runtime improvements

Goal: make Brewfather data more robust and dashboard-safe.

Tasks:

```text
[x] Normalize runtime recipe name
[x] Normalize runtime status
[x] Normalize primary target temp
[x] Normalize cold crash temp
[x] Normalize target FG
[x] Add runtime source status
[x] Add Brewfather availability binary sensor
[ ] Add Brewfather docs/examples
```

---

## v4.10 carbonation and packaging process

Goal: add carbonation/kolsyrning as a post-fermentation process stage after transfer and before serving/storage.

This belongs near Fermentation Process, but should be modeled as packaging/post-fermentation rather than active fermentation control.

Process sequence:

```text
Fermentation -> Cold crash -> Transfer -> Carbonation -> Serving / Storage
```

Suggested entities:

```text
sensor.brewassistant_carbonation_status
sensor.brewassistant_carbonation_method
sensor.brewassistant_carbonation_target_co2_volumes
sensor.brewassistant_carbonation_temperature
sensor.brewassistant_carbonation_pressure_bar
sensor.brewassistant_carbonation_pressure_psi
sensor.brewassistant_carbonation_time_remaining
sensor.brewassistant_carbonation_summary
binary_sensor.brewassistant_carbonation_active
binary_sensor.brewassistant_carbonation_ready
```

Tasks:

```text
[ ] Add carbonation as process stage after transfer
[ ] Support force carbonation in keg
[ ] Support natural carbonation / priming as optional later path
[ ] Calculate pressure from target CO2 volumes and beer temperature
[ ] Show bar/psi conversion
[ ] Track carbonation start time and estimated ready time
[ ] Add carbonation summary to process card / next action
[ ] Add ready-for-serving state
[ ] Keep read-only/calculation-first before any gas-control ideas
```

Notes:

```text
Initial scope should be calculation/tracking only.
No CO2 regulator or hardware control should be assumed.
```

---

## v4.11 BIAB Python module

Goal: migrate BIAB calculations and brewday status toward Python, starting read-only.

Recommended first target:

```text
BIAB Python v0.1 read-only calculations
```

Suggested v0.1 entities:

```text
sensor.brewassistant_biab_profile_name
sensor.brewassistant_biab_batch_volume_l
sensor.brewassistant_biab_grain_weight_kg
sensor.brewassistant_biab_mash_water_l
sensor.brewassistant_biab_sparge_water_l
sensor.brewassistant_biab_pre_boil_volume_l
sensor.brewassistant_biab_boiling_power_mode
sensor.brewassistant_biab_calculation_summary
binary_sensor.brewassistant_biab_ready_for_brewday
```

Tasks:

```text
[ ] Identify current BIAB helpers used as inputs
[ ] Move BIAB calculations into Python read-only sensors
[ ] Mirror current BIAB profile/settings
[ ] Add calculation summary sensor
[ ] Add dashboard card using Python BIAB sensors
[ ] Keep existing YAML helpers as source of truth initially
```

---

## v4.12 manual mode improvements

Goal: make manual cider/bucket fermentation tracking strong enough to use standalone.

Manual Fermentation should remain helper/UI-driven for now, then receive Python summary/bridge sensors later.

Tasks:

```text
[ ] Manual OG/SG/FG helpers
[ ] Gravity stability logic
[ ] Last reading timestamp
[ ] Manual next-step sensor
[ ] Manual reminder notifications
[ ] Manual dashboard card
[ ] Optional Python read-only summary/bridge layer
```

---

## v4.13 chamber automation polish

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

## v4.14 notifications polish

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
[ ] Carbonation ready notification
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
