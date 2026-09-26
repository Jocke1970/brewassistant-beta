# GF30 / coolant baseline field note — 2026-09-26

Status: **invalid coolant thermal-learning run / useful configuration finding**

## Test intent

The overnight setup deliberately kept the two systems physically separate:

1. **Freezer + water reservoir**
   - characterize freezer behavior at different thermostat settings;
   - observe freezer-air versus reservoir-liquid response;
   - no connection to the GF30 cooling circuit.

2. **GF30**
   - characterize standalone temperature holding;
   - compare the GF30 internal temperature sensor with external references;
   - RAPT Pill floated near the top;
   - RAPT BLE Thermometer was inserted as an additional liquid reference.

The GF30 target was raised above room temperature so the controller would actively regulate heating during the standalone baseline.

## What invalidated the freezer/reservoir run

The new Home Assistant `generic_thermostat` configuration had been created in YAML, but the configuration had **not been reloaded/restarted into active use** before the overnight run.

The freezer therefore ran without the intended thermostat control and the water reservoir froze.

This means the overnight freezer/reservoir data must **not** be used as valid coolant-response, thermostat-cycle or thermal-learning evidence.

## Useful finding

The incident establishes an explicit preflight requirement for every future coolant/freezer test:

```text
configuration loaded
  -> expected generic_thermostat entity present
  -> correct target_sensor verified
  -> target temperature verified
  -> HVAC mode/action/readback plausible
  -> compressor protection settings verified
  -> only then energize freezer
```

A configured YAML file is not evidence that the active Home Assistant runtime is using that configuration.

Water also cannot be treated as a safe sub-zero coolant. Any later test below the verified freeze range requires a physically suitable coolant mixture and validated material/pump limits.

## Dynamic coolant target design confirmed

The intended future BrewAssistant policy is not to keep the reservoir permanently at the coldest possible temperature.

Conceptually:

```text
coolant_target = gf30_beer_target - adaptive_cooling_headroom
coolant_target = clamp(coolant_target, verified_min_safe, verified_max_useful)
```

The objective is the **warmest coolant temperature that still provides enough cooling authority for the GF30**.

- GF30 continues to own cooling demand and the circulation pump.
- Home Assistant `generic_thermostat` continues to own freezer on/off.
- A future BrewAssistant bridge may only adjust the thermostat target inside verified bounds.
- Stable fermentation, active ramp-down and cold crash may use different headroom.
- Thermal learning may later refine the headroom from physically valid test data.

## Repeat-test requirement

Before repeating the reservoir baseline:

1. thaw and thermally stabilize the reservoir;
2. reload/restart Home Assistant as required;
3. verify the active thermostat entity and target sensor;
4. verify target and compressor-protection settings;
5. confirm freezer OFF before starting;
6. start with a target safely above water freezing;
7. record freezer air, reservoir liquid, thermostat state/action and freezer power over time.

The failed overnight run is retained as configuration/fail-safe evidence, not as a successful thermal characterization.
