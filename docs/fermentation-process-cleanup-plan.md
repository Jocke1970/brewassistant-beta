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

SG/gravity source:

```text
sensor.brewassistant_gravity
```

SG/gravity last updated source:

```text
sensor.brewassistant_gravity_last_updated
```

The `gravity_last_updated` value should come from the configured gravity source entity in Python Core, not from multiple YAML timestamp helper/template sensors.

---

## Patch order

### 1. Python Core gravity timestamp

```text
[ ] Add sensor.brewassistant_gravity_last_updated
[ ] Add attributes: source_entity, source_state, source_last_updated_iso
[ ] Add EN/SV translations
[ ] Test after HA restart
```

### 2. Batch age cleanup

```text
[ ] Decide canonical batch start helper
[ ] Add Python/Core batch age days/hours or fix YAML source
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

## Safety notes

This cleanup should remain read-only.

Do not delete legacy entities immediately after disabling them. Use disable -> restart -> observe -> delete later.
