# Carbonation backend

Status: active guidance/runtime backend  
Code snapshot documented: 2026-09-05

`carbonation_backend` owns BrewAssistant's Python carbonation session state and carbonation calculations. It tracks a carbonation session, resolves temperature/pressure inputs, recommends equilibrium pressure and estimates carbonation progress.

It does **not** control a CO₂ regulator, gas valve, kegerator compressor or climate entity.

## Runtime ownership and persistence

`carbonation_runtime.py` owns a mutable `CarbonationRuntime` with:

```text
active
method
target_volumes
start_volumes
pressure_bar
temperature_c
started_at
updated_at
```

The runtime is persisted through Home Assistant Storage:

```text
storage key: brewassistant_carbonation_runtime
storage version: 1
```

It is loaded during BrewAssistant integration startup and saved after service-driven changes.

## Defaults

```text
method: Set-and-forget
target volumes: 2.40 vol
start volumes: 0.85 vol
```

Known timing models used for the current progress estimate:

| Method | Modelled time to full |
| --- | ---: |
| Burst carbonation | 2 days |
| Set-and-forget | 14 days |
| Natural carbonation | 21 days |
| Conditioning | 14 days |

These are estimation inputs, not physical guarantees.

## Input resolution

### Pressure

Current actual pressure comes only from the Python runtime input (`pressure_bar`). A physical pressure sensor is not automatically adopted by this backend today.

### Temperature

Temperature is resolved in this order:

```text
runtime temperature override
  -> configured kegerator air-temperature entity
  -> sensor.brewassistant_liquid_temperature
  -> unavailable
```

The selected source is exposed in snapshot attributes.

## Calculations

The backend calculates:

- recommended pressure in PSI and bar for target CO₂ volumes at current temperature;
- equilibrium CO₂ volumes for an entered actual pressure/temperature;
- estimated current volumes from elapsed session age and the selected method model;
- progress from configured start volumes toward target volumes.

Status currently progresses through:

```text
Inactive
Carbonating
Conditioning        (estimated progress >= 75%)
Ready to serve      (estimated progress >= 95%)
```

The snapshot is explicitly marked `mode: read_only` because the calculation result is guidance, not automatic gas control.

## Public services

The integration root exposes:

```text
brewassistant.carbonation_start
brewassistant.carbonation_update
brewassistant.carbonation_pause
brewassistant.carbonation_reset
```

Start/update can set method, target/start volumes, pressure, temperature and timestamps through the service surface defined in `services.yaml`.

## Main sensor surface

The root sensor platform exposes the carbonation snapshot through entities including:

```text
sensor.brewassistant_carbonation_status
sensor.brewassistant_carbonation_method
sensor.brewassistant_carbonation_target_volumes
sensor.brewassistant_carbonation_temperature
sensor.brewassistant_carbonation_recommended_pressure_bar
sensor.brewassistant_carbonation_recommended_pressure_psi
sensor.brewassistant_carbonation_actual_pressure_bar
sensor.brewassistant_carbonation_actual_pressure_psi
sensor.brewassistant_carbonation_equilibrium_volumes
sensor.brewassistant_carbonation_estimated_volumes
sensor.brewassistant_carbonation_progress_percent
sensor.brewassistant_carbonation_started_at
sensor.brewassistant_carbonation_age_days
sensor.brewassistant_carbonation_summary
```

## Relationship to other backends

`carbonation_backend` can supply context to:

- [`../climate_backend/`](../climate_backend/) — determines whether carbonation/serving climate supervision is in scope;
- [`../kegerator/`](../kegerator/) — serving/guard diagnostics may read carbonation status/temperature.

Those consumers do not transfer compressor or climate ownership into this backend.

## Do not change casually

1. Carbonation guidance must remain separate from gas actuation unless a new explicit actuator/safety design is introduced.
2. Persisted runtime state must remain backward-compatible or receive a storage migration.
3. Temperature source fallback must remain visible in diagnostics; do not silently pretend kegerator air is measured beer temperature.
4. Progress is an estimate based on elapsed time/modelled equilibrium, not a direct measurement of dissolved CO₂.
