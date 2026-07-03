# Setup

This guide describes the current BrewAssistant beta setup in Home Assistant.

BrewAssistant is centered on the Python custom integration in `custom_components/brewassistant/`. Old YAML package files are no longer the source of truth for mainline setup.

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

## 3. Post-update smoke test

After a beta.7 update, verify the entities used by the latest BrewZilla mash-in flow:

```text
binary_sensor.brewassistant_brewzilla_mash_in_gate_pending
button.brewassistant_brewzilla_mash_in_complete
button.brewassistant_brewzilla_start_mash_circulation
```

The two button entities are the intended operator-action path. Dashboard YAML should call `button.press` on those entities, not duplicate the backend action through separate workaround services.

---

## 4. Add dashboard cards

Dashboard YAML is optional and should be treated as presentation only.

Current dashboard examples live under:

```text
dashboard/
```

Current baseline/dashboard policy is documented in:

```text
dashboard/README.md
docs/dashboard-baselines.md
```

Current dashboard/card files:

```text
dashboard/brewassistant_sanity.yaml
dashboard/cards/brewassistant_hub.yaml
dashboard/cards/brewassistant_brewday.yaml
dashboard/cards/brewassistant_brewday_bf_reload.yaml
dashboard/cards/brewassistant_brewday_event_log.yaml
dashboard/cards/brewassistant_manual_brewday.yaml
dashboard/cards/brewassistant_source_health.yaml
dashboard/cards/brewfather_feed.yaml
dashboard/cards/brewfather_recipe.yaml
dashboard/cards/brewtracker_runtime.yaml
dashboard/cards/brewzilla.yaml
dashboard/cards/brewzilla_mash_in_confirm.yaml
dashboard/cards/brewzilla_local_control.yaml
dashboard/cards/brewzilla_advice_auto.yaml
dashboard/cards/brewzilla_safety_rcl.yaml
dashboard/cards/brewzilla_learning.yaml
dashboard/cards/counterflow_chiller.yaml
dashboard/cards/carbonation.yaml
dashboard/cards/fermentation.yaml
dashboard/cards/kegerator.yaml
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

## 5. Recommended integrations and source entities

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
binary_sensor.brewassistant_runtime_brewfather_available
binary_sensor.brewassistant_brewzilla_mash_in_gate_pending
button.brewassistant_brewzilla_mash_in_complete
button.brewassistant_brewzilla_start_mash_circulation
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

---

## 6. Operational policy

```text
- Python integration owns runtime normalization, calculations and hardware decisions.
- Dashboard YAML owns presentation and explicit operator actions.
- Avoid hidden workflow logic in dashboard templates.
- Avoid duplicate action paths for the same physical action.
- Keep old YAML packages disabled unless intentionally testing migration behavior.
- Restart Home Assistant after integration updates.
```
