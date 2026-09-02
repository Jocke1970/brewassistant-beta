# Kegerator Temperature Presets

BrewAssistant exposes a persistent kegerator temperature preset selector:

```text
select.brewassistant_kegerator_temperature_preset
```

Preset contract:

```text
Cold Crash -> 2.0 °C
Storage    -> 3.0 °C
Serving    -> 4.0 °C
```

`Serving` is the fallback/default when no valid restored state exists. The select is a Home Assistant `RestoreEntity`, so the most recently selected preset is restored after a Home Assistant restart and reapplied to:

```text
climate.kegerator_kylskap
```

If the kegerator climate is off during restoration, BrewAssistant requests `cool` mode before applying the restored target.

## Generic Thermostat configuration

The kegerator uses Home Assistant `generic_thermostat`, not Dual Smart Thermostat.

Generic Thermostat has native target-temperature restore. When `target_temp` is omitted from its YAML configuration, Home Assistant restores the previously selected target temperature after restart when a previous value is available.

Therefore the kegerator climate configuration should not hard-code a startup target such as:

```yaml
target_temp: 1.5
```

Instead, omit `target_temp` and keep the normal kegerator limits, tolerances and compressor protection. BrewAssistant quick presets set the climate target through `climate.set_temperature`, while Generic Thermostat provides the underlying target restore.

The ownership model is:

```text
BrewAssistant preset select
  -> remembers the selected named preset
  -> applies climate.set_temperature

Generic Thermostat
  -> owns cooling hysteresis / compressor switching
  -> restores its last target temperature across restart
```

The select still exposes its numeric preset target as the `target_temperature` attribute for diagnostics and dashboard presentation. A thermostat template is not required for the kegerator.

Dual Smart Thermostat belongs to the separate Fermentation backend and must not be used as the kegerator configuration contract.

## Climate Supervisor

The Kegerator Climate Supervisor uses the selected preset target as its base target instead of owning a separate fixed 4.0 °C base.

Its dynamic correction remains relative to that base:

```text
+2.0 °C air delta -> base - 0.6 °C
+1.0 °C air delta -> base - 0.4 °C
+0.5 °C air delta -> base - 0.2 °C
-0.3 °C air delta -> base + 0.2 °C
-0.7 °C air delta -> base + 0.4 °C
```

The absolute effective-target safety range is 1.0–12.0 °C so Cold Crash and Storage are not forced back into the old serving-only 3.4–5.0 °C range.

## Dashboard

Quick-select example cards are provided in both dashboard languages:

```text
dashboard/cards/kegerator_temperature_presets.yaml
dashboard/cards/kegerator_temperature_presets_sv.yaml
```

The Swedish card translates only presentation labels; the `select.select_option` values stay canonical English backend values.
