# Kegerator Fan Backend

BrewAssistant's kegerator fan backend controls only the kegerator circulation fan.

Kegerator and Fermentation are separate logical backends. The kegerator fan backend must not read fermentation scope, fermentation climate targets, fermentation supervisor state or fermentation process entities.

## Architecture boundary

```text
Kegerator backend
  -> kegerator climate context
  -> kegerator air temperature
  -> physical kegerator power
  -> physical kegerator fan

Fermentation backend
  -> separate backend
  -> no dependency from kegerator fan control
```

The current installation may temporarily reuse the same physical refrigerator for fermentation. That hardware reuse is not represented as a cross-backend software dependency.

Physical compressor activity is still observable through the configured kegerator power source, so compressor-follow and afterrun remain useful even when another controller temporarily causes the refrigerator compressor to run.

## Control ownership

The fan controller owns only:

```text
switch.kegerator_fan
```

The master control is:

```text
switch.brewassistant_kegerator_fan_auto_enabled
```

The master switch is **off by default**. When it is off, BrewAssistant releases fan ownership and does not force the physical fan on or off.

When fan-auto is enabled, the fan section uses `Direct action` by default and is evaluated by one scheduler only:

```text
BrewAssistant fan-auto switch timer
  -> kegerator fan backend
  -> policy router
  -> switch.kegerator_fan
```

The switch timer runs every 30 seconds and performs an immediate tick when fan-auto is enabled. Changing the fan mode also requests an immediate fan evaluation.

The coordinator is not a second fan scheduler and the old standalone fan watchdog has been retired.

## Fan modes

```text
Off
Cooling only
Afterrun
Smart auto
Always on
```

`Smart auto` is the default mode when no previous valid restored selection exists.

### Off

Fan-auto owns the fan and keeps it off.

```text
Fan auto OFF -> BrewAssistant releases the fan; physical state is unmanaged.
Mode Off     -> BrewAssistant owns the fan and requests OFF.
```

### Cooling only

The fan follows physical compressor activity:

```text
compressor active -> fan ON
compressor idle   -> fan OFF
```

No afterrun is created or consumed in this mode.

### Afterrun

The fan follows the compressor and continues for the configured time after a detected compressor stop:

```text
compressor active
  -> fan ON

compressor active -> idle
  -> start configured afterrun window
  -> fan remains ON

afterrun expires
  -> fan OFF
```

Afterrun is created only in `Afterrun` and `Smart auto`. Changing to a non-afterrun mode clears stale afterrun state.

### Smart auto

Smart auto combines:

```text
physical compressor activity
afterrun
kegerator climate cooling demand
kegerator air-temperature delta
kegerator air-temperature trend
```

Decision priority:

```text
1. compressor active
   -> fan ON

2. active afterrun
   -> fan ON

3. kegerator climate reports hvac_action=cooling
   -> fan ON

4. kegerator air >= kegerator target + 0.8 °C
   -> fan ON

5. warming trend >= +0.20 °C/h and <= +5.00 °C/h
   -> fan ON

6. fan already running and temperature/trend still outside stop hysteresis
   -> keep fan ON

7. stable near kegerator target
   -> fan OFF
```

Smart auto hysteresis:

```text
start delta threshold: +0.80 °C
stop delta threshold:  +0.25 °C
start trend threshold: +0.20 °C/h
stop trend threshold:  +0.05 °C/h
```

A warming rate above +5 °C/h is ignored as a circulation trigger because restart/statistics spikes should not wake fan control.

If the kegerator climate context is unavailable or disabled, Smart auto does not borrow a target from any other backend. After compressor/afterrun demand has ended, temperature-based circulation fails passive.

That gives the current shared-hardware installation this behavior:

```text
kegerator climate unavailable/off
  + compressor physically running
    -> fan ON

compressor stops
  -> afterrun

afterrun expires
  -> fan OFF
```

No fermentation state is required for that behavior.

### Always on

While fan-auto is enabled, the fan is kept on.

