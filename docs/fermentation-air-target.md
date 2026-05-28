# Fermentation Air Target Engine

The Fermentation Air Target Engine is a read-only recommendation layer for future fermentation and cold-crash climate supervision.

It does not control any climate entity and does not switch hardware.

---

## Purpose

Fermentation and cold-crash temperature control should target liquid temperature, not chamber air temperature.

```text
Fermentation / cold crash:
liquid target = process goal
chamber air target = tool
```

The air target engine calculates a recommended chamber-air target from liquid temperature, process target and scope state.

---

## Architecture

```text
BrewAssistant process scope
+ real liquid temperature
+ rolling liquid/chamber stats
+ recipe/cold-crash target
        ↓
Fermentation Air Target Engine
        ↓
read-only sensors
        ↓
dashboard / future supervisor
```

No hardware is controlled by this engine.

---

## Current modules

```text
custom_components/brewassistant/fermentation_air_target.py
custom_components/brewassistant/select.py
```

Sensors are registered through:

```text
custom_components/brewassistant/sensor.py
```

---

## Current sensors

```text
sensor.brewassistant_fermentation_effective_air_target
sensor.brewassistant_fermentation_climate_demand
sensor.brewassistant_fermentation_climate_mode
sensor.brewassistant_fermentation_air_target_reason
sensor.brewassistant_fermentation_liquid_delta
sensor.brewassistant_fermentation_air_liquid_delta
sensor.brewassistant_fermentation_air_target_summary
```

---

## Test mode selector

A read-only test selector exists for validating recommendations without changing real process state.

```text
select.brewassistant_fermentation_air_target_test_mode
```

Options:

```text
Off
Fermentation
Cold crash
```

Behavior:

```text
Off
→ normal process-scope rules

Fermentation
→ recommendation engine evaluates as fermentation scope

Cold crash
→ recommendation engine evaluates as cold-crash scope
```

The selector is intended for dashboard/debug validation only.

It affects:

```text
Fermentation Air Target Engine recommendation sensors
```

It does not replace a real fermentation runtime and should not be used as production process state.

Safety behavior:

```text
select resets to Off after reload/restart
entity category = diagnostic
```

---

## Scope safety

The engine is scope-safe.

When no fermentation/cold-crash is active and test mode is Off:

```text
mode = standby
demand = standby
effective_air_target = unknown
liquid_delta = unknown
air_liquid_delta = unknown
ready = false
scope_active = false
```

Diagnostics remain available as attributes:

```text
real_liquid_source_available
liquid_source_entity
process_status
process_stage
test_mode
test_mode_active
```

This prevents external probe values, stale Yellow Pill data or unrelated room-temperature liquid readings from appearing as active fermentation control context.

---

## Clamp diagnostics

The engine exposes clamp diagnostics so dashboards can show why a recommended target was changed.

Important attributes:

```text
raw_air_target
effective_air_target
min_air_target
max_air_target
clamp_applied
clamp_reason
target_plausible_for_mode
```

Meaning:

```text
raw_air_target
→ unclamped recommendation calculated from the liquid delta

effective_air_target
→ final recommendation after safety clamp

min_air_target / max_air_target
→ current limits for the active mode

clamp_applied
→ true when raw_air_target was outside limits

clamp_reason
→ below_min_air_target / above_max_air_target / null

target_plausible_for_mode
→ false when the target looks unusual for the selected mode
```

Example:

```text
Cold crash target 1.0 °C, liquid 21.9 °C
raw_air_target = -0.5 °C
effective_air_target = 0.5 °C
clamp_applied = true
clamp_reason = below_min_air_target
```

---

## Real liquid requirement

The engine requires a real liquid source.

It does not use chamber fallback as liquid.

Invalid liquid contexts:

```text
liquid source = Chamber fallback
liquid source unavailable
fallback_active = true
no active fermentation/cold-crash scope and test mode Off
```

---

## Modes

Current modes:

```text
standby
fermentation
cold_crash
```

Mode is derived from BrewAssistant process state, target mode or the read-only test selector.

---

## Demands

Possible demand states include:

```text
standby
unavailable
strong_cooling
cooling
mild_cooling
nudge_cooling
settle
hold
relax
ease_cooling
hold_warm
warm_or_relax
```

