# Fermentation chamber backend

Status: active recommendation + supervised physical-provider backend  
Code/documentation snapshot: 2026-09-11

`fermentation_chamber` is BrewAssistant's currently implemented fermentation temperature-control provider. It converts normalized fermentation tracking data and the desired liquid/beer temperature into a recommended chamber-air target and, when enabled, bridges that recommendation into BrewAssistant's generic Supervised Apply flow for `climate.fermentation_chamber`.

It is intentionally separate from [`../fermentation_tracking/`](../fermentation_tracking/). Tracking owns the beer/process observations and strategy signals; chamber control consumes them and translates the desired beer target into a target understood by the physical chamber controller.

The generic provider ownership model is documented in [`../../../docs/backends/fermentation-control.md`](../../../docs/backends/fermentation-control.md).

## Responsibilities

- act as the physical fermentation-control provider for the current chamber;
- determine whether fermentation/cold-crash chamber scope is active;
- resolve normalized liquid temperature and fermentation temperature target;
- observe chamber-air temperature and air/liquid delta;
- translate the desired beer/liquid target into an effective chamber-air target;
- clamp recommendations to mode-specific safe/plausible ranges;
- expose demand/reason/diagnostics as read-only sensors;
- create a pending supervised climate target action when enabled and needed.

It does not directly own fermentation SG calculations, fermentation lifecycle observations, compressor timing or raw heat/cool switching.

The downstream Home Assistant climate controller owns actual heater/cooler regulation once its target has been set.

## Input priority

Liquid temperature is taken from the normalized `fermentation_tracking` snapshot first. A legacy rolling liquid-temperature average is only a fallback.

Fermentation target uses the tracking backend's recommended temperature when available. Older coordinator/recipe target context remains a fallback.

Chamber temperature is read from the rolling chamber average when available, then coordinator data.

This order is deliberate: the chamber backend should consume normalized tracking output rather than recreate source-selection policy.

## Provider-contract role

The chamber backend is an implementation of the generic fermentation control provider contract:

```text
fermentation_tracking
  recommended beer/liquid target
        |
        v
fermentation_chamber
  translate to chamber-air target
        |
        v
Supervised Apply
        |
        v
climate.fermentation_chamber
        |
        v
local climate controller
  owns heat/cool cycling
```

BrewAssistant therefore does not need to act as a second thermostat. The provider owns setpoint translation; the downstream climate controller owns actuator-level hysteresis, switching and local safety behavior.

When another writable provider such as a future Grainfather fermenter is added, only the explicitly selected physical provider may create target-write actions for a fermentation session.

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

The air-target calculation layer is explicitly `control: read_only`. Applying its result is a separate supervised provider action.

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

`supervisor.py` compares the translated chamber-air target with the current target of:

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

Confirming the target write delegates subsequent heat/cool regulation to `climate.fermentation_chamber`; BrewAssistant does not take over the controller's raw heating/cooling outputs.

## Runtime state

Supervisor enable/last-evaluation state is currently held in `hass.data["brewassistant"]`. The recommendation itself is recalculated from current tracking/coordinator state.

## Relationship to legacy package

`../fermentation/` contains compatibility registration/import bridges only. New chamber-control logic belongs here.

The conceptual phrase "fermentation control" does not make the legacy `fermentation/` package the owner of provider logic.

## Do not change casually

1. Tracking source selection belongs to `fermentation_tracking`, not this package.
2. The air-target calculation is recommendation/read-only logic; applying it is a separate provider action.
3. Normal chamber target writes must remain behind the generic Supervised Apply boundary unless the architecture is explicitly changed.
4. A missing/untrusted liquid temperature or target must not produce an invented control target.
5. Keep fermentation and cold-crash target clamps explicit and diagnosable.
6. The downstream climate controller owns raw heat/cool switching; do not duplicate its thermostat behavior in BrewAssistant.
7. Before a second writable fermentation provider is enabled, explicit single-provider authority/selection must prevent competing target writes.