## Compressor detection

The configured kegerator power source is used, with the BrewAssistant fallback resolving to:

```text
sensor.kegerator_power
```

Compressor activity is inferred as:

```text
power > 20 W
```

The food refrigerator/freezer power sensor is not a kegerator source.

## Fan feedback

The physical fan is considered running when either:

```text
switch.kegerator_fan == on
```

or the configured fan-power source is above 2 W. The default fan-power source is:

```text
sensor.kegerator_fan_power
```

## Kegerator temperature context

Smart temperature decisions use only:

```text
climate.kegerator_kylskap
configured kegerator air-temperature source
sensor.brewassistant_kegerator_air_temperature_average
```

The configured default air-temperature source is currently:

```text
sensor.kyl_temperatur_4
```

The backend never falls back to `climate.fermentation_chamber` or any fermentation target.

## Runtime and afterrun state

Compressor transitions are updated only by the active apply loop. Dashboard snapshot reads are side-effect free.

Important transition states:

```text
compressor_idle_to_active
compressor_active_to_idle
```

A falling compressor edge creates `afterrun_until` only when the active mode supports afterrun.

Afterrun state is runtime state in `hass.data`; it is cleared when fan-auto is disabled, when incompatible modes are selected and when the timer expires. Disabling fan-auto still does **not** turn the physical fan off.

## Apply locking

Fan apply is protected by an async lock. This prevents overlapping explicit/event-driven calls from issuing duplicate fan service actions while a previous action is still being verified.

## Diagnostics

Diagnostics are attributes on:

```text
switch.brewassistant_kegerator_fan_auto_enabled
```

Key attributes include:

```text
source
architecture_scope
strategy
scheduler_owner
controller_enabled
control_owner
fan_mode
status
fan_reason
fan_should_run
fan_action
fan_state
fan_power_w
compressor_active
power_entity
power_w
afterrun_active
afterrun_until
afterrun_remaining_minutes
climate_entity
climate_context_source
climate_state
current_temperature
target_temperature
temperature_delta
trend_c_per_hour
temperature_context_available
last_transition
last_apply_result
```

Backend source:

```text
python_kegerator_fan_backend_v4_separated
```

Architecture scope:

```text
kegerator_only
```

When fan-auto is disabled the diagnostics explicitly report a disabled/unmanaged controller rather than a hypothetical physical request.

## Separation contract

Regression tests enforce that the kegerator fan backend contains no references to:

```text
climate.fermentation_chamber
fermentation effective-air target
fermentation supervisor
fermentation scope
shared-cooling bridge
climate ownership conflict
```

This means a future dedicated fermentation vessel with integrated heating/cooling can be implemented by changing the Fermentation backend without changing kegerator fan control.

## Validation contract

Automated regression tests cover:

```text
Smart auto is the default
master disabled -> physical fan unmanaged
Mode Off -> fan OFF request
Cooling only ignores stale afterrun
Afterrun mode uses its active timer
Smart auto starts on warm kegerator air
Smart auto hysteresis prevents chatter
Smart auto fails passive without kegerator temperature context
physical compressor activity overrides missing temperature context
active afterrun overrides missing temperature context
kegerator backend has no fermentation dependency
only the fan-auto switch timer is the periodic fan scheduler
old fan watchdog file remains retired
```

Physical Home Assistant validation after merge/update/restart:

```text
[ ] verify all five modes against switch.kegerator_fan
[ ] verify compressor >20 W starts fan in Cooling only / Afterrun / Smart auto
[ ] verify compressor falling edge starts configured afterrun
[ ] verify fan stops after fixed Afterrun expiry
[ ] verify Smart auto continues circulation on kegerator temperature/trend demand
[ ] verify Smart auto stops inside hysteresis stop band
[ ] verify master OFF leaves current physical fan state untouched
[ ] with kegerator climate OFF, verify compressor + afterrun still work
[ ] verify multi-cycle behavior across Home Assistant restart
```
