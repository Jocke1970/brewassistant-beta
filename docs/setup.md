# Setup

This guide describes the current BrewAssistant beta setup in Home Assistant.

BrewAssistant is now centered on the Python custom integration in `custom_components/brewassistant/`. Old YAML package files are no longer the source of truth for mainline setup.

---

## 1. Install the custom integration

Copy the integration folder into Home Assistant:

```text
/config/custom_components/brewassistant/
```

The folder should contain files such as:

```text
__init__.py
manifest.json
sensor.py
binary_sensor.py
switch.py
button.py
select.py
number.py
services.yaml
brand/icon.png
brand/logo.png
brewday/
brewzilla/
carbonation_backend/
climate_backend/
cooling/
fermentation/
kegerator/
shared/
```

Recommended update pattern from a clone of this repository:

```bash
rsync -a --delete \
  /tmp/brewassistant-beta/custom_components/brewassistant/ \
  /config/custom_components/brewassistant/
```

Always back up the currently installed integration before replacing it, but keep backups outside `/config/custom_components/`, for example under `/config/brewassistant_backups/`.

---

## 2. Restart Home Assistant

After installing or updating the custom integration:

```text
1. Restart Home Assistant.
2. Check Home Assistant logs for BrewAssistant import/setup errors.
3. Confirm that BrewAssistant entities are created.
```

If Home Assistant keeps old entity IDs from the entity registry, verify the actual entity IDs in Developer Tools → States before editing dashboards.

---

## 3. Add dashboard cards

Dashboard YAML is optional and should be treated as presentation only.

Current baseline/dashboard policy is documented in:

```text
docs/dashboard-baselines.md
```

Dashboard cards may use custom Lovelace cards such as:

```text
custom:button-card
custom:vertical-stack-in-card
custom:mushroom-*
custom:expander-card
custom:gauge-card-pro
custom:bar-card
custom:apexcharts-card
```

Install required frontend cards through HACS before using dashboard examples.

---

## 4. Recommended integrations and source entities

BrewAssistant can run with different levels of connected hardware and data.

### Brewday / BrewZilla

Useful sources:

```text
BrewZilla / RAPT Cloud Link telemetry
Brewfather Brew Tracker runtime data
Shelly/local power telemetry
Manual Brewday runtime services
```

Main BrewAssistant areas:

```text
sensor.brewassistant_brewday_*
sensor.brewassistant_brewday_event_log_*
sensor.brewassistant_brewzilla_*
select.brewassistant_brewzilla_mash_temperature_source
```

### Kegerator / serving

Useful sources:

```text
climate.kegerator_kylskap
sensor.kyl_temperatur_4
sensor.kegerator_power
switch.kegerator_fan
sensor.kegerator_fan_power
```

Main BrewAssistant entities:

```text
switch.brewassistant_kegerator_guard_enabled
switch.brewassistant_kegerator_fan_auto_enabled
select.brewassistant_kegerator_fan_mode
number.brewassistant_kegerator_fan_afterrun_minutes
```

Preferred clean entity IDs should not include area/device prefixes such as `bryggeriet_`. If Home Assistant creates prefixed entities, clean them through the Entity Registry UI.

### Fermentation

Useful sources:

```text
climate.fermentation_chamber
RAPT Pill or other gravity/temperature source
switch.fermentation_heat_mat
sensor.fermentation_heat_mat_power
```

Main BrewAssistant areas:

```text
sensor.brewassistant_fermentation_*
sensor.brewassistant_smart_*
sensor.brewassistant_gravity
```

### Carbonation

Main control entities:

```text
select.brewassistant_carbonation_method
number.brewassistant_carbonation_target_volumes
number.brewassistant_carbonation_start_volumes
number.brewassistant_carbonation_pressure_bar
```

Main display sensors:

```text
sensor.brewassistant_carbonation_status
sensor.brewassistant_carbonation_method
sensor.brewassistant_carbonation_target_volumes
sensor.brewassistant_carbonation_temperature
sensor.brewassistant_carbonation_recommended_pressure_bar
```

---

## 5. Legacy local packages

The `packages/` directory is no longer part of the main repository setup.

Older Home Assistant installs may still have local BrewAssistant YAML packages under `/config/packages/` or `/config/packages_disabled/`. Treat those as legacy/local files only.

Recommended cleanup policy:

```text
- Do not enable old package helpers together with the Python integration unless deliberately testing migration behavior.
- Disable old kegerator/fermentation/carbonation package helpers after verifying dashboards no longer depend on them.
- Use Developer Tools → States and the Entity Registry UI to remove orphaned unavailable entities.
- Keep backup copies outside /config/custom_components/.
```

---

## 6. Basic verification after restart

Useful checks:

```text
sensor.brewassistant_core_version
sensor.brewassistant_next_action
sensor.brewassistant_brewday_runtime_status
sensor.brewassistant_brewday_stage
sensor.brewassistant_brewday_event_log_summary
sensor.brewassistant_brewzilla_wort_temperature
switch.brewassistant_kegerator_guard_enabled
switch.brewassistant_kegerator_fan_auto_enabled
select.brewassistant_kegerator_fan_mode
number.brewassistant_kegerator_fan_afterrun_minutes
sensor.brewassistant_carbonation_status
sensor.brewassistant_fermentation_chamber_air_temperature_average
```

Baseline checks should show:

```text
- no active `bryggeriet_brewassistant_*` entity IDs
- `sensor.brewassistant_brewday_event_log_summary` exists
- old `sensor.brewassistant_brewday_audit_*` entities are gone or unknown
- `climate.kegerator_kylskap` remains `cool` when serving cooling should be active
- `switch.kegerator_fan` follows fan mode when fan-auto is enabled
```

---

## 7. Updating

Recommended update flow:

```text
1. Back up /config/custom_components/brewassistant/ to /config/brewassistant_backups/.
2. Pull latest main from this repository.
3. Sync custom_components/brewassistant/ into Home Assistant.
4. Restart Home Assistant.
5. Check logs.
6. Verify key entities and dashboards.
```

Dashboard cards should be updated separately from backend installation.
