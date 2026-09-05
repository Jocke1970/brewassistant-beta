# Fermentation tracking backend

Status: active MVP  
Code snapshot documented: 2026-09-05

`fermentation_tracking` is BrewAssistant's independent fermentation observation and calculation backend. It normalizes gravity and beer-temperature observations, supports manual and automatic sources independently, persists manual observations/runtime state, and derives progress/stability/readiness information.

It does **not** control a fermentation chamber, heater, cooler or fan. Chamber recommendations/control belong in [`../fermentation_chamber/`](../fermentation_chamber/).

## Responsibilities

- own fermentation tracking session configuration and lifecycle;
- accept manual gravity and/or temperature observations;
- consume configured automatic SG and liquid-temperature entities;
- resolve gravity and temperature source policy independently;
- normalize hydrometer SG and refractometer Brix/SG correctly;
- retain raw observation metadata alongside normalized values;
- calculate fermentation progress and estimated ABV;
- calculate gravity stability and readiness for temperature rise/cold crash;
- persist runtime configuration and recorded manual observations.

## Persistence

Home Assistant Storage key:

```text
brewassistant_fermentation_runtime
```

The runtime is loaded by `async_setup_fermentation_runtime()` and saved after start/update/record/reset service operations.

A stored observation can include:

```text
metric + observed timestamp
manual/automatic source type
source/source entity
instrument/method
raw value and unit
normalized value and unit
note
wort correction / calculation Brix metadata when relevant
```

## Independent source policy

Gravity and temperature each have their own source mode:

```text
manual
automatic
hybrid
```

This allows combinations such as manual refractometer SG + automatic beer temperature, or automatic gravity + manual temperature.

In hybrid mode, the newest valid source wins independently for the metric. A manual observation wins an exact timestamp tie.

## Manual observation service

Canonical service:

```text
brewassistant.fermentation_record_observation
```

One call may contain gravity, temperature or both.

Supported gravity concepts include:

- refractometer Brix;
- refractometer displayed SG (converted back to optical/Brix-equivalent before alcohol correction);
- hydrometer SG;
- generic/manual SG compatibility input.

The legacy service remains as an alias:

```text
brewassistant.fermentation_record_gravity
```

## Runtime services

```text
brewassistant.fermentation_start
brewassistant.fermentation_update
brewassistant.fermentation_record_observation
brewassistant.fermentation_record_gravity
brewassistant.fermentation_reset
```

Start creates a fresh session. Update validates changes atomically on a copy and recalculates dependent refractometer observations before replacing live state.

## Validation boundaries

The runtime rejects ambiguous or implausible configuration/readings, including:

- invalid SG/Brix/temperature ranges;
- OG <= target FG;
- temperature-rise trigger outside OG-to-FG range;
- unknown source mode;
- hydrometer+Brix combinations;
- fermented refractometer correction when required OG context is missing.

Current configurable limits include stable hours, stability tolerance, FG tolerance and wort correction factor.

## Derived calculations

### Fermentation progress

```text
(OG - current SG) / (OG - target FG) * 100
```

Clamped to 0–100% when required inputs exist.

### Estimated ABV

```text
(OG - current SG) * 131.25
```

This remains an estimate until final gravity is accepted/confirmed.

### Temperature-rise readiness

Ready when tracking is active and normalized current SG reaches the configured trigger.

### Gravity stability

Uses persisted gravity observations over the configured stable period and tolerance. The existing MVP default documented behavior is a 48-hour span with max-min SG <= 0.001 unless runtime settings change it.

### Cold-crash readiness

Requires both stable gravity and proximity to target FG within the configured tolerance, preventing a stalled but high-SG fermentation from becoming ready only because it stopped changing.

## Automatic-source limitation

Configured automatic SG and temperature entities can supply the live current values. Automatic-only sensor history is not automatically copied into BrewAssistant Storage today, so stable-FG history is strongest when persisted observations exist. Do not imply that every external sensor update becomes a stored BrewAssistant observation.

## Sensor surface

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
```

Additional last-observation/recommended-temperature/summary sensors are registered by `sensor.py` in this package.

## Important files

| File | Purpose |
| --- | --- |
| `models.py` | Runtime/observation data models and source-mode constants |
| `storage.py` | Home Assistant Storage serialization/access |
| `runtime.py` | Lifecycle, validation and service registration |
| `observations.py` | Manual observation normalization/recording |
| `recalculation.py` | Recompute refractometer-derived values after config changes |
| `calculations.py` | SG/Brix/ABV and validation helpers |
| `snapshot.py` | Source resolution and derived fermentation state |
| `sensor.py` | Home Assistant read-only sensor presentation |

## Do not change casually

1. Gravity and temperature source policies are independent by design.
2. Refractometer displayed SG is not hydrometer SG during fermentation.
3. Raw observation data should remain auditable after normalization.
4. Tracking recommends readiness/temperature changes but does not actuate chamber hardware.
5. Storage changes require migration/backward-compatibility consideration.
6. Do not infer stable FG from a live automatic value without sufficient history evidence.
