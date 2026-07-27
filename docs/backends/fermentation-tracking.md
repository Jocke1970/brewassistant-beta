# Fermentation Tracking MVP

## Purpose

The fermentation tracking backend is Python-owned and independent of RAPT Pill.
It treats a manually recorded gravity observation as a first-class source, stores
observations in Home Assistant Storage, and exposes one normalized current SG to
downstream BrewAssistant logic.

The existing fermentation climate code remains separate. This MVP recommends
process transitions but does not change climate targets or start cold crash.

## Runtime and storage

Storage key:

```text
brewassistant_fermentation_runtime
```

Each stored gravity sample contains:

- observation timestamp
- measurement type
- raw value
- corrected SG
- source
- optional note
- wort correction factor when relevant

The latest valid observation becomes `current_sg`. A configured external gravity
entity can participate as another source. When timestamps are equal, a manual
observation wins.

## Supported manual observations

```text
refractometer_brix
hydrometer_sg
manual_sg
```

For a refractometer observation, BrewAssistant stores the raw Brix reading and
calculates corrected SG from recipe OG, measured Brix, and the configured wort
correction factor. The default correction factor is `1.04`.

Hydrometer and generic manual SG observations use the submitted SG directly as
the corrected/current SG.

## Services

### Start tracking

```yaml
service: brewassistant.fermentation_start
data:
  recipe_name: American Lite Ale
  original_gravity: 1.044
  target_final_gravity: 1.011
  temp_rise_trigger_sg: 1.016
  primary_temperature_c: 18
  temp_rise_temperature_c: 20
  stable_hours: 48
  stability_tolerance_sg: 0.001
  fg_tolerance_sg: 0.002
  wort_correction_factor: 1.04
```

Starting a new runtime clears previous gravity samples.

### Record daily refractometer reading

```yaml
service: brewassistant.fermentation_record_gravity
data:
  measurement_type: refractometer_brix
  value: 6.0
  note: Daily Oxebar sample
```

### Record hydrometer SG

```yaml
service: brewassistant.fermentation_record_gravity
data:
  measurement_type: hydrometer_sg
  value: 1.011
```

### Adjust thresholds without clearing samples

```yaml
service: brewassistant.fermentation_update
data:
  stable_hours: 48
  stability_tolerance_sg: 0.001
```

### Reset

```yaml
service: brewassistant.fermentation_reset
```

## Normalized outputs

The existing entity below now resolves the normalized current/corrected SG
regardless of source:

```text
sensor.brewassistant_gravity
```

MVP tracking sensors:

```text
sensor.brewassistant_fermentation_tracking_status
sensor.brewassistant_fermentation_gravity_source
sensor.brewassistant_fermentation_progress_percent
sensor.brewassistant_fermentation_estimated_abv
sensor.brewassistant_fermentation_gravity_stability
sensor.brewassistant_fermentation_ready_for_temp_rise
sensor.brewassistant_fermentation_ready_for_cold_crash
sensor.brewassistant_fermentation_sample_count
sensor.brewassistant_fermentation_last_observation
sensor.brewassistant_fermentation_recommended_temperature
sensor.brewassistant_fermentation_tracking_summary
```

Each tracking sensor exposes the complete current snapshot as attributes,
including the ten most recent stored samples.

## Detection rules

### Fermentation progress

```text
(OG - current SG) / (OG - target FG) × 100
```

The displayed result is clamped to 0–100%.

### Estimated ABV

```text
(OG - current SG) × 131.25
```

This is a live estimate until final gravity is confirmed.

### Ready for temperature rise

True when the runtime is active and normalized current SG is at or below the
configured trigger SG.

For the American Lite Ale test case:

```text
current SG <= 1.016
```

The backend then recommends `20 °C`; it does not apply that target.

### Stable FG

Stable FG requires at least two stored manual samples whose observation window
spans the configured minimum time and whose SG range stays inside the configured
tolerance.

Default MVP rule:

```text
window >= 48 h
max SG - min SG <= 0.001
```

External live sensor points are allowed as the current SG source, but stable-FG
detection is deliberately based on persisted manual samples in this MVP. That
makes the daily measurement workflow deterministic and auditable.

### Ready for cold crash

True only when all conditions are met:

- runtime is active
- gravity is stable for the configured period
- current SG is no more than the configured tolerance above target FG

American Lite Ale defaults:

```text
target FG: 1.011
FG tolerance: 0.002
eligible SG: <= 1.013
stable period: >= 48 h
```

This extra target-FG gate prevents a stalled fermentation at a much higher SG
from being marked ready merely because the reading stopped changing.

## MVP boundaries

Included:

- Python-owned runtime
- HA Storage samples
- manual Brix and SG observations
- external gravity source compatibility
- canonical current/corrected SG
- progress, ABV and readiness calculations
- service surface for a later daily-input dashboard card

Not included yet:

- automatic climate target changes
- automatic cold-crash start
- a large fermentation dashboard
- automatic import of OG/FG from every recipe provider
- sample editing/deletion UI
