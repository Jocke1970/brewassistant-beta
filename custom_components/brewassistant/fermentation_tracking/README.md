# Fermentation tracking backend

Status: active development  
Code snapshot documented: 2026-09-11

`fermentation_tracking` is BrewAssistant's independent fermentation observation, calculation and **recipe temperature-schedule** backend. It normalizes gravity and beer-temperature observations, supports manual and automatic sources independently, persists manual observations/runtime state, derives progress/stability/readiness information, and interprets fermentation steps from read-only recipe data.

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
- persist runtime configuration and recorded manual observations;
- consume read-only recipe payloads from adapters such as Brewfather/BrewTracker;
- interpret recipe fermentation steps and ramps into BrewAssistant's current recommended beer-temperature target.

## Adapter boundary

Brewfather is a **data source**, not the owner of BrewAssistant fermentation logic.

The current Brewfather fork exposes the active BrewTracker batch's full recipe on the BrewTracker raw sensor:

```text
sensor.brewfather_brew_tracker_raw
  attribute: recipe
```

BrewAssistant then owns this chain:

```text
Brewfather recipe payload
        ↓
fermentation_tracking/recipe_schedule.py
        ↓
recommended_temperature_c
        ↓
fermentation_chamber
        ↓
optional supervised climate application
```

The Brewfather adapter must not calculate or publish BrewAssistant-specific ramp targets. This keeps the same fermentation backend reusable with future recipe sources.

## Recipe temperature schedule

For Brewfather recipe data, the schedule currently consumes:

```text
recipe.fermentation.steps[].actualTime
recipe.fermentation.steps[].stepTemp
recipe.fermentation.steps[].ramp
```

`ramp` is interpreted as days. BrewAssistant aligns the first recipe fermentation step with the actual Brewfather fermentation-start sensor when available, then preserves the relative recipe timing for later steps.

During an active ramp, the recommended target is linearly interpolated between the previous step temperature and the target step temperature. Both rising and falling ramps are supported.

The normalized snapshot exposes ramp diagnostics such as:

```text
temperature_schedule_ramp_active
temperature_schedule_ramp_start_temperature_c
temperature_schedule_ramp_target_temperature_c
temperature_schedule_ramp_days
temperature_schedule_ramp_started_at
temperature_schedule_ramp_ends_at
temperature_schedule_ramp_progress_percent
```

If no usable recipe schedule is available, the existing BrewAssistant tracking rule remains the fallback: primary target until the configured SG rise trigger is reached, then the configured temperature-rise target.

## Persistence

Home Assistant Storage key:

```text
brewassistant_fermentation_runtime
```

The runtime is loaded by `async_setup_fermentation_runtime()` and saved after start/update/record/reset service operations.

A stored observation can include metric/timestamp, source type/entity, method, raw value/unit, normalized value/unit, note and refractometer correction metadata.

## Independent source policy

Gravity and temperature each have their own source mode:

```text
manual
automatic
hybrid
```

This allows combinations such as manual refractometer SG + automatic beer temperature, or automatic gravity + manual temperature.

In hybrid mode, the newest valid source wins independently for the metric. A manual observation wins an exact timestamp tie.

## Runtime services

```text
brewassistant.fermentation_start
brewassistant.fermentation_update
brewassistant.fermentation_record_observation
brewassistant.fermentation_record_gravity
brewassistant.fermentation_reset
```

Start creates a fresh session. Update validates changes atomically on a copy and recalculates dependent refractometer observations before replacing live state.

## Derived calculations

### Fermentation progress

```text
(OG - current SG) / (OG - target FG) * 100
```

### Estimated ABV

```text
(OG - current SG) * 131.25
```

### Temperature-rise readiness

Ready when tracking is active and normalized current SG reaches the configured trigger.

### Gravity stability

Uses persisted gravity observations over the configured stable period and tolerance.

### Cold-crash readiness

Requires both stable gravity and proximity to target FG within the configured tolerance.

## Automatic-source limitation

Configured automatic SG and temperature entities can supply the live current values. Automatic-only sensor history is not automatically copied into BrewAssistant Storage today, so stable-FG history is strongest when persisted observations exist.

## Important files

| File | Purpose |
| --- | --- |
| `models.py` | Runtime/observation data models and source-mode constants |
| `storage.py` | Home Assistant Storage serialization/access |
| `runtime.py` | Lifecycle, validation and service registration |
| `observations.py` | Manual observation normalization/recording |
| `recalculation.py` | Recompute refractometer-derived values after config changes |
| `calculations.py` | SG/Brix/ABV and validation helpers |
| `recipe_schedule.py` | Pure recipe fermentation-step/ramp interpretation |
| `snapshot.py` | Source resolution and normalized fermentation state |
| `sensor.py` | Home Assistant read-only sensor presentation and adapter lookup |

## Do not change casually

1. Gravity and temperature source policies are independent by design.
2. Refractometer displayed SG is not hydrometer SG during fermentation.
3. Raw observation data should remain auditable after normalization.
4. Recipe adapters expose data; BrewAssistant owns schedule interpretation.
5. Tracking recommends readiness/temperature changes but does not actuate chamber hardware.
6. Storage changes require migration/backward-compatibility consideration.
7. Do not infer stable FG from a live automatic value without sufficient history evidence.
