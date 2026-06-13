# BrewAssistant Dashboard Examples

Dashboard files in this directory are examples/snippets for Home Assistant Lovelace.

The Python integration owns business logic. Dashboard YAML should only render state and call explicit services.

---

## BrewZilla / Brewday

### `brewzilla_cockpit_v3_1.yaml`

Production-oriented BrewZilla cockpit for the verified Brewfather RAW → BrewAssistant → BrewZilla flow.

Shows:

```text
current runtime stage/step
current temperature → target
heater / pump / power chips
progress
next step
Power toggle
ABORT button
BrewZilla diagnostics
```

Important behavior:

```text
If Brewday target is unknown/idle,
fall back to BrewZilla device target.
```

ABORT calls:

```text
brewassistant.abort_brewzilla
```

### `brewfather_raw_timeline_v2.yaml`

Debug/checklist card for `sensor.brewfather_brew_tracker_raw`.

Shows:

```text
raw stage index
raw step index
RAW-resolved active step
DONE / RAW ACTIVE / WAITING rows
step targets and anchors
snapshot age
```

Use this during acceptance testing. Later it can be moved behind an Advanced/Debug expander.

---

## Required custom cards

Common required cards:

```text
custom:button-card
custom:mushroom-entity-card
custom:vertical-stack-in-card
```

The RAW timeline only needs:

```text
custom:button-card
```

---

## Rule

```text
Python decides.
Dashboard displays.
```
