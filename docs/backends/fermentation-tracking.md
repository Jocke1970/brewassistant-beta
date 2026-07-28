# Fermentation Tracking MVP

## Architecture

BrewAssistant now separates two concerns:

```text
fermentation_tracking
  process observations, SG/Brix correction, beer temperature,
  progress, ABV, stability and readiness

fermentation_chamber
  chamber-air recommendations and supervised climate control
```

`fermentation_tracking` does not require RAPT Pill, a fermentation chamber, or any automatic sensor. It can run entirely from manual SG and temperature observations.

The chamber backend consumes normalized tracking outputs when available, but tracking never switches a heater, cooler, fan, or climate entity itself.

Legacy files under `custom_components/brewassistant/fermentation/` are compatibility bridges only.

## Runtime and storage

Storage key:

```text
brewassistant_fermentation_runtime
```

A stored observation includes:

- metric: gravity or temperature
- observation timestamp
- source type: manual or automatic
- source and optional source entity
- instrument/method
- raw value and raw unit
- normalized value and unit
- optional note
- wort correction factor and calculation Brix when relevant

Recipe metadata is optional. OG and target FG are only required for calculations that need them. A fermented refractometer observation requires OG because alcohol correction cannot be calculated safely without it.

## Independent source policies

Gravity and beer temperature have separate policies:

```text
manual
automatic
hybrid
```

Example:

```yaml
service: brewassistant.fermentation_start
data:
  recipe_name: American Lite Ale
  original_gravity: 1.044
  target_final_gravity: 1.011
  temp_rise_trigger_sg: 1.016
  primary_temperature_c: 18
  temp_rise_temperature_c: 20
  gravity_source_mode: manual
  temperature_source_mode: automatic
```

In `hybrid`, the newest valid source wins independently for each metric. A manual observation wins an exact timestamp tie.

This allows combinations such as:

- manual refractometer SG + automatic beer temperature
- automatic SG + manual temperature
- manual SG + manual temperature
- automatic SG + automatic temperature

## Manual observation service

Use one shared service for gravity, temperature, or both:

```text
brewassistant.fermentation_record_observation
```

Instrument and displayed unit are separate fields. This prevents a refractometer SG scale from being treated as hydrometer SG.

### Refractometer showing Brix

```yaml
service: brewassistant.fermentation_record_observation
data:
  gravity_instrument: refractometer
  gravity_unit: brix
  gravity_value: 6.2
  temperature_c: 18.4
  note: Daily Oxebar sample
```

### Refractometer showing SG

```yaml
service: brewassistant.fermentation_record_observation
data:
  gravity_instrument: refractometer
  gravity_unit: sg
  gravity_value: 1.024
  temperature_c: 18.4
```

The displayed SG is first converted to its Brix-equivalent optical reading and is then alcohol-corrected with batch OG and the configured wort correction factor. It is never accepted as hydrometer SG.

### Hydrometer SG

```yaml
service: brewassistant.fermentation_record_observation
data:
  gravity_instrument: hydrometer
  gravity_unit: sg
  gravity_value: 1.011
  temperature_c: 20.0
```

### Temperature only

```yaml
service: brewassistant.fermentation_record_observation
data:
  temperature_c: 18.6
  note: No gravity sample today
```

### Method shortcuts

A dashboard may use one shortcut instead of separate instrument and unit fields:

```text
refractometer_brix
refractometer_sg
hydrometer_sg
manual_sg
```

Example:

```yaml
service: brewassistant.fermentation_record_observation
data:
  gravity_method: refractometer_sg
  gravity_value: 1.024
```

The former `brewassistant.fermentation_record_gravity` service remains as a compatibility alias.

## Validation guardrails

The backend rejects ambiguous or implausible combinations, including:

- refractometer reading without OG during fermentation tracking
- hydrometer with Brix as the selected unit
- Brix outside 0–40
- SG outside 0.900–1.200
- temperature outside -5–50 °C
- OG at or below target FG
- temperature-rise trigger outside the configured OG–FG range
- unknown source policy

Both the raw reading and normalized result remain visible in sensor attributes.

## Normalized outputs

Primary tracking sensors include:

```text
sensor.brewassistant_fermentation_tracking_status
sensor.brewassistant_fermentation_current_sg
sensor.brewassistant_fermentation_gravity_source
sensor.brewassistant_fermentation_gravity_source_type
sensor.brewassistant_fermentation_gravity_source_mode
sensor.brewassistant_fermentation_current_temperature
sensor.brewassistant_fermentation_temperature_source
sensor.brewassistant_fermentation_temperature_source_type
sensor.brewassistant_fermentation_temperature_source_mode
sensor.brewassistant_fermentation_progress_percent
sensor.brewassistant_fermentation_estimated_abv
sensor.brewassistant_fermentation_gravity_stability
sensor.brewassistant_fermentation_ready_for_temp_rise
sensor.brewassistant_fermentation_ready_for_cold_crash
sensor.brewassistant_fermentation_sample_count
sensor.brewassistant_fermentation_temperature_observation_count
sensor.brewassistant_fermentation_recommended_temperature
sensor.brewassistant_fermentation_tracking_summary
```

Each tracking sensor exposes the complete normalized snapshot as attributes, including raw reading metadata and recent persisted observations.

## Detection rules

### Progress

```text
(OG - current SG) / (OG - target FG) × 100
```

The result is clamped to 0–100%. It is unavailable until OG, target FG, and current SG exist.

### Estimated ABV

```text
(OG - current SG) × 131.25
```

This is a live estimate until FG is confirmed.

### Temperature rise

Ready when tracking is active and normalized current SG is at or below the configured trigger.

American Lite Ale example:

```text
current SG <= 1.016
recommended temperature: 20 °C
```

Tracking recommends the process change but does not apply it directly.

### Stable FG

Stable FG uses persisted gravity observations:

```text
observation span >= 48 h
max SG - min SG <= 0.001
```

At least two observations are required. The current MVP persists manual observations. A configured automatic SG entity can supply live `current_sg`, but its history is not automatically copied into BrewAssistant Storage yet. Therefore automatic-only stable-FG detection is a known follow-up, not a silent assumption.

### Cold-crash readiness

All conditions must be true:

- tracking is active
- persisted gravity observations are stable for the configured period
- current SG is no more than the configured tolerance above target FG

American Lite Ale defaults:

```text
target FG: 1.011
FG tolerance: 0.002
eligible SG: <= 1.013
stable period: >= 48 h
```

This target-FG gate prevents a stalled fermentation at a much higher SG from being marked ready merely because it stopped changing.

## MVP boundaries

Included:

- separate tracking and chamber packages
- recipe-independent runtime
- manual or automatic source resolution per metric
- manual Brix, refractometer-SG, hydrometer-SG, generic SG, and temperature observations
- HA Storage persistence for manual observations
- normalized current SG and beer temperature
- progress, ABV, stability, and readiness calculations
- backward-compatible imports and gravity service

Not included yet:

- automatic persistence of every external SG sensor update
- automatic climate target changes without the existing supervised chamber policy
- automatic cold-crash start
- observation edit/delete UI
- large dashboard redesign
- automatic OG/FG import from every recipe provider
