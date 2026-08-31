# Kegerator Fan Backend

BrewAssistant's kegerator fan backend controls the circulation fan around the shared kegerator / fermentation-chamber refrigerator.

The climate layer still owns cooling/heating targets and compressor cycling. Fan control owns only:

```text
switch.kegerator_fan
```

## Control ownership

The master control is:

```text
switch.brewassistant_kegerator_fan_auto_enabled
```

The master switch is **off by default**. When it is off, BrewAssistant releases fan ownership and does not force the physical fan on or off.

When fan-auto is enabled, the fan section uses `Direct action` by default and is evaluated by one scheduler only:

```text
BrewAssistant fan-auto switch timer -> fan backend -> policy router -> switch.kegerator_fan
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

This differs from disabling the fan-auto master switch:

```text
Fan auto OFF -> BrewAssistant releases the fan; physical state is unmanaged.
Mode Off     -> BrewAssistant owns the fan and requests OFF.
```

### Cooling only

The fan follows inferred compressor activity:

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

Smart auto combines compressor activity, afterrun, climate demand, temperature delta and temperature trend.

Decision priority:

```text
1. compressor active
   -> fan ON

2. active afterrun
   -> fan ON

3. active climate reports hvac_action=cooling
   -> fan ON

4. air >= active target + 0.8 °C
   -> fan ON

5. warming trend >= +0.20 °C/h and <= +5.00 °C/h
   -> fan ON

6. fan already running and temperature/trend still outside stop hysteresis
   -> keep fan ON

7. stable near target
   -> fan OFF
```

Smart auto uses hysteresis to avoid a fan state change on every 30-second tick:

```text
start delta threshold: +0.80 °C
stop delta threshold:  +0.25 °C
start trend threshold: +0.20 °C/h
stop trend threshold:  +0.05 °C/h
```

A large apparent warming rate above +5 °C/h is ignored as a circulation trigger because restart/statistics spikes should not wake fan control.

If temperature/target context is unavailable, Smart auto fails passive after any compressor/afterrun requirement has ended. It does not invent a temperature-based circulation request.

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

## Shared fridge climate context

The physical refrigerator can be used both for serving/kegerator operation and as the fermentation chamber.

Smart auto therefore resolves an **active climate context** rather than assuming that an enabled kegerator climate always owns the refrigerator.

Priority:

```text
active fermentation scope / fermentation supervisor
  -> climate.fermentation_chamber

otherwise active serving/kegerator climate
  -> climate.kegerator_kylskap
```

The fermentation effective-air-target scope is used as ownership evidence. Both climate entities merely existing or being enabled is not itself considered a conflict.

A conflict is reported only when BrewAssistant fermentation ownership and an active serving/carbonation kegerator-supervisor scope claim the refrigerator simultaneously. Smart temperature circulation then fails passive until the ownership ambiguity is resolved; compressor and active afterrun still retain priority.

For a dual-setpoint fermentation climate, the cooling high target is used during cooling, the heating low target during heating, and the midpoint when idle.

## Runtime and afterrun state

Compressor transitions are updated only by the active apply loop. Dashboard snapshot reads are side-effect free.

Important transition states:

```text
compressor_idle_to_active
compressor_active_to_idle
```

A falling compressor edge creates `afterrun_until` only when the active mode supports afterrun.

Afterrun state is runtime state in `hass.data`; it is intentionally cleared when fan-auto is disabled and when incompatible modes are selected. Disabling fan-auto still does **not** turn the physical fan off.

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
active_climate_entity
climate_conflict
current_temperature
target_temperature
temperature_delta
trend_c_per_hour
temperature_context_available
last_transition
last_apply_result
```

Backend version/source for this state machine:

```text
python_kegerator_fan_backend_v3_smart_auto
```

When fan-auto is disabled the diagnostics explicitly report a disabled/unmanaged controller rather than a hypothetical physical request.

## Validation contract

Automated regression tests cover:

```text
Smart auto is the default
master disabled -> physical fan unmanaged
Mode Off -> fan OFF request
Cooling only ignores stale afterrun
Afterrun mode uses its active timer
Smart auto starts on warm air
Smart auto hysteresis prevents chatter
Smart auto fails passive without temperature context
compressor activity has priority in Smart auto
only the fan-auto switch timer is the periodic fan scheduler
old fan watchdog file remains retired
```

Physical Home Assistant validation is still required after backend changes:

```text
[ ] verify all five modes against switch.kegerator_fan
[ ] verify compressor >20 W starts fan in Cooling only / Afterrun / Smart auto
[ ] verify compressor falling edge starts configured afterrun
[ ] verify fan stops after fixed Afterrun expiry
[ ] verify Smart auto continues circulation when air/trend demand remains
[ ] verify Smart auto stops inside hysteresis stop band
[ ] verify master OFF leaves current physical fan state untouched
[ ] verify serving and fermentation climate-context handoff
[ ] verify multi-cycle behavior across Home Assistant restart
```
