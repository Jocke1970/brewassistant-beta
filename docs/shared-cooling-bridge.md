# Shared Cooling Hardware Bridge

BrewAssistant treats the kegerator and fermentation chamber as separate logical backends even when they temporarily share one physical refrigerator.

## Architecture

```text
Kegerator backend
  -> cooling-only appliance context
  -> physical compressor observation via sensor.kegerator_power
  -> circulation fan control via switch.kegerator_fan

Fermentation backend
  -> fermentation process context
  -> heating + cooling demand
  -> liquid/chamber temperature logic
  -> future dedicated fermentation heat/cool hardware
```

The current installation temporarily uses the kegerator refrigerator for fermentation cooling. That hardware sharing is represented by an explicit compatibility option:

```text
shared_kegerator_fermentation_cooling = true
```

The option defaults to `true` so existing installations keep the current shared-fridge behavior after update.

## Bridge enabled

During an active fermentation scope, the kegerator fan backend may use `climate.fermentation_chamber` as the temperature/target context for Smart auto while it continues to observe the physical kegerator compressor and control only the kegerator circulation fan.

The bridge does **not** merge the two logical backends and does not give the kegerator fan backend ownership of fermentation heating/cooling decisions.

## Bridge disabled

When fermentation later receives dedicated physical heat/cool hardware, disable the option in BrewAssistant integration options:

```text
shared_kegerator_fermentation_cooling = false
```

The kegerator fan backend then ignores `climate.fermentation_chamber` entirely and uses only the kegerator climate context. Fermentation continues independently on its own hardware.

## Diagnostics

The fan-auto switch exposes:

```text
architecture_scope = kegerator_fan_only
climate_context_source
shared_cooling_bridge_enabled
shared_cooling_bridge_active
```

Expected context sources:

```text
kegerator                           normal serving/kegerator context
fermentation_shared_cooling_bridge temporary shared-fridge fermentation context
none                                no usable climate target context
```

Compressor-follow and afterrun remain based on the physical kegerator power source regardless of which logical backend requested the cooling cycle.