Demand is only a recommendation label. It does not perform control actions.

---

## Cold-crash recommendation model

Cold crash is intentionally more aggressive than normal fermentation, but still avoids overcooling near target.

Example behavior:

```text
liquid far above cold-crash target
→ chamber air target below liquid target
→ demand strong_cooling / cooling

liquid approaching target
→ chamber air target closer to liquid target
→ demand mild_cooling / settle

liquid at or below target
→ chamber air target raised
→ demand hold / relax
```

Current cold-crash clamps:

```text
minimum recommended air target = 0.5 °C
maximum recommended air target = 8.0 °C
```

---

## Fermentation recommendation model

Fermentation recommendations are gentler than cold crash.

Example behavior:

```text
liquid above target
→ chamber air target below liquid target
→ demand cooling / mild_cooling / nudge_cooling

liquid close to target
→ chamber air target equals liquid target
→ demand hold

liquid below target
→ chamber air target above liquid target
→ demand ease_cooling / hold_warm / warm_or_relax
```

Current fermentation clamps:

```text
minimum recommended air target = 7.0 °C
maximum recommended air target = 35.0 °C
```

---

## Current UI

Current dashboard card:

```text
Fermentation Air Target Card v1.1
```

Recommended placement:

```text
Inside Fermentation Cockpit
below the fermentation overview/top card
near Temperature Stats
```

The test mode selector should live behind the debug expander, not in the main cockpit view.

Expected standby text:

```text
Standby · ej aktiv jäsning
Real liquid finns, men används inte förrän fermentation/cold crash är aktiv
```

---

## Validation snapshots

Validated standby behavior:

```text
Test mode = Off
Mode = standby
Demand = standby
Air target = unknown
Reason = no active fermentation or cold-crash scope
Ready = False
Scope = False
Test active = False
Liquid = None
Target = None
Target plausible = None
Raw air target = None
Effective air target = None
Min air target = None
Max air target = None
Clamp applied = False
Clamp reason = None
Liquid delta = unknown
Air/liquid delta = unknown
Summary = standby · standby · no active fermentation or cold-crash scope
```

Validated cold-crash test behavior:

```text
Test mode = Cold crash
Mode = cold_crash
Demand = strong_cooling
Air target = 0.5
Reason = test mode: cold crash; liquid far above cold-crash target
Ready = True
Scope = True
Test active = True
Liquid = 21.87
Target = 1.0
Target plausible = True
Raw air target = -0.5
Effective air target = 0.5
Min air target = 0.5
Max air target = 8.0
Clamp applied = True
Clamp reason = below_min_air_target
Liquid delta = 20.87
Air/liquid delta = -18.76
Summary = test · cold_crash · strong_cooling · liquid 21.9 → 1.0 °C · air target 0.5 °C · clamp below_min_air_target
```

Validated fermentation test behavior:

```text
Test mode = Fermentation
Mode = fermentation
Demand = cooling
Air target = 7.0
Reason = test mode: fermentation; liquid above fermentation target; target unusual for fermentation mode
Ready = True
Scope = True
Test active = True
Liquid = 21.87
Target = 1.0
Target plausible = False
Raw air target = -0.5
Effective air target = 7.0
Min air target = 7.0
Max air target = 35.0
Clamp applied = True
Clamp reason = below_min_air_target
Liquid delta = 20.87
Air/liquid delta = -18.72
Summary = test · fermentation · cooling · liquid 21.9 → 1.0 °C · air target 7.0 °C · clamp below_min_air_target
```

This is correct because a real liquid source may exist while no active fermentation/cold-crash process is in scope. The test selector can wake the recommendation engine for validation without changing process state.

---

## Future direction

This engine is the read-only precursor to a future Fermentation Climate Supervisor.

Possible future chain:

```text
Fermentation Air Target Engine
→ Fermentation Climate Supervisor
→ climate.fermentation_chamber target
→ Home Assistant thermostat / climate layer
→ cooling/heating hardware
```

Important rule:

```text
Liquid temperature remains the process goal.
Chamber air target is only the control tool.
```

Future implementation should follow the same boundary as Climate Supervisor:

```text
BrewAssistant calculates target.
Home Assistant climate layer handles compressor/heater switching and cycle safety.
```
