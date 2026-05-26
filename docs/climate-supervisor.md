# Climate Supervisor

Climate Supervisor is the active BrewAssistant path for kegerator/carbonation temperature control.

It replaces the experimental Kegerator Guard direct-switch controller.

---

## Purpose

Climate Supervisor owns dynamic target selection, not compressor switching.

```text
BrewAssistant Climate Supervisor
→ calculates a dynamic air target from temperature delta
→ applies that target to climate.kegerator_kylskap
→ Home Assistant thermostat controls switch.kegerator
```

This keeps compressor protection in the Home Assistant climate/thermostat layer while BrewAssistant provides the brewing-aware target logic.

---

## Current architecture

```text
sensor.kyl_temperatur_4
        ↓
Climate Supervisor
        ↓
climate.kegerator_kylskap target temperature
        ↓
Generic thermostat / climate integration
        ↓
switch.kegerator
```

Important boundary:

```text
BrewAssistant adjusts climate target.
BrewAssistant does not directly short-cycle switch.kegerator.
```

---

## Active entities

```text
switch.brewassistant_climate_supervisor_enabled
climate.kegerator_kylskap
sensor.kyl_temperatur_4
sensor.brewassistant_carbonation_status
sensor.brewassistant_carbonation_temperature
switch.kegerator
```

Diagnostic attributes on `switch.brewassistant_climate_supervisor_enabled` include:

```text
mode
status
action
reason
base_target_temperature
effective_air_target
air_temperature
air_delta
cooling_demand
controller_entity
controller_state
controller_target_temperature
target_delta
carbonation_active
carbonation_status
carbonation_temperature
legacy_guard_enabled
last_control_action
last_evaluation
summary
```

---

## Dynamic target behavior

Climate Supervisor currently treats the climate target as a dynamic air target around a base serving/carbonation target.

Example with base target `4.0 °C`:

```text
Air delta >= +2.0 °C → effective target = 3.4 °C
Air delta >= +1.0 °C → effective target = 3.6 °C
Air delta >= +0.5 °C → effective target = 3.8 °C
Air close to target   → effective target = 4.0 °C
Air delta <= -0.3 °C → effective target = 4.2 °C
Air delta <= -0.7 °C → effective target = 4.4 °C
```

The climate integration then decides when to run or stop the compressor using its own hysteresis, min-cycle and cooldown rules.

---

## Verified behavior

Validated during active carbonation:

```text
Air 5.69 °C
Base target 4.0 °C
Effective target 3.6 °C
climate.kegerator_kylskap target changed from 4.0 °C to 3.6 °C
Last control result: applied
```

Also validated:

```text
Air 3.11 °C
Base target 4.0 °C
Effective target 4.4 °C
climate.kegerator_kylskap target changed from 3.6 °C to 4.4 °C
switch.kegerator turned off through climate thermostat behavior
Last control result: applied
```

---

## Kegerator Guard deprecation

`switch.brewassistant_kegerator_guard_enabled` and `kegerator_guard.py` are deprecated as an active control path.

Reason:

```text
Direct switch control was too fragile and placed compressor-cycle responsibility inside BrewAssistant.
```

Current rule:

```text
switch.brewassistant_kegerator_guard_enabled = off
```

Climate Supervisor may turn the legacy guard off if it is accidentally enabled.

The legacy guard can remain in the code temporarily as deprecated/parked compatibility until Climate Supervisor is fully validated and the UI has been migrated.

---

## Current operating rule

For carbonation/serving:

```text
Climate Supervisor enabled
climate.kegerator_kylskap = cool
climate.kegerator_kylskap owns switch.kegerator
Kegerator Guard disabled
```

For future fermentation/cold-crash control:

```text
Fermentation target = liquid temperature
Climate/chamber target = dynamically calculated air temperature
Climate integration = compressor/heater control layer
```

---

## Validation snippet

```jinja
Supervisor = {{ states('switch.brewassistant_climate_supervisor_enabled') }}
Status = {{ state_attr('switch.brewassistant_climate_supervisor_enabled', 'status') }}
Action = {{ state_attr('switch.brewassistant_climate_supervisor_enabled', 'action') }}
Air = {{ state_attr('switch.brewassistant_climate_supervisor_enabled', 'air_temperature') }}
Effective target = {{ state_attr('switch.brewassistant_climate_supervisor_enabled', 'effective_air_target') }}
Climate target = {{ state_attr('switch.brewassistant_climate_supervisor_enabled', 'controller_target_temperature') }}
Kegerator = {{ states('switch.kegerator') }}
Last control = {{ state_attr('switch.brewassistant_climate_supervisor_enabled', 'last_control_action') }}
```

Expected healthy state after a target apply:

```text
Action = hold_target
Effective target = Climate target
Last control result = applied
```
