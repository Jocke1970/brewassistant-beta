# Fermentation Process Cleanup Plan

This plan tracks the cleanup of legacy Fermentation Process entities and dashboard drift.

Related issue:

```text
#27 Clean up Fermentation Process legacy entities and mixed UI language
```

---

## Problems observed

```text
[x] Mixed Swedish and English UI text in Fermentation Process card
[x] Batch age appears incorrect
[x] Duplicate batch start helpers/entities exist
[x] Multiple SG last-updated sensors exist
[x] Some last-updated sensors are restored/ghost/unavailable entities
[x] Legacy _2 automation references missing script.brew_batch_start
```

---

## Canonical direction

Batch start source:

```text
input_datetime.brew_batch_started_at
```

Python Core batch age sensors:

```text
sensor.brewassistant_batch_started_at
sensor.brewassistant_batch_age_hours
sensor.brewassistant_batch_age_days
```

SG/gravity source:

```text
sensor.brewassistant_gravity
```

SG/gravity last updated source:

```text
sensor.brewassistant_gravity_last_updated
```

The `gravity_last_updated` value comes from the configured gravity source entity in Python Core, not from multiple YAML timestamp helper/template sensors.

Verified gravity example:

```text
Gravity: 1.004
Gravity last updated: 2026-05-19T18:52:12.481540+00:00
Source entity: sensor.yellow_pill_gravity
Source state: 1.0041
Source last updated ISO: 2026-05-19T18:52:12.481540+00:00
```

Verified batch age example:

```text
Batch started: 2026-05-02T15:00:00+00:00
Batch age hours: 412.7
Batch age days: 17.2
Source entity: input_datetime.brew_batch_started_at
Source state: 2026-05-02 17:00:00
Started at ISO: 2026-05-02T15:00:00+00:00
```

---

## Patch order

### 1. Python Core gravity timestamp

```text
[x] Add sensor.brewassistant_gravity_last_updated
[x] Add attributes: source_entity, source_state, source_last_updated_iso
[ ] Add EN/SV translations
[x] Test after HA restart
```

### 2. Batch age cleanup

```text
[x] Decide canonical batch start helper
[x] Add Python/Core batch age days/hours or fix YAML source
[ ] Add EN/SV translations
[ ] Update Fermentation Process card to canonical source
```

### 3. Fermentation Process card cleanup

```text
[ ] Standardize UI language
[ ] Replace legacy fwk/brew timestamp sensors with Python Core values
[ ] Remove references to ghost/restored entities
[ ] Keep active process logic stable during migration
```

### 4. Legacy entity quarantine

```text
[ ] Keep _2 / ghost entities disabled for a few days
[ ] Confirm post-restart sanity checks remain green
[ ] Delete only after no dashboard/package references remain
```

---

## Test template after gravity_last_updated patch

```jinja
# BrewAssistant gravity timestamp check

Gravity:
{{ states('sensor.brewassistant_gravity') }}

Gravity last updated:
{{ states('sensor.brewassistant_gravity_last_updated') }}

Source entity:
{{ state_attr('sensor.brewassistant_gravity_last_updated', 'source_entity') }}

Source state:
{{ state_attr('sensor.brewassistant_gravity_last_updated', 'source_state') }}

Source last updated ISO:
{{ state_attr('sensor.brewassistant_gravity_last_updated', 'source_last_updated_iso') }}
```

---

## Test template after batch age patch

```jinja
# BrewAssistant batch age check

Batch started:
{{ states('sensor.brewassistant_batch_started_at') }}

Batch age hours:
{{ states('sensor.brewassistant_batch_age_hours') }}

Batch age days:
{{ states('sensor.brewassistant_batch_age_days') }}

Source entity:
{{ state_attr('sensor.brewassistant_batch_age_days', 'source_entity') }}

Source state:
{{ state_attr('sensor.brewassistant_batch_age_days', 'source_state') }}

Started at ISO:
{{ state_attr('sensor.brewassistant_batch_age_days', 'started_at_iso') }}
```

---

## Safety notes

This cleanup should remain read-only.

Do not delete legacy entities immediately after disabling them. Use disable -> restart -> observe -> delete later.
