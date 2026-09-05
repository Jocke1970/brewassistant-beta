# Fermentation chamber backend

Status: active recommendation + supervised control backend  
Code snapshot documented: 2026-09-05

`fermentation_chamber` converts normalized fermentation tracking data into a recommended chamber-air target and, when enabled, bridges that recommendation into BrewAssistant's generic Supervised Apply flow for `climate.fermentation_chamber`.

It is intentionally separate from [`../fermentation_tracking/`](../fermentation_tracking/). Tracking owns the beer/process observations; chamber control consumes them.

## Responsibilities

- determine whether fermentation/cold-crash chamber scope is active;
- resolve normalized liquid temperature and fermentation temperature target;
- observe chamber-air temperature and air/liquid delta;
- recommend an effective chamber-air target;
- clamp recommendations to mode-specific safe/plausible ranges;
- expose demand/reason/diagnostics as read-only sensors;
- create a pending supervised climate target action when enabled and needed.

It does not directly own fermentation SG calculations, fermentation lifecycle observations, compressor timing or raw heat/cool switching.

## Input priority

Liquid temperature is taken from the normalized `fermentation_tracking` snapshot first. A legacy rolling liquid-temperature average is only a fallback.

Fermentation target uses the tracking backend's recommended temperature when available. Older coordinator/recipe target context remains a fallback.

Chamber temperature is read from the rolling chamber average when available, then coordinator data.

This order is deliberate: the chamber backend should consume normalized tracking output rather than recreate source-selection policy.

## Modes

Current modes:

```text
standby
fermentation
cold_crash
```

A test-mode select can force fermentation or cold-crash context for controlled validation.

## Recommendation model

The recommendation adjusts chamber air around the desired liquid temperature according to liquid delta, with extra damping when a valid liquid trend exists.

Mode-specific clamps:

```text
fermentation air target: 7.0–35.0 °C
cold-crash air target:    0.5–8.0 °C
```

The snapshot exposes both raw and clamped target plus `clamp_applied`/`clamp_reason` so a dashboard or test can see when the guard changed the recommendation.

The air-target layer is explicitly `control: read_only`.

## Sensor surface

The chamber recommendation package creates sensors including:

```text
sensor.brewassistant_fermentation_effective_air_target
sensor.brewassistant_fermentation_climate_demand
sensor.brewassistant_fermentation_climate_mode
sensor.brewassistant_fermentation_air_target_reason
sensor.brewassistant_fermentation_liquid_delta
sensor.brewassistant_fermentation_air_liquid_delta
sensor.brewassistant_fermentation_air_target_summary
```

All carry the broader normalized snapshot as attributes for diagnostics.

## Supervisor

`supervisor.py` compares the recommended air target with the current target of:

```text
climate.fermentation_chamber
```

Current evaluation interval is 30 seconds and the target-change epsilon is 0.05 °C.

The supervisor only proposes control when:

```text
supervisor enabled
scope active
recommendation ready
climate entity available
target change needed
```

## Supervised Apply boundary

The fermentation chamber supervisor does **not** directly call `climate.set_temperature` from its normal evaluation path.

When generic Supervised Apply is enabled and a target change is needed, it creates a pending action with:

```text
source: fermentation_chamber_supervisor
kind: climate_set_temperature
entity: climate.fermentation_chamber
service: climate.set_temperature
recommended target + diagnostic context
```

The snapshot then reports `pending_confirmation`.

If Supervised Apply is not enabled, the supervisor remains `monitor_only` rather than silently switching to direct control.

Pending actions are cleared when the backend leaves scope, loses readiness or reaches/holds the desired target.

## Runtime state

Supervisor enable/last-evaluation state is currently held in `hass.data["brewassistant"]`. The recommendation itself is recalculated from current tracking/coordinator state.

## Relationship to legacy package

`../fermentation/` contains compatibility registration/import bridges only. New chamber-control logic belongs here.

## Do not change casually

1. Tracking source selection belongs to `fermentation_tracking`, not this package.
2. The air-target calculation is recommendation/read-only logic.
3. Normal chamber target writes must remain behind the generic Supervised Apply boundary unless the architecture is explicitly changed.
4. A missing/untrusted liquid temperature or target must not produce an invented control target.
5. Keep fermentation and cold-crash target clamps explicit and diagnosable.
