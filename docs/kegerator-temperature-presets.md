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

`Serving` is the fallback/default when no valid restored state exists. The select is a Home Assistant `RestoreEntity`, so the most recently selected preset is restored after a Home Assistant restart and immediately reapplied to:

```text
climate.kegerator_kylskap
```

If the kegerator climate is off during restoration, BrewAssistant requests `cool` mode before applying the restored target.

## Template-friendly climate configuration

The select exposes the numeric target as an attribute:

```text
target_temperature
```

Dual Smart Thermostat versions with template-based preset temperatures can therefore replace a fixed preset temperature with the BrewAssistant target. For example, if the kegerator uses the `home` thermostat preset:

```yaml
home_temp: "{{ state_attr('select.brewassistant_kegerator_temperature_preset', 'target_temperature') | float(4) }}"
```

Use the equivalent `*_temp` field if another Dual Smart Thermostat preset is used. The machine-state values remain the English backend values (`Cold Crash`, `Storage`, `Serving`); presentation cards may translate the labels.

This gives two compatible paths:

```text
BrewAssistant preset selection
  -> applies climate.set_temperature immediately

Dual Smart Thermostat template
  -> observes target_temperature
  -> keeps its active preset target aligned with BrewAssistant
```

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
