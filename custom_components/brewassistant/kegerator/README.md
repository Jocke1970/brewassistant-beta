# Kegerator backend

Status: active / mixed modern + legacy control paths  
Code snapshot documented: 2026-09-05

`kegerator` contains serving-fridge support that is intentionally narrower than a generic refrigeration backend. It currently provides:

- circulation-fan decision/control;
- compressor inference and serving-temperature diagnostics;
- a separate legacy/policy-mediated kegerator guard;
- restart climate restore protection;
- serving-temperature preset support.

Normal compressor regulation should remain owned by `climate.kegerator_kylskap` when using the modern climate path. The legacy guard is documented separately below because it can still request physical kegerator switch actions.

## Fan control

`fan_control.py` owns only:

```text
switch.kegerator_fan
```

It does not own compressor switching.

Inputs include:

```text
climate.kegerator_kylskap
configured kegerator air-temperature entity
configured kegerator power entity
configured fan-power entity
rolling kegerator air statistics
fan-auto enable switch
fan-mode select
afterrun-minutes number
```

### Compressor inference

The current fan runtime infers compressor activity from physical kegerator power:

```text
compressor active: power > 20 W
fan running: switch ON or fan power > 2 W
```

This keeps fan afterrun behavior usable even if the refrigerator is temporarily being used by another backend; it does not transfer compressor ownership to fan control.

### Fan modes and afterrun

The pure decision logic lives in `fan_model.py`; the Home Assistant adapter/runtime lives in `fan_control.py`.

The controller tracks compressor active->idle transitions and may maintain a bounded afterrun window. Default afterrun is 10 minutes and the evaluation interval is 30 seconds.

Fan actions are sent through BrewAssistant's common `control_policy.request_action()` layer under section `kegerator_fan`, rather than bypassing policy directly.

Runtime transition/decision/apply diagnostics live in `hass.data`.

## Legacy kegerator guard

`guard.py` is a separate control path and should not be confused with the fan controller or Climate Supervisor.

It observes kegerator air temperature and can request physical actions on:

```text
switch.kegerator
```

Current legacy guard thresholds:

```text
target: 4.0 °C
start cooling: 4.8 °C
stop cooling: 3.4 °C
safety low: 1.0 °C
minimum ON: 10 min
minimum OFF: 6 min
evaluation interval: 30 s
```

Physical ON/OFF requests go through the common control policy under section `kegerator_guard`.

The guard also detects `climate.fermentation_chamber` as a possible conflicting climate controller.

### Restart watchdog

When the legacy guard is enabled, its restart helper can restore `climate.kegerator_kylskap` to:

```text
hvac_mode: cool
target: 4.0 °C
```

if the climate entity is off/unknown/unavailable after Home Assistant restart, and can create a persistent notification about the result.

Note: the integration root also currently has a kegerator climate restore helper. These overlapping restart responsibilities should be treated as technical debt and kept visible when refactoring.

## Climate Supervisor relationship

[`../climate_backend/`](../climate_backend/) contains the modern kegerator Climate Supervisor. It adjusts the climate target and lets the HA climate integration regulate the compressor.

When that supervisor actively applies a target, it turns off the legacy BrewAssistant kegerator guard switch to avoid competing control strategies.

Recommended responsibility split:

```text
HA climate integration
  compressor regulation / hysteresis

climate_backend
  dynamic serving/carbonation target selection

kegerator/fan_control.py
  circulation fan only

kegerator/guard.py
  legacy/policy guard + restart watchdog; do not treat as the primary modern controller
```

## Serving temperature presets

`temperature_preset.py` owns the selected serving-target preset used by the Climate Supervisor as its base target. Keep preset selection separate from real-time compressor/fan decisions.

## Important files

| File | Purpose |
| --- | --- |
| `fan_model.py` | Pure fan decision model |
| `fan_control.py` | HA adapter/runtime, compressor inference, afterrun and policy-mediated fan writes |
| `guard.py` | Legacy kegerator physical-switch guard and restart watchdog |
| `temperature_preset.py` | Serving-temperature preset selection |

## Do not change casually

1. Fan control must not become a hidden compressor controller.
2. Compressor inference from power is an observation used for fan decisions, not ownership.
3. Avoid two simultaneous compressor-control strategies: Climate Supervisor/HA climate and legacy guard must not fight each other.
4. Preserve minimum-cycle/safety behavior if the legacy guard remains available.
5. Keep kegerator and fermentation-chamber ownership separate even when the same physical refrigerator is reused.
