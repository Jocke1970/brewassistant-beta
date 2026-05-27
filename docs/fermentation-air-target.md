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

## Current module

```text
custom_components/brewassistant/fermentation_air_target.py
```

Registered through:

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

## Scope safety

The engine is scope-safe.

When no fermentation/cold-crash is active:

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
```

This prevents external probe values, stale Yellow Pill data or unrelated room-temperature liquid readings from appearing as active fermentation control context.

---

## Real liquid requirement

The engine requires a real liquid source.

It does not use chamber fallback as liquid.

Invalid liquid contexts:

```text
liquid source = Chamber fallback
liquid source unavailable
fallback_active = true
no active fermentation/cold-crash scope
```

---

## Modes

Current modes:

```text
standby
fermentation
cold_crash
```

Mode is derived from BrewAssistant process state and target mode.

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
Fermentation Air Target Card v1.0
```

Recommended placement:

```text
Inside Fermentation Cockpit
below the fermentation overview/top card
near Temperature Stats
```

Expected standby text:

```text
Standby · ej aktiv jäsning
Real liquid finns, men används inte förrän fermentation/cold crash är aktiv
```

---

## Validation snapshot

Validated standby behavior:

```text
Mode = standby
Demand = standby
Air target = unknown
Reason = no active fermentation or cold-crash scope
Liquid delta = unknown
Air/liquid delta = unknown
Ready = False
Scope = False
Real liquid = True
Source = sensor.yellow_pill_temperature
```

This is correct because a real liquid source may exist while no active fermentation/cold-crash process is in scope.

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
